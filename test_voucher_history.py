import tempfile
import unittest
from unittest.mock import patch
import server
from core import ValidationError
from voucher_history import VoucherHistory

class HistoryTests(unittest.TestCase):
    def setUp(self):server.route('/api/demo',{})
    def generate(self,count=2,**extra):
        return server.route('/api/vouchers',{'profile':'default','server':'hotspot1','count':count,'duration':'1d','confirmation':'CREATE',**extra})['vouchers']
    def test_batch_profile_filter_and_original_credentials(self):
        a=self.generate(2,credential_mode='credentials');b=self.generate(1)
        rows=server.route('/api/vouchers/reprint',{'batch':a[0]['batch']})['vouchers']
        self.assertEqual([x['password'] for x in rows],[x['password'] for x in a])
        self.assertEqual(server.route('/api/vouchers/reprint',{'profile':'default'})['total'],3)
        self.assertEqual(server.route('/api/vouchers/reprint',{'batch':b[0]['batch'],'profile':'missing'})['total'],0)
        self.assertNotIn('password',str(server.route('/api/vouchers/history',{})))
    def test_pagination(self):
        self.generate(100);self.generate(2)
        first=server.route('/api/vouchers/reprint',{'profile':'default'})
        second=server.route('/api/vouchers/reprint',{'profile':'default','offset':100})
        self.assertEqual(len(first['vouchers']),100);self.assertEqual(len(second['vouchers']),2)
        self.assertFalse({x['username'] for x in first['vouchers']} & {x['username'] for x in second['vouchers']})
    def test_partial_batch_only_confirmed_printable(self):
        r=server.STATE['router'];original=r.call;n=0
        def fail(path,method='GET',data=None):
            nonlocal n
            if path=='ip/hotspot/user' and method=='PUT':
                n+=1
                if n==2:raise ValidationError('interrupted')
            return original(path,method,data)
        with patch.object(r,'call',side_effect=fail):
            with self.assertRaises(ValidationError):self.generate(3)
        self.assertEqual(server.route('/api/vouchers/reprint',{'profile':'default'})['total'],1)
        self.assertTrue(server.route('/api/vouchers/history',{})['batches'][0]['incomplete'])
    def test_archive_failure_prevents_router_write(self):
        r=server.STATE['router']
        with patch('server.save_voucher_archive',side_effect=OSError('full')):
            with self.assertRaises(OSError):self.generate()
        self.assertEqual(r.call('ip/hotspot/user'),[])
    def test_persistence_and_router_isolation(self):
        self.generate()
        with tempfile.TemporaryDirectory() as td:
            store=VoucherHistory(td,'192.168.1.1','a');store.write(server.voucher_archive())
            self.assertEqual(len(VoucherHistory(td,'192.168.1.1','a').read()),1)
            self.assertEqual(VoucherHistory(td,'192.168.1.2','a').read(),{})
    def test_recover_legacy_batch_without_invented_prices(self):
        rows=self.generate();server.STATE['demo_vouchers']={}
        result=server.route('/api/vouchers/import',{})
        self.assertEqual(result['added'],2)
        recovered=server.route('/api/vouchers/reprint',{'batch':rows[0]['batch']})['vouchers']
        self.assertEqual(recovered[0]['password'],rows[0]['password']);self.assertEqual(recovered[0]['price_label'],'')
        self.assertEqual(server.route('/api/vouchers/import',{})['added'],0)
    def test_missing_password_not_guessed(self):
        self.generate();server.STATE['demo_vouchers']={}
        for row in server.STATE['router'].data['ip/hotspot/user']:row.pop('password')
        self.assertEqual(server.route('/api/vouchers/import',{})['added'],0)
    def test_invalid_selection_and_demo_reset(self):
        self.generate()
        with self.assertRaises(ValidationError):server.route('/api/vouchers/reprint',{})
        with self.assertRaises(ValidationError):server.route('/api/vouchers/reprint',{'profile':'default','offset':-1})
        server.route('/api/demo',{});self.assertEqual(server.route('/api/vouchers/history',{})['batches'],[])
