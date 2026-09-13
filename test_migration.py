"""Cross-computer restore preserves scope and rejects unintended connection changes."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import backups
import server
from core import ValidationError
from locations import LocationStore
from pricing import PriceStore

class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.source=Path(self.tmp.name)/'source';self.dest=Path(self.tmp.name)/'destination'
        self.row=LocationStore(self.source/'locations').save({'name':'Gembu','host':'192.168.88.1','username':'owner','transport':'api'})
        PriceStore(self.source/'prices',self.row['id'],'original-router').write({'daily':{'amount':'500.00','currency':'NGN','label':'NGN 500.00'}})
        self.bundle=backups.export(self.source)
        self.change={**self.row,'host':'10.20.0.1','transport':'api-ssl','port':'8729','username':'new-owner','fingerprint':'ab'*32}
        p=patch.object(server,'DATA',self.dest);p.start();self.addCleanup(p.stop)
        server.route('/api/disconnect',{});self.addCleanup(lambda:server.route('/api/disconnect',{}))
    def test_preview_is_read_only_and_no_secrets(self):
        original=copy.deepcopy(self.bundle)
        with patch.dict('os.environ',{'PAYSTACK_SECRET_KEY':'sk_test_do-not-disclose'}):
            result=server.route('/api/backup/preview',{'backup':self.bundle,'location_updates':[self.change]})
        self.assertFalse(self.dest.exists());self.assertEqual(self.bundle,original)
        self.assertEqual(result['locations'][0]['port'],8729)
        self.assertTrue(result['destination']['configured']['PAYSTACK_SECRET_KEY'])
        self.assertNotIn('sk_test_do-not-disclose',json.dumps(result))
        self.assertIn('host',[x['field'] for x in result['connection_changes']])
    def test_restore_same_location_scope_and_recovery(self):
        LocationStore(self.dest/'locations').save({'name':'Destination','host':'10.1.1.1','username':'admin'})
        before=backups.export(self.dest)
        with patch.object(server,'Router') as router:
            result=server.route('/api/backup/restore',{'backup':self.bundle,'location_updates':[self.change],'migration_ack':True,'confirmation':'RESTORE'})
            router.assert_not_called()
        row=LocationStore(self.dest/'locations').get(self.row['id'])
        self.assertEqual(row['host'],'10.20.0.1');self.assertEqual(row['id'],self.row['id'])
        self.assertEqual(PriceStore(self.dest/'prices',row['id'],'original-router').read()['daily']['amount'],'500.00')
        old=json.loads((self.dest/'recovery'/result['recovery']).read_text())
        self.assertEqual(old['files'],before['files'])
        self.assertEqual(self.bundle['files'],backups.export(self.source)['files'])
    def test_reject_bad_updates_before_writing(self):
        bad=[{**self.change,'id':'f'*24},{**self.change,'host':'127.0.0.1'},
             {**self.change,'transport':'api','host':'8.8.8.8'},
             {**self.change,'port':0},{**self.change,'fingerprint':'bad'},
             {**self.change,'password':'secret'},{**self.change,'name':''},
             {**self.change,'host':None},{**self.change,'port':True}]
        for update in bad:
            with self.subTest(update=update),self.assertRaises(ValidationError):
                server.route('/api/backup/restore',{'backup':self.bundle,'location_updates':[update],'migration_ack':True,'confirmation':'RESTORE'})
        self.assertFalse(self.dest.exists())
    def test_reject_duplicate_locations_and_missing_ack(self):
        with self.assertRaises(ValidationError):backups.prepare(self.bundle,[self.change,self.change])
        with self.assertRaises(ValidationError):server.route('/api/backup/restore',{'backup':self.bundle,'location_updates':[self.change],'confirmation':'RESTORE'})
        self.assertFalse(self.dest.exists())
    def test_connected_restore_refused(self):
        server.route('/api/demo',{})
        with self.assertRaises(ValidationError):server.route('/api/backup/restore',{'backup':self.bundle,'location_updates':[self.change],'migration_ack':True,'confirmation':'RESTORE'})
        self.assertFalse(self.dest.exists())
    def test_legacy_backup_without_locations_unchanged(self):
        bundle={'format':'nelsonict-backup-1','files':{}}
        result=server.route('/api/backup/preview',{'backup':bundle})
        self.assertEqual(result['locations'],[])
        result=server.route('/api/backup/restore',{'backup':bundle,'confirmation':'RESTORE'})
        self.assertEqual(result['restored'],0)
