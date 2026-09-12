import json,unittest
from unittest.mock import patch
import server,user_manager
from core import Router,ValidationError
class UserManagerTests(unittest.TestCase):
 def setUp(self):server.route('/api/demo',{});self.r=server.STATE['router']
 def preview(self,path,values,action='create',ident=''):
  return server.route('/api/user-manager/preview',{'path':path,'action':action,'id':ident,'values':values})
 def apply(self,p):return server.route('/api/user-manager/apply',{'review_id':p['id'],'backup':True,'confirmation':'APPLY USER MANAGER'})
 def test_setup_chain(self):
  self.apply(self.preview('user-manager',{'enabled':'yes','use-profiles':'yes'},'update'))
  self.apply(self.preview('user-manager/profile',{'name':'daily','validity':'1d','starts-when':'first-auth'}))
  self.apply(self.preview('user-manager/limitation',{'name':'speed','rate-limit-rx':'2M','rate-limit-tx':'5M'}))
  self.apply(self.preview('user-manager/profile-limitation',{'profile':'daily','limitation':'speed'}))
  self.apply(self.preview('user-manager/user',{'name':'tester','password':'private-password','group':'default'}))
  self.apply(self.preview('user-manager/user-profile',{'user':'tester','profile':'daily'}))
  self.assertEqual(self.r.data['user-manager/user-profile'][0]['profile'],'daily')
 def test_secrets_redacted_from_preview_list_and_journal(self):
  p=self.preview('user-manager/router',{'name':'nas','address':'127.0.0.1','shared-secret':'top-secret'})
  self.assertNotIn('top-secret',json.dumps(p));self.apply(p)
  self.assertNotIn('top-secret',json.dumps(server.route('/api/user-manager/list',{})))
  self.assertNotIn('top-secret',json.dumps(server.STATE['demo_journals'],default=lambda value:'<callback>'))
 def test_invalid_reference_and_path(self):
  with self.assertRaises(ValidationError):self.preview('user-manager/user-profile',{'user':'missing','profile':'missing'})
  with self.assertRaises(ValidationError):self.preview('system/script',{'name':'bad'})
  with self.assertRaises(ValidationError):self.preview('user-manager',{'enabled':'maybe'},'update')
 def test_stale_and_replay(self):
  p=self.preview('user-manager/profile',{'name':'daily'});self.r.data['user-manager'][0]['enabled']='yes'
  with self.assertRaises(ValidationError):self.apply(p)
  p=self.preview('user-manager/profile',{'name':'daily'});self.apply(p)
  with self.assertRaises(ValidationError):self.apply(p)
 def test_location_change_and_confirmation(self):
  p=self.preview('user-manager/profile',{'name':'daily'})
  with self.assertRaises(ValidationError):server.route('/api/user-manager/apply',{'review_id':p['id']})
  server.route('/api/demo',{})
  with self.assertRaises(ValidationError):self.apply(p)
 def test_update_delete_and_singleton(self):
  self.apply(self.preview('user-manager/user',{'name':'tester','password':'password'}));ident=self.r.data['user-manager/user'][0]['.id']
  self.apply(self.preview('user-manager/user',{'disabled':'yes'},'update',ident))
  self.assertEqual(self.r.data['user-manager/user'][0]['disabled'],'yes')
  self.apply(self.preview('user-manager/user',{},'delete',ident));self.assertFalse(self.r.data['user-manager/user'])
  with self.assertRaises(ValidationError):self.preview('user-manager',{},'delete')
 def test_uncertain_write_stops_and_consumes_plan(self):
  p=self.preview('user-manager/profile',{'name':'daily'});original=self.r.call
  def fail(path,method='GET',data=None):
   if method=='PUT':raise OSError('lost connection')
   return original(path,method,data)
  with patch.object(self.r,'call',side_effect=fail):
   with self.assertRaises(OSError):self.apply(p)
  self.assertIsNone(server.STATE.get('um_plan'))
  journal=list(server.STATE['demo_journals'].values())[-1];self.assertEqual(journal['entries'][0]['state'],'uncertain')
 def test_remote_requires_tls_for_public_address(self):
  for service in ('api','http'):
   with self.assertRaises(ValidationError):Router('8.8.8.8','owner','password',transport=service)
  self.assertEqual(Router('8.8.8.8','owner','password',transport='api-ssl').transport,'api-ssl')
