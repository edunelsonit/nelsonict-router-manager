import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import backups,payments
from core import ValidationError
from pricing import validate_price
from templates import DEFAULT

class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def bundle(self):return {'format':'nelsonict-backup-1','files':{'templates/custom.json':{**DEFAULT,'id':'custom'}}}
    def test_roundtrip_and_recovery(self):
        b=self.bundle();backups.restore(self.root,b);self.assertEqual(backups.export(self.root)['files'],b['files'])
        b['files']['templates/custom.json']['brand']='Updated'
        result=backups.restore(self.root,b)
        old=json.loads((self.root/'recovery'/result['recovery']).read_text())
        self.assertEqual(old['files']['templates/custom.json']['brand'],DEFAULT['brand'])
    def test_paths_and_excluded_payment_files(self):
        for name in ('../secret.json','payments/'+('a'*64)+'.json','templates/../../x.json'):
            b=self.bundle();b['files']={name:{}}
            with self.assertRaises(ValidationError):backups.restore(self.root,b)
    def test_invalid_data_rejected_before_overwrite(self):
        b=self.bundle();backups.restore(self.root,b)
        bad=copy.deepcopy(b);bad['files']['templates/custom.json']['accent']='script'
        with self.assertRaises(ValidationError):backups.restore(self.root,bad)
        self.assertEqual(backups.export(self.root)['files'],b['files'])
    def test_rollback_on_write_failure(self):
        b=self.bundle();backups.restore(self.root,b)
        updated=copy.deepcopy(b);updated['files']['templates/custom.json']['brand']='Changed'
        updated['files']['templates/other.json']={**DEFAULT,'id':'other'}
        original=backups.write
        def fail(path,value):
            if path.name=='other.json':raise OSError('disk failure')
            original(path,value)
        with patch('backups.write',side_effect=fail):
            with self.assertRaises(OSError):backups.restore(self.root,updated)
        self.assertEqual(backups.export(self.root)['files'],b['files'])
    def test_secrets_excluded(self):
        (self.root/'payments').mkdir();(self.root/'payments'/'x.json').write_text('{"secret":"x"}')
        self.assertEqual(backups.export(self.root)['files'],{})

class PaymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.env=patch.dict('os.environ',{'PAYSTACK_SECRET_KEY':'sk_test_example'});self.env.start();self.addCleanup(self.env.stop)
        self.store=payments.Orders(self.tmp.name,'site','router')
    def create(self):
        def init(path,data):return {'reference':data['reference'],'authorization_url':'https://checkout.paystack.com/example'}
        with patch('payments.request',side_effect=init):return self.store.create('owner@example.com',validate_price('500','NGN'),{'profile':'daily'},'*1')
    def success(self,o):return {'status':'success','reference':o['reference'],'amount':50000,'currency':'NGN','domain':'test','customer':{'email':'owner@example.com'}}
    def test_verified_issue_once_and_frozen_price(self):
        o=self.create()
        with patch('payments.request',return_value=self.success(o)),patch('builtins.print'):
            issued=[]
            def issue(order):issued.append(order);return {'vouchers':[{'batch':'abc12345'}],'journal':'journal'}
            self.store.reconcile(issue);self.store.reconcile(issue)
            self.assertEqual(len(issued),1);self.assertEqual(issued[0]['price']['amount'],'500.00')
            self.assertEqual(self.store.store.read()[o['reference']]['state'],'issued')
    def test_mismatch_never_issues(self):
        for field,value in [('amount',1),('currency','USD'),('reference','other'),('domain','live')]:
            o=self.create();response=self.success(o);response[field]=value
            with patch('payments.request',return_value=response),patch('payments.mode') as unused:
                calls=[];self.store.reconcile(lambda order:calls.append(order))
                self.assertEqual(calls,[])
    def test_pending_or_network_failure_no_issue(self):
        o=self.create()
        with patch('payments.request',return_value={'status':'pending'}):self.store.reconcile(lambda o:self.fail('issued pending'))
        with patch('payments.request',side_effect=OSError()):self.store.reconcile(lambda o:self.fail('issued without verification'))
        self.assertEqual(self.store.store.read()[o['reference']]['state'],'pending')
    def test_uncertain_issue_not_retried(self):
        o=self.create();calls=[]
        def fail(order):calls.append(order);raise OSError('router disconnected')
        with patch('payments.request',return_value=self.success(o)):
            self.store.reconcile(fail);self.store.reconcile(fail)
        self.assertEqual(len(calls),1);self.assertEqual(self.store.store.read()[o['reference']]['state'],'needs-review')
    def test_initialization_intent_saved_and_no_key_persisted(self):
        with patch('payments.request',side_effect=OSError()):
            with self.assertRaises(OSError):self.store.create('a@example.com',validate_price('500','NGN'),{},'*1')
        self.assertEqual(len(self.store.store.read()),1)
        self.assertNotIn('sk_test_example',self.store.store.path.read_text())

class BusinessRouteTests(unittest.TestCase):
    def setUp(self):
        import server
        self.server=server;self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        p=patch.object(server,'DATA',Path(self.tmp.name));p.start();self.addCleanup(p.stop)
        e=patch.dict('os.environ',{'PAYSTACK_SECRET_KEY':'sk_test_example'});e.start();self.addCleanup(e.stop)
        server.route('/api/demo',{});server.STATE.update(demo=False,host='192.168.88.1',identity='lab')
        self.addCleanup(lambda:server.route('/api/disconnect',{}))
    def test_paid_route_to_archive_and_price_snapshot(self):
        s=self.server
        s.route('/api/profiles/price',{'id':'*1','name':'default','amount':'500','currency':'NGN'})
        def init(path,data):return {'reference':data['reference'],'authorization_url':'https://checkout.paystack.com/test'}
        with patch('payments.request',side_effect=init):
            order=s.route('/api/payments/create',{'profile':'default','server':'hotspot1','email':'a@example.com','duration':'1d','amount':'1'})
        s.route('/api/profiles/price',{'id':'*1','name':'default','amount':'900','currency':'NGN'})
        with patch('payments.request',return_value={'status':'success','reference':order['reference'],'amount':50000,'currency':'NGN','domain':'test','customer':{'email':'a@example.com'}}):
            result=s.route('/api/payments/check',{})
        self.assertEqual(result['orders'][0]['state'],'issued')
        rows=s.route('/api/vouchers/reprint',{'profile':'default'})['vouchers']
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['price_amount'],'500.00')
        self.assertIn('TEST PAYMENT',rows[0]['price_label'])
        self.assertEqual(rows[0]['payment_reference'],order['reference'])
    def test_restore_requires_disconnect(self):
        s=self.server;bundle=s.route('/api/backup/export',{})
        self.assertEqual(s.route('/api/backup/preview',{'backup':bundle})['files'],0)
        with self.assertRaises(ValidationError):s.route('/api/backup/restore',{'backup':bundle,'confirmation':'RESTORE'})
        s.route('/api/disconnect',{})
        self.assertEqual(s.route('/api/backup/restore',{'backup':bundle,'confirmation':'RESTORE'})['restored'],0)
