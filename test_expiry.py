import copy
from datetime import datetime,timezone
import unittest
from unittest.mock import patch
from expiry import *
import server

def ts(value):return int(datetime.fromisoformat(value).timestamp())

class ExpiryPolicyTests(unittest.TestCase):
    def policy(self,mode='elapsed',first='2026-09-10T12:00:00+01:00'):
        p=policy_from_form({'expiry_mode':mode,'duration':'1d','utc_offset':60,'closing_time':'18:00','fallback_time':'10:10'},ts('2026-09-10T00:00:00+01:00'))
        p.update(first=ts(first) if first else 0,batch='1234abcd')
        return p
    def test_elapsed_counts_offline_time(self):
        p=self.policy();self.assertEqual(deadline(p,p['first'],p['first']-3600),p['first']+86400)
    def test_business_closing_same_day(self):
        p=self.policy('business');self.assertEqual(deadline(p,p['first'],p['first']-1),ts('2026-09-10T18:00:00+01:00'))
    def test_login_after_closing(self):
        p=self.policy('business','2026-09-10T19:00:00+01:00');self.assertEqual(deadline(p,p['first'],p['first']-1),ts('2026-09-11T18:00:00+01:00'))
    def test_startup_same_day_restart_does_not_expire(self):
        p=self.policy('startup');self.assertIsNone(deadline(p,p['first']+3600,p['first']+1800))
    def test_next_day_boot_gets_ten_minutes(self):
        p=self.policy('startup');boot=ts('2026-09-11T08:00:00+01:00')
        self.assertEqual(deadline(p,boot+60,boot),boot+600)
    def test_delayed_ntp_uses_boot_not_sync_time(self):
        p=self.policy('startup');boot=ts('2026-09-11T08:00:00+01:00')
        self.assertEqual(deadline(p,boot+1800,boot),boot+600)
    def test_stable_power_fallback(self):
        p=self.policy('startup');now=ts('2026-09-11T09:00:00+01:00')
        self.assertEqual(deadline(p,now,p['first']-3600),ts('2026-09-11T10:10:00+01:00'))
    def test_unused_survives_next_day(self):
        p=self.policy('startup',None);self.assertIsNone(deadline(p,ts('2026-09-12T00:00:00Z'),ts('2026-09-11T23:59:00Z')))
    def test_persisted_deadline_never_extended_by_reboot(self):
        p=self.policy('startup');p['due']=ts('2026-09-11T08:10:00+01:00')
        self.assertEqual(deadline(p,p['due']+86400,p['due']+86300),p['due'])
    def test_fixed_expires_unused_ticket(self):
        now=ts('2026-09-10T00:00:00Z');p=policy_from_form({'expiry_mode':'fixed','fixed_at':'2026-09-11T00:00:00+01:00'},now)
        self.assertEqual(deadline(p,now,now-60),ts('2026-09-10T23:00:00Z'))
    def test_fixed_without_zone_refused(self):
        with self.assertRaises(ValidationError):policy_from_form({'expiry_mode':'fixed','fixed_at':'2026-09-11T00:00:00'},0)
    def test_serialized_policy_roundtrip(self):
        p=self.policy();self.assertEqual(decode(encode(p)),p)
    def test_damaged_policy_reported(self):
        u={'name':'alice','comment':'ns2,garbage'}
        self.assertEqual(describe_user(u,[],100,10,True)['expiry_state'],'invalid-policy')
    def test_unsynchronized_clock_unknown_not_expired(self):
        p=self.policy();u={'name':'alice','comment':encode(p)}
        status=describe_user(u,[{'user':'alice','uptime':'10m'}],p['first']+172800,p['first'],False)
        self.assertEqual(status['expiry_state'],'clock-unverified');self.assertFalse(status['overdue_active'])
    def test_expired_active_highlight(self):
        p=self.policy();u={'name':'alice','comment':encode(p)}
        self.assertTrue(describe_user(u,[{'user':'alice','uptime':'10m'}],p['first']+90000,p['first'],True)['overdue_active'])
    def test_old_first_login_not_invented(self):
        u={'name':'old','uptime':'1d','limit-uptime':'2d'}
        r=describe_user(u,[{'user':'old','uptime':'1h'}],200000,100000,True)
        self.assertIsNone(r['first_login']);self.assertEqual(r['current_session_started'],196400)
    def test_connected_old_exhausted_ticket(self):
        u={'name':'old','uptime':'1d','limit-uptime':'1d'}
        self.assertTrue(describe_user(u,[{'user':'old','uptime':'1h'}],200000,100000,False)['overdue_active'])
    def test_duration_formats(self):
        self.assertEqual(ros_seconds('1w2d03:04:05'),788645)
        self.assertEqual(ros_seconds('1w2d3h4m5s'),788645)
        with self.assertRaises(ValidationError):ros_seconds('garbage')

