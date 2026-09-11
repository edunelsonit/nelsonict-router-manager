import tempfile,unittest
from unittest.mock import patch
import gateways,payments
from core import ValidationError
from pricing import validate_price
ENV={'FLUTTERWAVE_SECRET_KEY':'FLWSECK_TEST-example-X','FLUTTERWAVE_REDIRECT_URL':'https://example.com/receipt','MONNIFY_API_KEY':'api-example','MONNIFY_SECRET_KEY':'secret-example','MONNIFY_CONTRACT_CODE':'123','MONNIFY_REDIRECT_URL':'https://example.com/receipt','MONNIFY_MODE':'test'}
class GatewayTests(unittest.TestCase):
    def setUp(self):
        p=patch.dict('os.environ',ENV);p.start();self.addCleanup(p.stop)
    def order(self,p):return {'provider':p,'reference':'ns-example','price':{'amount':'500.00'},'email':'a@example.com','customer_name':'Customer','provider_reference':'MNFY|example'}
    def test_flutter_checkout(self):
        with patch('gateways.flutter',return_value={'link':'https://checkout.flutterwave.com/example'}) as req:
            gateways.initialize(self.order('flutterwave'));self.assertEqual(req.call_args.args[1]['amount'],'500.00');self.assertEqual(req.call_args.args[1]['tx_ref'],'ns-example')
    def test_flutter_verify(self):
        with patch('gateways.flutter',return_value={'status':'successful','tx_ref':'ns-example','amount':500,'currency':'NGN','customer':{'email':'a@example.com'}}):
            r=gateways.verify(self.order('flutterwave'));self.assertEqual(r['amount'],50000);self.assertEqual(r['status'],'success')
    def test_monnify_auth(self):
        with patch('gateways.http',side_effect=[{'requestSuccessful':True,'responseBody':{'accessToken':'token'}},{'requestSuccessful':True,'responseBody':{'ok':1}}]) as req:
            gateways.monnify('/api/test');self.assertEqual(req.call_args_list[0].args[0],'sandbox.monnify.com');self.assertEqual(req.call_args_list[1].args[2],'Bearer token')
    def test_monnify_checkout_verify(self):
        with patch('gateways.monnify',return_value={'paymentReference':'ns-example','transactionReference':'MNFY|example','checkoutUrl':'https://checkout.monnify.com/example'}):self.assertEqual(gateways.initialize(self.order('monnify'))['provider_reference'],'MNFY|example')
        with patch('gateways.monnify',return_value={'transactionReference':'MNFY|example','paymentReference':'ns-example','amountPaid':'500.00','currency':'NGN','paymentStatus':'PAID','customer':{'email':'a@example.com'}}) as req:
            self.assertEqual(gateways.verify(self.order('monnify'))['amount'],50000);self.assertIn('MNFY%7Cexample',req.call_args.args[0])
    def test_invalid_urls_modes_amounts(self):
        for p in ('monnify','flutterwave'):
            with self.assertRaises(ValidationError):gateways.checkout_url(p,'https://evil.example')
        for amount in ('NaN','1.005','-1'):
            with self.assertRaises(ValidationError):gateways.minor(amount)
        with patch.dict('os.environ',{'MONNIFY_MODE':'wrong'}):
            with self.assertRaises(ValidationError):gateways.mode('monnify')
    def test_both_providers_issue_once(self):
        for p in ('monnify','flutterwave'):
            with tempfile.TemporaryDirectory() as td:
                store=payments.Orders(td,'site','router')
                with patch('gateways.initialize',return_value={'checkout_url':'https://checkout.'+p+'.com/example'}):o=store.create('a@example.com',validate_price('500','NGN'),{},'*1',provider=p,customer_name='Name')
                issued=[]
                def issue(order):issued.append(order);return {'vouchers':[{'batch':'12345678'}],'journal':'j'}
                with patch('gateways.verify',return_value={'status':'success','reference':o['reference'],'amount':50000,'currency':'NGN','domain':'test','customer':{'email':'a@example.com'}}):store.reconcile(issue);store.reconcile(issue)
                self.assertEqual(len(issued),1);self.assertEqual(issued[0]['provider'],p);self.assertNotIn('secret-example',store.store.path.read_text())
    def test_key_change_blocks_verification(self):
        with tempfile.TemporaryDirectory() as td:
            store=payments.Orders(td,'site','router')
            with patch('gateways.initialize',return_value={'checkout_url':'https://checkout.flutterwave.com/example'}):store.create('a@example.com',validate_price('500','NGN'),{},'*1',provider='flutterwave')
            with patch.dict('os.environ',{'FLUTTERWAVE_SECRET_KEY':'FLWSECK_TEST-new-X'}),patch('gateways.verify') as verify:
                store.reconcile(lambda o:self.fail('issued'));verify.assert_not_called()
