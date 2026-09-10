import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import server
from core import ValidationError
from locations import LocationStore

class LocationsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.patch=patch.object(server,'DATA',Path(self.temp.name));self.patch.start();self.addCleanup(self.patch.stop)
        server.route('/api/disconnect',{})
    def save(self,**extra):return server.route('/api/locations/save',{'name':'Site A','host':'192.168.88.1','username':'owner','transport':'api','password':'never-store',**extra})['location']
    def test_metadata_persistence_no_password(self):
        row=self.save();self.assertEqual(row['port'],8728)
        self.assertEqual(LocationStore(server.DATA/'locations').get(row['id']),row)
        self.assertNotIn('never-store',''.join(p.read_text() for p in server.DATA.rglob('*.json')))
    def test_rename_delete(self):
        row=self.save();self.save(id=row['id'],name='New name')
        self.assertEqual(server.route('/api/locations/list',{})['locations'][0]['name'],'New name')
        server.route('/api/locations/delete',{'id':row['id']})
        self.assertEqual(server.route('/api/locations/list',{})['locations'],[])
    def test_invalid_addresses_and_name(self):
        for change in ({'name':''},{'host':'127.0.0.1'},{'host':'8.8.8.8'},{'port':0}):
            with self.assertRaises(ValidationError):self.save(**change)
    def test_saved_settings_used_and_plans_cleared(self):
        row=self.save(port=9999)
        server.STATE.update(plan={'stale':True},upload_plan={'stale':True},portal_plan={'stale':True})
        with patch('server.Router') as router,patch('server.snapshot',return_value={'system/identity':[{'name':'router'}]}),patch('server.public_status',return_value={}):
            router.return_value.host=row['host']
            server.route('/api/connect',{'location_id':row['id'],'password':'session-secret','host':'10.0.0.1'})
            self.assertEqual(router.call_args.args[:4],(row['host'],'owner','session-secret',9999))
        self.assertEqual(server.STATE['location_id'],row['id']);self.assertIsNone(server.STATE['plan']);self.assertIsNone(server.STATE['upload_plan'])
        with self.assertRaises(ValidationError):server.route('/api/locations/delete',{'id':row['id']})
        server.route('/api/disconnect',{});self.assertIsNone(server.STATE['location_id'])
    def test_same_ip_locations_isolated(self):
        a=self.save();b=self.save(name='Site B')
        server.STATE.update(demo=False,host=a['host'],identity='same',location_id=a['id'])
        server.save_profile_prices({'example':'A'});server.save_voucher_archive({'example':'A'})
        server.STATE['location_id']=b['id']
        self.assertEqual(server.profile_prices(),{});self.assertEqual(server.voucher_archive(),{})
        server.STATE['location_id']=a['id'];self.assertEqual(server.profile_prices(),{'example':'A'})
