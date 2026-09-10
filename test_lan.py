import io
import unittest
from unittest.mock import patch
import api_transport as api
from core import Router, ValidationError
import server
from templates import DEFAULT
from portal_install import prepare, deploy

class Wire:
    def __init__(self,data=b''):self.data=io.BytesIO(data);self.sent=b''
    def recv(self,n):return self.data.read(min(n,3))
    def sendall(self,data):self.sent+=data
    def close(self):pass

def reply(*sentences):
    w=Wire()
    for s in sentences:api.sentence(w,s)
    return w.sent

class TransportTests(unittest.TestCase):
    def test_lengths(self):
        for n in (0,127,128,16383,16384,2097151,2097152,268435455,268435456,4294967295):
            self.assertEqual(api.read_length(Wire(api.encode_length(n))),n)
    def test_fragmented_unicode_and_equal(self):
        rows,_=api.response(Wire(reply(['!re','=name=Nélson=ICT'],['!done'])))
        self.assertEqual(rows,[{'name':'Nélson=ICT'}])
    def test_trap_sanitized(self):
        with self.assertRaises(api.APIError) as e:api.response(Wire(reply(['!trap','=message=secret'],['!done'])))
        self.assertNotIn('secret',str(e.exception))
    def test_empty(self):self.assertEqual(api.response(Wire(reply(['!empty'],['!done']))),([],{}))
    def test_truncated_and_oversized(self):
        for raw in (b'\x05hi',api.encode_length(api.MAX_REPLY+1),b'\xf1'):
            with self.assertRaises(api.APIError):api.response(Wire(raw))
    def test_modern_login_before_command(self):
        w=Wire(reply(['!done'],['!re','=name=router'],['!done']))
        with patch('api_transport.socket.create_connection',return_value=w):
            self.assertEqual(Router('192.168.88.1','owner','secret',transport='api').call('system/identity'),[{'name':'router'}])
        self.assertEqual(w.sent,reply(['/login','=name=owner','=password=secret'],['/system/identity/print']))
    def test_tls_pin_before_login(self):
        w=Wire();w.getpeercert=lambda **k:b'certificate'
        r=Router('192.168.88.1','owner','secret',transport='api-ssl',fingerprint='0'*64)
        with patch('api_transport.socket.create_connection',return_value=w),patch.object(r,'tls_context') as ctx:
            ctx.return_value.wrap_socket.return_value=w
            with self.assertRaises(ValidationError):r.call('system/identity')
        self.assertEqual(w.sent,b'')
    def test_native_resource_operations(self):
        r=Router('192.168.88.1','owner','secret',transport='api')
        with patch('api_transport.command',return_value=([],{'ret':'*A'})) as cmd:
            self.assertEqual(r.call('ip/hotspot/user','PUT',{'name':'x'})['.id'],'*A')
            r.call('ip/hotspot/user/%2AA','PATCH',{'disabled':True})
            self.assertEqual(cmd.call_args.args[1],['/ip/hotspot/user/set','=.id=*A','=disabled=yes'])
            r.call('file/print','POST',{'.proplist':['name','contents'],'.query':['.id=*A']})
            self.assertEqual(cmd.call_args.args[1],['/file/print','=.proplist=name,contents','?.id=*A'])
    def test_private_only_plaintext_and_defaults(self):
        for t,p in [('http',80),('https',443),('api',8728),('api-ssl',8729)]:
            self.assertEqual(Router('192.168.88.1','u','p',transport=t).port,p)
        for t in ('http','api'):
            with self.assertRaises(ValidationError):Router('8.8.8.8','u','p',transport=t)
        with self.assertRaises(ValidationError):Router('192.168.88.1','u','p',port=0)
    def test_http_request(self):
        with patch('core.http.client.HTTPConnection') as conn:
            conn.return_value.getresponse.return_value.status=200
            conn.return_value.getresponse.return_value.read.return_value=b'[]'
            Router('192.168.88.1','u','p',transport='http').call('file')
            self.assertEqual(conn.return_value.request.call_args.args[:2],('GET','/rest/file?.proplist=.id,name,type,size'))

class DirectInstallTests(unittest.TestCase):
    def setUp(self):
        server.route('/api/demo',{});self.r=server.STATE['router']
    def plan(self):return server.route('/api/portal/prepare',{'server':'hotspot1','template':DEFAULT})
    def install(self,p):return server.route('/api/portal/deploy',{'plan_id':p['id'],'confirmation':'INSTALL PORTAL'})
    def test_upload_verify_activate_restore(self):
        before=self.r.call('file');p=self.plan();result=self.install(p)
        self.assertEqual(self.r.call('ip/hotspot/profile')[0]['html-directory'],p['directory'])
        server.route('/api/rollback',{'id':result['journal'],'confirmation':'ROLLBACK'})
        self.assertEqual(self.r.call('ip/hotspot/profile')[0]['html-directory'],'hotspot')
        self.assertTrue(all(x in self.r.call('file') for x in before))
        self.assertTrue(any(x['name']==p['directory']+'/portal.css' for x in self.r.call('file')))
        with self.assertRaises(ValidationError):self.install(p)
    def test_persistent_destination(self):
        self.r.data['file'].append({'.id':'*FLASH','name':'flash','type':'directory'})
        self.assertTrue(self.plan()['directory'].startswith('flash/'))
    def test_occupied_destination(self):
        with self.assertRaises(ValidationError):prepare(self.r,'hotspot1',DEFAULT,'hotspot')
    def test_changed_source_blocks_writes(self):
        p=self.plan();self.r.data['file'][-1]['size']='999'
        with patch.object(self.r,'call',wraps=self.r.call) as c:
            with self.assertRaises(ValidationError):self.install(p)
            self.assertTrue(all(len(x.args)<2 or x.args[1]=='GET' for x in c.call_args_list))
    def test_copy_failure_not_retried_or_activated(self):
        p=self.plan();original=self.r.call
        def fail(path,method='GET',data=None):
            if path=='file/copy':raise ValidationError('unsupported')
            return original(path,method,data)
        with patch.object(self.r,'call',side_effect=fail) as c:
            with self.assertRaises(ValidationError):self.install(p)
            self.assertEqual(sum(x.args[0]=='file/copy' for x in c.call_args_list),1)
        self.assertEqual(original('ip/hotspot/profile')[0]['html-directory'],'hotspot')
    def test_readback_failure_blocks_activation(self):
        p=self.plan();original=self.r.call
        def fail(path,method='GET',data=None):
            if path=='file/print':return []
            return original(path,method,data)
        with patch.object(self.r,'call',side_effect=fail):
            with self.assertRaises(ValidationError):self.install(p)
        self.assertEqual(original('ip/hotspot/profile')[0]['html-directory'],'hotspot')
    def test_profile_drift_during_upload(self):
        p=self.plan();original=self.r.call
        def drift(path,method='GET',data=None):
            result=original(path,method,data)
            if path=='file/print':self.r.data['ip/hotspot/profile'][0]['html-directory']='other'
            return result
        with patch.object(self.r,'call',side_effect=drift):
            with self.assertRaises(ValidationError):self.install(p)
        self.assertEqual(original('ip/hotspot/profile')[0]['html-directory'],'other')
