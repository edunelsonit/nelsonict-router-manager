import tempfile
import unittest
import server
from core import ValidationError
from pricing import PriceStore,validate_price
from templates import DEFAULT,print_html

class PriceTests(unittest.TestCase):
    def setUp(self):server.route('/api/demo',{})
    def save(self,amount='500',currency='NGN'):
        return server.route('/api/profiles/price',{'id':'*1','name':'default','amount':amount,'currency':currency})
    def batch(self):
        return server.route('/api/vouchers',{'profile':'default','server':'hotspot1','count':1,'duration':'1d','confirmation':'CREATE'})['vouchers']
    def test_price_flows_to_ticket_and_is_frozen(self):
        self.save();batch=self.batch();self.save('1000')
        html=print_html({**DEFAULT,'price':'wrong fallback'},batch)
        self.assertIn('NGN 500.00',html);self.assertNotIn('wrong fallback',html)
        self.assertEqual(self.batch()[0]['price_amount'],'1000.00')
        self.assertEqual(batch[0]['base_profile'],'default')
    def test_tracked_profile_keeps_base_price(self):
        self.save('2000')
        server.route('/api/expiry/install',{'confirmation':'INSTALL'})
        rows=server.route('/api/vouchers',{'profile':'default','server':'hotspot1','count':1,'duration':'1w','expiry_mode':'elapsed','confirmation':'CREATE'})['vouchers']
        self.assertNotEqual(rows[0]['profile'],'default')
        self.assertEqual(rows[0]['base_profile'],'default')
        self.assertEqual(rows[0]['price_label'],'NGN 2,000.00')
    def test_free_and_remove(self):
        self.save('0');self.assertIn('NGN 0.00',print_html(DEFAULT,self.batch()))
        self.save('');self.assertNotIn('price_label',self.batch()[0])
        self.assertIn('fallback',print_html({**DEFAULT,'price':'fallback'},self.batch()))
    def test_invalid_prices(self):
        for value in ('-1','1.001','NaN','1e3','1000000000','<script>',None):
            with self.assertRaises(ValidationError):self.save(value)
        with self.assertRaises(ValidationError):self.save('500','<x>')
    def test_stale_profile_rejected(self):
        with self.assertRaises(ValidationError):server.route('/api/profiles/price',{'id':'*2','name':'default','amount':'5','currency':'NGN'})
    def test_store_persists_and_isolates_routers(self):
        with tempfile.TemporaryDirectory() as directory:
            store=PriceStore(directory,'192.168.1.1','site A');store.write({'profile':validate_price('500','NGN')})
            self.assertEqual(PriceStore(directory,'192.168.1.1','site A').read()['profile']['amount'],'500.00')
            self.assertEqual(PriceStore(directory,'192.168.1.2','site A').read(),{})
            self.assertEqual(PriceStore(directory,'192.168.1.1','site B').read(),{})
    def test_demo_reset_and_list(self):
        self.save();self.assertEqual(server.route('/api/profiles/prices',{})['profiles'][0]['price']['label'],'NGN 500.00')
        server.route('/api/demo',{});self.assertIsNone(server.route('/api/profiles/prices',{})['profiles'][0]['price'])
    def test_print_escapes_price(self):
        rows=[{'username':'12345678','password':'12345678','price_label':'<script>bad</script>'}]
        self.assertIn('&lt;script&gt;',print_html(DEFAULT,rows))
