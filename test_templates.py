import base64
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from core import ValidationError,voucher_operations
import server
from templates import *

class TemplateTests(unittest.TestCase):
    def test_template_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            store=TemplateStore(td);saved=store.save({**DEFAULT,'name':'School ticket','mode':'credentials'})
            self.assertNotEqual(saved['id'],'default');self.assertEqual(len(store.list()),2)
            store.save({**saved,'heading':'Updated'});self.assertEqual(len(store.list()),2)
    def test_html_escaped_and_unsafe_color_rejected(self):
        html=print_html({**DEFAULT,'brand':'<script>alert(1)</script>'})
        self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>',html)
        with self.assertRaises(ValidationError):validate_template({**DEFAULT,'accent':'red; background:url(https://evil)'})
    def test_template_directive_and_path_rejected(self):
        for change in [{'brand':'$(if logged-in)'},{'id':'../outside'},{'columns':20}]:
            with self.assertRaises(ValidationError):validate_template({**DEFAULT,**change})
    def test_pin_layout_cannot_hide_password(self):
        with self.assertRaises(ValidationError):print_html(DEFAULT,[{'username':'one','password':'two'}])
    def test_pair_layout_prints_both(self):
        html=print_html({**DEFAULT,'mode':'credentials'},[{'username':'NS-SAMPLE','password':'realPassword'}])
        self.assertIn('NS-SAMPLE',html);self.assertIn('realPassword',html)
    def test_pair_generator_applies_configuration(self):
        ops,rows=voucher_operations('profile','hotspot',100,'1d',[],{'credential_mode':'credentials','username_prefix':'ABC','username_length':6,'password_length':16})
        self.assertEqual(len({x['username'] for x in rows}),100)
        for op,row in zip(ops,rows):
            self.assertTrue(row['username'].startswith('ABC'));self.assertEqual(len(row['username']),9)
            self.assertEqual(len(row['password']),16);self.assertNotEqual(row['username'],row['password'])
            self.assertEqual(row['password'],op['values']['password']);self.assertIsNone(row['pin'])
    def test_pin_generator_applies_length(self):
        _,rows=voucher_operations('profile','hotspot',20,'1d',[],{'pin_length':12})
        self.assertTrue(all(len(x['pin'])==12 and x['username']==x['password']==x['pin'] for x in rows))
    def test_generation_settings_reject_injection(self):
        with self.assertRaises(ValidationError):credential_settings({'username_prefix':'bad;command'})
    def test_generated_package_is_overlay_and_has_instructions(self):
        package=portal_package(DEFAULT)
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(package['base64']))) as z:
            self.assertIn('nelsonict-pin/login.html',z.namelist())
            self.assertIn('nelsonict-pin/flogin.html',z.namelist())
            self.assertNotIn('nelsonict-pin/md5.js',z.namelist())
            self.assertIn('KEEP the original md5.js',z.read('INSTALL.txt').decode())
    def test_portal_no_recursive_template_interpolation(self):
        page=portal_files({**DEFAULT,'brand':'FIELDS HEADING'})['login.html']
        self.assertIn('<header>FIELDS HEADING</header>',page)
        self.assertIn('$(chap-id)',page);self.assertIn('$(chap-challenge)',page)