class ExpiryIntegrationTests(unittest.TestCase):
    def setUp(self):server.route('/api/demo',{})
    def test_install_create_tracked_and_protect_engine(self):
        plan=server.route('/api/expiry/preview',{});self.assertEqual(len(plan['operations']),1)
        installed=server.route('/api/expiry/install',{'confirmation':'INSTALL'})
        body={'profile':'default','server':'hotspot1','count':2,'duration':'1d','expiry_mode':'elapsed','confirmation':'CREATE'}
        batch=server.route('/api/vouchers',body)
        status=server.route('/api/status',{})
        self.assertTrue(all(x['expiry_state']=='unused' for x in status['users']))
        self.assertTrue(all(x['first_login'] is None for x in status['users']))
        self.assertEqual(status['users'][0]['limit-uptime'],'0s')
        profile=server.STATE['router'].call('ip/hotspot/user/profile')[-1]
        self.assertEqual(profile['on-login'],HOOK_SOURCE)
        with self.assertRaises(ValidationError):server.route('/api/rollback',{'id':installed['journal'],'confirmation':'ROLLBACK'})
        self.assertEqual(server.route('/api/expiry/install',{'confirmation':'INSTALL'})['count'],0)
    def test_missing_engine_blocks_tracked_creation(self):
        with self.assertRaises(ValidationError):server.route('/api/vouchers',{'profile':'default','server':'hotspot1','count':2,'expiry_mode':'elapsed','confirmation':'CREATE'})
    def test_dashboard_counts_and_disable_any_local_user(self):
        status=server.route('/api/demo/activity',{})
        self.assertEqual(status['counts']['connected_users'],2);self.assertEqual(status['counts']['overdue_active'],1)
        expired=next(x for x in status['users'] if x['overdue_active'])
        server.route('/api/ticket/action',{'id':expired['.id'],'action':'disable','confirmation':'DISABLE'})
        self.assertEqual(server.route('/api/status',{})['counts']['overdue_active'],0)
        with self.assertRaises(ValidationError):server.route('/api/ticket/action',{'id':expired['.id'],'action':'enable','confirmation':'ENABLE'})
    def test_disconnect_preserves_ticket(self):
        status=server.route('/api/demo/activity',{});u=status['users'][0]
        server.route('/api/ticket/action',{'id':u['.id'],'action':'disconnect','confirmation':'DISCONNECT'})
        self.assertEqual(len(server.route('/api/status',{})['users']),3)
        self.assertEqual(server.route('/api/status',{})['counts']['connected_users'],1)
    def test_valid_ticket_can_be_reenabled(self):
        u=server.route('/api/demo/activity',{})['users'][0]
        for a in ['disable','enable']:server.route('/api/ticket/action',{'id':u['.id'],'action':a,'confirmation':a.upper()})
        row=server.STATE['router'].call('ip/hotspot/user')[0];self.assertEqual(row['disabled'],'no')
    def test_existing_custom_hook_preserved(self):
        with self.assertRaises(ValidationError):expiry_profile({'name':'custom','on-login':':log info "custom";'},'1234abcd')
    def test_engine_drift_refused(self):
        r=server.STATE['router'];server.route('/api/expiry/install',{'confirmation':'INSTALL'})
        r.data['system/scheduler'][0]['on-event']='other code'
        with self.assertRaises(ValidationError):engine_operations(r)

if __name__=='__main__':unittest.main()
