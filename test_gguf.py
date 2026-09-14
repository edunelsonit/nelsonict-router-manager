"""Mocked local GGUF protocol and fail-closed analysis tests."""
import json,os,unittest
from unittest.mock import patch
import llm_review
from core import ValidationError

class GGUFTests(unittest.TestCase):
    def setUp(self):
        env=patch.dict(os.environ,{},clear=True);env.start();self.addCleanup(env.stop)
        p=patch('llm_review.http.client.HTTPConnection');self.conn=p.start();self.addCleanup(p.stop)
        p=patch('llm_review.http.client.HTTPSConnection');self.cloud=p.start();self.addCleanup(p.stop)
        self.response=self.conn.return_value.getresponse.return_value;self.response.status=200
        self.reply()
    def reply(self,ids=None,finish='stop'):
        value={'summary':'Local review','findings':[],'recommended_fix_ids':ids or []}
        self.response.read.return_value=json.dumps({'choices':[{'finish_reason':finish,'message':{'content':json.dumps(value)}}]}).encode()
    def test_default_local_request_and_validation(self):
        self.reply(['allowed'])
        result=llm_review.review({'available_fixes':[{'id':'allowed'}]})
        self.assertEqual(result['recommended_fix_ids'],['allowed'])
        self.conn.assert_called_once_with('127.0.0.1',8080,timeout=120)
        call=self.conn.return_value.request.call_args
        self.assertEqual(call.args,('POST','/v1/chat/completions'))
        body=json.loads(call.kwargs['body'])
        self.assertEqual(body['model'],'nelsonict-gguf')
        self.assertEqual(body['response_format']['schema'],llm_review.SCHEMA)
        self.assertFalse(body['stream'])
        self.assertNotIn('Authorization',call.kwargs['headers'])
        self.cloud.assert_not_called()
        self.conn.return_value.close.assert_called_once()
    def test_unknown_fix_rejected(self):
        self.reply(['invented'])
        with self.assertRaises(ValidationError):llm_review.review({})
    def test_truncated_and_malformed_outputs_rejected(self):
        self.reply(finish='length')
        with self.assertRaises(ValidationError):llm_review.review({})
        for raw in (b'not json',b'[]',b'{"choices":[]}',b'{"choices":[null]}'):
            self.response.read.return_value=raw
            with self.assertRaises(ValidationError):llm_review.review({})
        self.reply()
        self.assertEqual(llm_review.review({})['summary'],'Local review')
    def test_failure_no_cloud_fallback(self):
        for status in (302,400,503):
            self.response.status=status
            with self.assertRaises(ValidationError):llm_review.review({})
        self.response.status=200
        self.conn.return_value.request.side_effect=TimeoutError()
        with self.assertRaises(ValidationError):llm_review.review({})
        self.cloud.assert_not_called()
        self.assertFalse(llm_review.LOCAL_LOCK.locked())
    def test_configuration_and_input_limits(self):
        for port in ('0','65536','http://other','bad'):
            with patch.dict(os.environ,{'NELSONICT_GGUF_PORT':port}),self.assertRaises(ValidationError):llm_review.review({})
        with self.assertRaises(ValidationError):llm_review.review({'text':'x'*300001})
        with self.assertRaises(ValidationError):llm_review.review({},provider='unknown')
        self.conn.assert_not_called()
    def test_large_response_and_invalid_contract(self):
        for raw in (b'x'*1048577,json.dumps({'choices':[{'finish_reason':'stop','message':{'content':'{"summary":"x"}'}}]}).encode()):
            self.response.read.return_value=raw
            with self.assertRaises(ValidationError):llm_review.review({})
    def test_busy_local_server_rejected(self):
        llm_review.LOCAL_LOCK.acquire()
        try:
            with self.assertRaises(ValidationError):llm_review.review({})
            self.conn.assert_not_called()
        finally:llm_review.LOCAL_LOCK.release()
    def test_explicit_cloud_still_requires_credentials(self):
        with self.assertRaises(ValidationError):llm_review.review({},provider='openai')
        self.conn.assert_not_called()
        self.cloud.assert_not_called()
    def test_alias_and_port_override(self):
        with patch.dict(os.environ,{'NELSONICT_GGUF_MODEL':'my-model','NELSONICT_GGUF_PORT':'8090'}):
            llm_review.review({})
        self.conn.assert_called_once_with('127.0.0.1',8090,timeout=120)
        self.assertEqual(json.loads(self.conn.return_value.request.call_args.kwargs['body'])['model'],'my-model')
