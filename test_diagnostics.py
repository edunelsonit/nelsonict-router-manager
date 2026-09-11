import copy,json,os,unittest
from unittest.mock import patch
import diagnostics,llm_review,server
from core import ValidationError
from expiry import encode,decode,ENGINE_NAME,SCHEDULER_SOURCE

class DiagnosticTests(unittest.TestCase):
    def setUp(self):server.route('/api/demo',{});self.r=server.STATE['router']
    def collect(self):return server.route('/api/diagnostics/collect',{})
    def apply(self,r,ids,**extra):return server.route('/api/diagnostics/apply',{'review_id':r['id'],'fix_ids':ids,'backup':True,'confirmation':'APPLY FIXES',**extra})
    def ticket(self,comment,**extra):return self.r.call('ip/hotspot/user','PUT',{'name':'1234567890','password':'1234567890','profile':'default','comment':comment,'uptime':'0s','disabled':'no',**extra})
    def policy(self,**extra):return {'mode':'connected','duration':3600,'offset':60,'cutoff':86340,'fixed':0,'fallback':36600,'first':0,'due':0,'batch':'abcd1234',**extra}
    def test_projection_omits_credentials_comments_and_scripts(self):
        self.ticket('secret-comment');self.r.data['system/scheduler'].append({'name':'custom','on-event':'secret-key'})
        report=self.collect();payload=json.dumps(diagnostics.ai_payload(report))
        for secret in ('1234567890','secret-comment','secret-key','password'):self.assertNotIn(secret,payload)
        self.assertIn('1234567890',json.dumps(report['tickets']))
    def test_rsc_import_is_projection_not_execution(self):
        r=diagnostics.import_file('/ip hotspot user\nadd name=12345678 password=secret comment=hidden profile=default\n/system script\nadd source="evil command"','rsc')
        text=json.dumps(r)
        for secret in ('12345678','secret','hidden','evil command'):self.assertNotIn(secret,text)
        self.assertEqual(r['configuration']['ip/hotspot/user'][0]['profile'],'default')
    def test_canonical_comments_preserve_policy(self):
        p=self.policy(first=1704067200,due=1704070800);self.ticket(' '+encode(p)+' ',**{'limit-uptime':'1h'})
        r=self.collect();fix=next(f for f in r['fixes'] if f['kind']=='ticket-metadata')
        self.apply(r,[fix['id']]);self.assertEqual(decode(self.r.call('ip/hotspot/user')[0]['comment']),p)
    def test_expired_disable_and_session_cookie_cleanup(self):
        user=self.ticket(encode(self.policy()),uptime='2h',**{'limit-uptime':'1h'})
        for menu in ('ip/hotspot/active','ip/hotspot/cookie'):self.r.call(menu,'PUT',{'user':user['name']})
        r=self.collect();fix=next(f for f in r['fixes'] if f['kind']=='expired-ticket')
        self.apply(r,[fix['id']]);self.assertEqual(self.r.call('ip/hotspot/user')[0]['disabled'],'yes')
        self.assertEqual(self.r.call('ip/hotspot/active'),[]);self.assertEqual(self.r.call('ip/hotspot/cookie'),[])
    def test_missing_activation_not_guessed(self):
        self.ticket(encode(self.policy(mode='elapsed')),uptime='1h',**{'limit-uptime':'30m'})
        r=self.collect();self.assertFalse(any(f['path']=='ip/hotspot/user' for f in r['fixes']))
        self.assertTrue(any('withheld' in f for f in r['findings']))
    def test_damaged_policy_requires_manual_review(self):
        self.ticket('ns2,broken');r=self.collect();self.assertEqual(r['fixes'],[])
        self.assertTrue(any('damaged' in f for f in r['findings']))
    def test_stale_review_and_replay(self):
        self.ticket(encode(self.policy()),**{'limit-uptime':'30m'})
        r=self.collect();ids=[f['id'] for f in r['fixes']]
        self.r.data['ip/hotspot/user'][0]['profile']='changed'
        with self.assertRaises(ValidationError):self.apply(r,ids)
        r=self.collect();ids=[f['id'] for f in r['fixes']];self.apply(r,ids)
        with self.assertRaises(ValidationError):self.apply(r,ids)
    def test_legacy_note_preview_and_protected_comments(self):
        u=self.ticket('ordinary note')
        r=server.route('/api/diagnostics/comments',{'ids':[u['.id']],'comment':'Paid cash'})
        self.apply(r,[f['id'] for f in r['fixes']],comments=True)
        self.assertEqual(self.r.call('ip/hotspot/user')[0]['comment'],'Paid cash')
        self.r.data['ip/hotspot/user'][0]['comment']='ns-batch-abcd1234'
        with self.assertRaises(ValidationError):diagnostics.comment_plan(self.r,[u['.id']],'overwrite')
    def test_wrong_location_clears_plan(self):
        self.ticket(encode(self.policy()),**{'limit-uptime':'30m'});r=self.collect()
        server.route('/api/demo',{})
        with self.assertRaises(ValidationError):self.apply(r,[f['id'] for f in r['fixes']])
    def test_custom_scheduler_not_overwritten(self):
        self.r.data['system/scheduler'].append({'.id':'*E','name':ENGINE_NAME,'comment':'foreign','on-event':'foreign script','disabled':'yes'})
        self.assertFalse(any(f['kind']=='expiry-engine' for f in self.collect()['fixes']))
    def test_owned_scheduler_has_no_false_script_drift(self):
        self.r.data['system/scheduler'].append({'.id':'*E','name':ENGINE_NAME,'comment':'Nelsonict expiry v2','on-event':SCHEDULER_SOURCE,'interval':'30s','disabled':'false','policy':'read,write'})
        self.assertFalse(any(f['kind']=='expiry-engine' for f in self.collect()['fixes']))
    def test_ai_no_key_and_sharing_guard(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'','OPENAI_MODEL':''}):
            with self.assertRaises(ValidationError):llm_review.review({})
        with self.assertRaises(ValidationError):server.route('/api/diagnostics/ai',{'kind':'json','text':'{}'})
    def test_llm_contract_and_unsupported_fix_rejected(self):
        def reply(ids):return json.dumps({'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'summary':'Review','findings':[],'recommended_fix_ids':ids})}]}]}).encode()
        with patch.dict(os.environ,{'OPENAI_API_KEY':'secret','OPENAI_MODEL':'configured-model'}),patch('llm_review.http.client.HTTPSConnection') as conn:
            response=conn.return_value.getresponse.return_value;response.status=200;response.read.return_value=reply(['allowed'])
            self.assertEqual(llm_review.review({'available_fixes':[{'id':'allowed'}]})['recommended_fix_ids'],['allowed'])
            body=json.loads(conn.return_value.request.call_args.kwargs['body']);self.assertFalse(body['store']);self.assertNotIn('secret',json.dumps(body))
            response.read.return_value=reply(['arbitrary-command'])
            with self.assertRaises(ValidationError):llm_review.review({'available_fixes':[]})
