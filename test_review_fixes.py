import copy,json,tempfile,threading,unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
import server,expiry,diagnostics,backups
from core import ValidationError
from sales import SalesDB,scope_key

def ts(s):return int(datetime.fromisoformat(s).timestamp())
class ReviewFixes(unittest.TestCase):
 def setUp(self):server.route('/api/demo',{})
 def policy(self):
  p=expiry.policy_from_form({'expiry_mode':'startup','utc_offset':60,'fallback_time':'10:10'},ts('2026-09-10T12:00:00+01:00'))
  p.update(first=ts('2026-09-10T12:00:00+01:00'),batch='1234abcd');return p
 def voucher(self):return server.route('/api/vouchers',{'profile':'default','server':'hotspot1','count':1,'duration':'1d','confirmation':'CREATE'})
 def test_midnight_fallback_shortens_after_boot(self):
  p=self.policy();p['due']=expiry.deadline(p,ts('2026-09-11T00:01:00+01:00'),p['first']-3600)
  boot=ts('2026-09-11T08:00:00+01:00')
  self.assertEqual(expiry.deadline(p,boot+60,boot),boot+600)
  self.assertEqual(expiry.deadline(p,boot+1800,boot),boot+600)
 def test_no_revival_or_extension(self):
  p=self.policy();p['due']=ts('2026-09-11T10:10:00+01:00');due=p['due']
  self.assertEqual(expiry.deadline(p,due+3600,due+3000),due)
  p['due']=ts('2026-09-11T08:10:00+01:00')
  self.assertEqual(expiry.deadline(p,p['due']-30,p['due']-60),p['due'])
 def test_known_engine_upgrade_updates_hooks_only(self):
  r=server.STATE['router'];r.call('system/scheduler','PUT',{'name':expiry.ENGINE_NAME,'on-event':expiry.LEGACY_SCHEDULER_SOURCE,'interval':'30s','disabled':'no'})
  r.call('ip/hotspot/user/profile','PUT',{'name':'legacy','on-login':expiry.LEGACY_HOOK_SOURCE})
  r.call('ip/hotspot/user/profile','PUT',{'name':'custom','on-login':'custom script'})
  result=server.route('/api/expiry/install',{'confirmation':'INSTALL'});self.assertEqual(result['count'],2)
  self.assertEqual(r.call('system/scheduler')[0]['on-event'],expiry.SCHEDULER_SOURCE)
  self.assertEqual(next(p for p in r.call('ip/hotspot/user/profile') if p['name']=='legacy')['on-login'],expiry.HOOK_SOURCE)
  self.assertEqual(next(p for p in r.call('ip/hotspot/user/profile') if p['name']=='custom')['on-login'],'custom script')
  self.assertEqual(expiry.engine_operations(r),[])
 def test_revoked_not_printable_sellable_but_sale_retained(self):
  v=self.voucher();report=server.route('/api/sales/report',{});ident=report['vouchers'][0]['id']
  server.route('/api/sales/sell',{'id':ident,'amount':'500','currency':'NGN'})
  server.route('/api/rollback',{'id':v['journal'],'confirmation':'ROLLBACK'})
  self.assertEqual(server.route('/api/vouchers/reprint',{'batch':v['vouchers'][0]['batch']})['total'],0)
  with self.assertRaises(ValidationError):server.route('/api/vouchers/validate-print',{'tickets':v['vouchers']})
  report=server.route('/api/sales/report',{});self.assertEqual(report['total'],0);self.assertEqual(report['reports'][0]['amount_minor'],50000)
  with self.assertRaises(ValidationError):server.route('/api/sales/sell',{'id':ident,'amount':'500','currency':'NGN'})
 def test_old_rollback_journal_reconciles_archive(self):
  v=self.voucher();journal=server.STATE['demo_journals'][v['journal']]
  from core import rollback
  rollback(server.STATE['router'],journal['entries'],journal['save'])
  self.assertEqual(server.route('/api/vouchers/reprint',{'batch':v['vouchers'][0]['batch']})['total'],0)
 def test_failed_rollback_quarantines_before_mutation(self):
  v=self.voucher();r=server.STATE['router'];original=r.call
  def fail(path,method='GET',data=None):
   if method=='DELETE':raise OSError('lost reply')
   return original(path,method,data)
  with patch.object(r,'call',side_effect=fail):
   with self.assertRaises(OSError):server.route('/api/rollback',{'id':v['journal'],'confirmation':'ROLLBACK'})
  self.assertEqual(server.route('/api/vouchers/reprint',{'batch':v['vouchers'][0]['batch']})['total'],0)
 def test_revoked_online_sale_still_indexed(self):
  from sales import SalesDB
  db=SalesDB(':memory:');self.addCleanup(db.close);v=self.voucher();archive=server.voucher_archive();batch=v['vouchers'][0]['batch']
  archive[batch]['vouchers'][0].update(lifecycle='revoked',payment_reference='order',payment_domain='live')
  db.sync(scope_key('a','b'),archive,{'order':{'state':'issued','batch':batch,'amount':50000,'currency':'NGN','created':1700000000}})
  self.assertEqual(db.inventory(scope_key('a','b'),{})['total'],0)
  self.assertEqual(db.report(scope_key('a','b'),{})[0]['amount_minor'],50000)
 def test_diagnostic_roundtrip_preserves_policy_and_flags(self):
  raw={'ip/hotspot/user':[{'name':'secret-pin','password':'secret','comment':expiry.encode(self.policy())}], 'system/scheduler':[{'on-event':'secret-script'}], 'ip/hotspot/user/profile':[{'on-login':'hook','on-logout':''}]}
  projected=diagnostics.project(raw)
  result=diagnostics.import_file(json.dumps({'schema_version':1,'configuration':projected}),'json')
  self.assertEqual(projected,result['configuration'])
  for word in ('secret-pin','secret-script','password'):self.assertNotIn(word,json.dumps(result))
 def test_rsc_retains_only_structured_policy(self):
  result=diagnostics.import_file('/ip hotspot user\nadd name=secret password=secret comment="'+expiry.encode(self.policy())+'"\n/system scheduler\nadd name=engine on-event="secret script"','rsc')
  self.assertEqual(result['configuration']['ip/hotspot/user'][0]['expiry_metadata'],self.policy())
  self.assertTrue(result['configuration']['system/scheduler'][0]['script_present'])
  self.assertNotIn('secret',json.dumps(result))
 def test_invalid_projected_metadata_and_flags_rejected(self):
  for raw in ({'ip/hotspot/user':[{'expiry_metadata':{'secret':'bad'}}]}, {'system/scheduler':[{'script_present':'secret'}]}):
   with self.assertRaises(ValidationError):diagnostics.import_file(json.dumps({'configuration':raw}),'json')
  with self.assertRaises(ValidationError):diagnostics.import_file('{"schema_version":2,"configuration":{}}','json')