class PortalInstallTests(unittest.TestCase):
    def setUp(self):server.route('/api/demo',{})
    def test_install_and_restore_preserve_original(self):
        plan=server.route('/api/portal/plan',{'server':'hotspot1','directory':'nelsonict-pin','mode':'pin'})
        self.assertEqual(plan['before'],'hotspot')
        result=server.route('/api/portal/install',{'plan_id':plan['id'],'confirmation':'INSTALL PORTAL'})
        self.assertEqual(server.STATE['router'].call('ip/hotspot/profile')[0]['html-directory'],'nelsonict-pin')
        server.route('/api/rollback',{'id':result['journal'],'confirmation':'ROLLBACK'})
        self.assertEqual(server.STATE['router'].call('ip/hotspot/profile')[0]['html-directory'],'hotspot')
    def test_missing_support_file_refused(self):
        r=server.STATE['router'];r.data['file']=[x for x in r.data['file'] if x['name']!='nelsonict-pin/md5.js']
        with self.assertRaisesRegex(ValidationError,'md5.js'):portal_plan(r,'hotspot1','nelsonict-pin','pin')
    def test_shared_profile_disclosed(self):
        r=server.STATE['router'];r.data['ip/hotspot'].append({'name':'hotel2','profile':'default'})
        self.assertEqual(portal_plan(r,'hotspot1','nelsonict-pin','pin')['affected_servers'],['hotspot1','hotel2'])
    def test_changed_plan_refused(self):
        plan=server.route('/api/portal/plan',{'server':'hotspot1','directory':'nelsonict-pin','mode':'pin'})
        server.STATE['router'].data['ip/hotspot/profile'][0]['html-directory']='other'
        with self.assertRaises(ValidationError):server.route('/api/portal/install',{'plan_id':plan['id'],'confirmation':'INSTALL PORTAL'})
    def test_plaintext_auth_only_refused(self):
        r=server.STATE['router'];r.data['ip/hotspot/profile'][0]['login-by']='http-pap,cookie'
        with self.assertRaises(ValidationError):portal_plan(r,'hotspot1','nelsonict-pin','pin')
    def test_api_template_save_does_not_store_credentials(self):
        with tempfile.TemporaryDirectory() as td,patch.object(server,'DATA',Path(td)):
            result=server.route('/api/templates/save',{'template':{**DEFAULT,'password':'SECRET'}})
            raw=next((Path(td)/'templates').glob('*.json')).read_text()
            self.assertNotIn('SECRET',raw)

@unittest.skipUnless(shutil.which('node'),'Node unavailable; generated portal JS execution test skipped')
class PortalJavaScriptTests(unittest.TestCase):
    def run_page(self,mode,chap,protocol):
        page=portal_files({**DEFAULT,'mode':mode})['login.html']
        script=re.findall(r'<script>(.*?)</script>',page,re.S)[0]
        a,b=script.split('$(if chap-id)');yes,no=b.split('$(else)');no,tail=no.split('$(endif)')
        script=a+(yes if chap else no)+tail
        script=script.replace('$(chap-id)',r'\001').replace('$(chap-challenge)',r'\002')
        js='''const vm=require('node:vm');let fn,submitted=false,hashed=null;
const form={elements:{username:{},password:{}},submit(){submitted=true;}};
const nodes={'ticket-form':{addEventListener(k,f){fn=f;}},'router-login':form,'ticket-pin':{value:'1234567890'},'ticket-user':{value:'alice'},'ticket-pass':{value:'SecretPassword'},'login-error':{textContent:''}};
const context={document:{getElementById:id=>nodes[id]},location:{protocol:PROTOCOL,host:'router.local'},hexMD5(s){hashed=s;return 'HASH';}};
vm.runInNewContext(SOURCE,context);fn({preventDefault(){}});
console.log(JSON.stringify({submitted,username:form.elements.username.value,password:form.elements.password.value,action:form.action,hashed,error:nodes['login-error'].textContent}));'''
        js=js.replace('PROTOCOL',json.dumps(protocol)).replace('SOURCE',json.dumps(script))
        return json.loads(subprocess.check_output(['node','-e',js],text=True))
    def test_pin_chap_maps_pin_to_both_inputs(self):
        r=self.run_page('pin',True,'http:');self.assertTrue(r['submitted']);self.assertEqual(r['username'],'1234567890');self.assertEqual(r['password'],'HASH');self.assertEqual(r['hashed'],'\x011234567890\x02')
    def test_separate_credentials_chap(self):
        r=self.run_page('credentials',True,'http:');self.assertEqual(r['username'],'alice');self.assertEqual(r['hashed'],'\x01SecretPassword\x02')
    def test_https_password_does_not_downgrade(self):
        r=self.run_page('credentials',False,'https:');self.assertTrue(r['submitted']);self.assertEqual(r['action'],'https://router.local/login');self.assertEqual(r['password'],'SecretPassword')
    def test_plain_http_pap_is_blocked(self):
        r=self.run_page('pin',False,'http:');self.assertFalse(r['submitted']);self.assertIn('Secure login',r['error'])

if __name__=='__main__':unittest.main()
