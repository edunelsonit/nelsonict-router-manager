"""Transport gates, including a real local TLS smoke test when OpenSSL is present."""
import http.client
import json
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
import server

class MobileTransportTests(unittest.TestCase):
    def test_plaintext_lan_start_refused(self):
        r=subprocess.run([sys.executable,'server.py','--listen','192.168.1.10','--no-browser'],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0);self.assertIn('requires --tls-cert',r.stderr)
    def test_wildcard_and_public_start_refused(self):
        for host in ['0.0.0.0','8.8.8.8']:
            r=subprocess.run([sys.executable,'server.py','--listen',host,'--no-browser'],capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0);self.assertIn('explicit private',r.stderr)
    @unittest.skipUnless(shutil.which('openssl'),'OpenSSL unavailable; TLS smoke test requires it')
    def test_https_api_and_origin_checks(self):
        with tempfile.TemporaryDirectory() as td:
            cert=str(Path(td)/'cert.pem');key=str(Path(td)/'key.pem')
            subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',key,'-out',cert,'-days','1','-subj','/CN=127.0.0.1','-addext','subjectAltName=IP:127.0.0.1'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            endpoint=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,key)
            endpoint.socket=context.wrap_socket(endpoint.socket,server_side=True)
            endpoint.app_origin=f'https://127.0.0.1:{endpoint.server_port}'
            thread=threading.Thread(target=endpoint.serve_forever,daemon=True);thread.start()
            try:
                trust=ssl.create_default_context(cafile=cert)
                for origin,expected in [(endpoint.app_origin,200),('https://attacker.invalid',403)]:
                    conn=http.client.HTTPSConnection('127.0.0.1',endpoint.server_port,context=trust)
                    conn.request('POST','/api/demo','{}',{'Origin':origin,'X-App-Token':server.TOKEN,'Content-Type':'application/json'})
                    response=conn.getresponse();body=response.read();conn.close()
                    self.assertEqual(response.status,expected)
                    if expected==200:self.assertTrue(json.loads(body)['demo'])
            finally:endpoint.shutdown();endpoint.server_close();thread.join()

if __name__=='__main__':unittest.main()