class CloudConcurrency(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  p=patch.object(server,'DATA',Path(self.tmp.name));p.start();self.addCleanup(p.stop)
  p=patch.dict('os.environ',{'PAYSTACK_SECRET_KEY':'sk_test_example'});p.start();self.addCleanup(p.stop)
  server.route('/api/demo',{});self.r=server.STATE['router'];server.STATE.update(demo=False,host='192.168.88.1',identity='lab')
  self.addCleanup(lambda:server.route('/api/disconnect',{}))
 def background(self,fn):
  results=[]
  def run():
   try:results.append(fn())
   except Exception as exc:results.append(exc)
  thread=threading.Thread(target=run,daemon=True);thread.start();return thread,results
 def create(self):
  server.route('/api/profiles/price',{'id':'*1','name':'default','amount':'500','currency':'NGN'})
  with patch('payments.request',side_effect=lambda path,data:{'reference':data['reference'],'authorization_url':'https://checkout.paystack.com/test'}):
   return server.route('/api/payments/create',{'profile':'default','server':'hotspot1','email':'a@example.com','duration':'1d'})
 def test_slow_ai_does_not_block_status_or_disconnect(self):
  review=server.route('/api/diagnostics/collect',{});entered=threading.Event();release=threading.Event()
  def slow(payload):entered.set();release.wait(3);return {'summary':'done','findings':[],'recommended_fix_ids':[]}
  with patch('llm_review.review',side_effect=slow):
   task,result=self.background(lambda:server.route('/api/diagnostics/ai',{'review_id':review['id'],'share':True}))
   try:
    self.assertTrue(entered.wait(1));control,out=self.background(lambda:server.route('/api/status',{}));control.join(1);self.assertFalse(control.is_alive());self.assertIsInstance(out[0],dict)
    control,out=self.background(lambda:server.route('/api/disconnect',{}));control.join(1);self.assertFalse(control.is_alive())
   finally:release.set();task.join(2)
  self.assertIsInstance(result[0],ValidationError)
 def test_slow_payment_verification_switch_defers_then_issues_once(self):
  order=self.create();store=server.payment_store();entered=threading.Event();release=threading.Event()
  response={'status':'success','reference':order['reference'],'amount':50000,'currency':'NGN','domain':'test','customer':{'email':'a@example.com'}}
  def slow(path):entered.set();release.wait(3);return response
  with patch('payments.request',side_effect=slow):
   task,result=self.background(lambda:server.route('/api/payments/check',{}))
   try:
    self.assertTrue(entered.wait(1));control,out=self.background(lambda:server.route('/api/disconnect',{}));control.join(1);self.assertFalse(control.is_alive())
   finally:release.set();task.join(2)
  self.assertEqual(store.store.read()[order['reference']]['state'],'pending');self.assertEqual(self.r.call('ip/hotspot/user'),[])
  server.STATE.update(router=self.r,demo=False,host='192.168.88.1',identity='lab')
  with patch('payments.request',return_value=response):server.route('/api/payments/check',{});server.route('/api/payments/check',{})
  self.assertEqual(len(self.r.call('ip/hotspot/user')),1);self.assertEqual(store.store.read()[order['reference']]['state'],'issued')
 def test_slow_checkout_does_not_block_owner(self):
  server.route('/api/profiles/price',{'id':'*1','name':'default','amount':'500','currency':'NGN'});store=server.payment_store();entered=threading.Event();release=threading.Event()
  def slow(path,data):entered.set();release.wait(3);return {'reference':data['reference'],'authorization_url':'https://checkout.paystack.com/test'}
  with patch('payments.request',side_effect=slow):
   task,result=self.background(lambda:server.route('/api/payments/create',{'profile':'default','server':'hotspot1','email':'a@example.com'}))
   try:
    self.assertTrue(entered.wait(1));control,out=self.background(lambda:server.route('/api/disconnect',{}));control.join(1);self.assertFalse(control.is_alive())
   finally:release.set();task.join(2)
  self.assertIsInstance(result[0],ValidationError);self.assertEqual(next(iter(store.store.read().values()))['state'],'pending')

class HTTPCloudLockTest(unittest.TestCase):
 def test_http_handler_does_not_wrap_cloud_wait_in_lock(self):
  from http.client import HTTPConnection
  from http.server import ThreadingHTTPServer
  server.route('/api/demo',{});review=server.route('/api/diagnostics/collect',{})
  http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);http.daemon_threads=True
  serving=threading.Thread(target=http.serve_forever,daemon=True);serving.start()
  entered=threading.Event();release=threading.Event();results=[]
  def call(path,data):
   conn=HTTPConnection('127.0.0.1',http.server_port,timeout=1)
   try:
    conn.request('POST',path,json.dumps(data),{'Content-Type':'application/json','X-App-Token':server.TOKEN,'Origin':f'http://127.0.0.1:{http.server_port}'})
    response=conn.getresponse();response.read();return response.status
   finally:conn.close()
  def slow(payload):entered.set();release.wait(2);return {'summary':'ok','findings':[],'recommended_fix_ids':[]}
  with patch('llm_review.review',side_effect=slow):
   worker=threading.Thread(target=lambda:results.append(call('/api/diagnostics/ai',{'review_id':review['id'],'share':True})),daemon=True);worker.start()
   try:self.assertTrue(entered.wait(1));self.assertEqual(call('/api/status',{}),200)
   finally:release.set();worker.join(2);http.shutdown();http.server_close();serving.join(2)
  self.assertEqual(results,[200])
