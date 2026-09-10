"""Local HTTP integration tests; no network router access."""
import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
import server

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True)
        cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.thread.join()
    def call(self,path,data=None,token=True,origin=True):
        conn=http.client.HTTPConnection('127.0.0.1',self.http.server_port)
        headers={'Content-Type':'application/json'}
        if token:headers['X-App-Token']=server.TOKEN
        if origin:headers['Origin']=f'http://127.0.0.1:{self.http.server_port}'
        conn.request('POST',path,json.dumps(data or {}),headers)
        response=conn.getresponse();body=json.loads(response.read());conn.close()
        return response.status,body
    def test_missing_token_rejected(self):
        self.assertEqual(self.call('/api/demo',token=False)[0],403)
    def test_missing_origin_rejected(self):
        self.assertEqual(self.call('/api/demo',origin=False)[0],403)
    def test_complete_demo_workflow(self):
        self.assertEqual(self.call('/api/demo')[0],200)
        status,p=self.call('/api/plan',{'scenario':'existing','name':'http-test'})
        self.assertEqual(status,200)
        self.assertEqual(self.call('/api/apply',{'plan_id':p['id'],'backup':True,'confirmation':'APPLY'})[0],200)
        status,batch=self.call('/api/vouchers',{'profile':'ns-http-test-users','server':'hotspot1','count':3,'duration':'1d','confirmation':'CREATE'})
        self.assertEqual(status,200);self.assertEqual(len(batch['vouchers']),3)
        _,current=self.call('/api/status')
        self.assertTrue(all('password' not in u for u in current['users']))
        self.assertEqual(self.call('/api/disable',{'id':current['users'][0]['.id'],'confirmation':'DISABLE'})[0],200)
        self.assertEqual(self.call('/api/rollback',{'id':batch['journal'],'confirmation':'ROLLBACK'})[0],200)
        self.assertEqual(len(self.call('/api/status')[1]['users']),0)
        self.assertEqual(self.call('/api/disconnect')[0],200)
        self.assertEqual(self.call('/api/status')[0],400)

if __name__=='__main__':unittest.main()
