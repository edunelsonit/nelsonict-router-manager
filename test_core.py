import copy
import unittest
from unittest.mock import patch
import core
import server

class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.router=server.DemoRouter()
        self.state=core.snapshot(self.router)
        self.cfg={'scenario':'hotspot','name':'test','lan':'ether5','wan':'ether1','subnet':'10.50.0.0/24','upload':5,'download':10}
    def test_occupied_port_refused(self):
        self.cfg['lan']='bridge'
        with self.assertRaises(core.ValidationError):core.build_plan(self.state,self.cfg)
    def test_bridge_member_refused(self):
        self.state['interface/bridge/port']=[{'interface':'ether5','bridge':'bridge'}]
        with self.assertRaises(core.ValidationError):core.build_plan(self.state,self.cfg)
    def test_overlapping_subnet_refused(self):
        self.cfg['subnet']='192.168.88.0/24'
        with self.assertRaises(core.ValidationError):core.build_plan(self.state,self.cfg)
    def test_fasttrack_refused(self):
        self.state['ip/firewall/filter'].append({'action':'fasttrack-connection'})
        with self.assertRaises(core.ValidationError):core.build_plan(self.state,self.cfg)
    def test_missing_firewall_refused(self):
        self.state['ip/firewall/filter']=[]
        with self.assertRaises(core.ValidationError):core.build_plan(self.state,self.cfg)
    def test_ipv6_enabled_refused(self):
        self.router.data['ipv6/settings']['disable-ipv6']='false'
        with self.assertRaises(core.ValidationError):server.new_network_checks(self.router,self.cfg)
    def test_hotspot_device_mode_refused(self):
        self.router.data['system/device-mode']['hotspot']='no'
        with self.assertRaises(core.ValidationError):server.new_network_checks(self.router,self.cfg)
    def test_name_injection_refused(self):
        self.cfg['name']='foo; /system reset-configuration'
        with self.assertRaises(core.ValidationError):core.build_plan(self.state,self.cfg)
    def test_plan_and_rollback_preserve_existing_config(self):
        plan=core.build_plan(self.state,self.cfg)
        journal={'entries':[],'save':lambda:None}
        core.execute(self.router,plan['operations'],journal)
        self.assertGreater(len(self.router.data['ip/address']),1)
        core.rollback(self.router,journal['entries'],journal['save'])
        self.assertEqual(core.digest(core.snapshot(self.router)),core.digest(self.state))
    def test_unknown_write_outcome_is_not_retried(self):
        journal={'entries':[],'save':lambda:None}
        with patch.object(self.router,'call',side_effect=TimeoutError) as call:
            with self.assertRaises(TimeoutError):core.execute(self.router,[{'path':'ip/pool','values':{'name':'test'},'label':'pool'}],journal)
            self.assertEqual(call.call_count,1)
        self.assertEqual(journal['entries'][0]['state'],'uncertain')
    def test_modified_object_blocks_rollback(self):
        journal={'entries':[],'save':lambda:None}
        core.execute(self.router,[{'path':'ip/pool','values':{'name':'test'},'label':'pool'}],journal)
        self.router.data['ip/pool'][0]['name']='changed'
        with self.assertRaises(core.ValidationError):core.rollback(self.router,journal['entries'],journal['save'])
    def test_counters_do_not_invalidate_plan(self):
        other=copy.deepcopy(self.state);other['system/resource'][0]['uptime']='4h'
        self.assertEqual(core.digest(self.state),core.digest(other))
    def test_configuration_changes_invalidate_plan(self):
        other=copy.deepcopy(self.state);other['ip/firewall/filter'][0]['action']='accept'
        self.assertNotEqual(core.digest(self.state),core.digest(other))
    def test_vouchers_have_online_allowance_and_unique_pins(self):
        ops,rows=core.voucher_operations('ns-site-users','hotspot1',100,'28d',[])
        self.assertEqual(len(set(v['pin'] for v in rows)),100)
        self.assertTrue(all(x['values']['limit-uptime']=='28d' for x in ops))
        self.assertTrue(all(x['values']['name']==x['values']['password'] for x in ops))
    def test_router_transport_rejects_invalid_targets(self):
        for host in ['127.0.0.1','169.254.169.254','0.0.0.0','example.org']:
            with self.assertRaises((ValueError,core.ValidationError)):core.Router(host,'a','b')
    def test_replay_blocked(self):
        server.route('/api/demo',{})
        plan=server.route('/api/plan',{'scenario':'existing','name':'test'})
        body={'plan_id':plan['id'],'confirmation':'APPLY','backup':True}
        server.route('/api/apply',body)
        with self.assertRaises(core.ValidationError):server.route('/api/apply',body)
    def test_v6_refused(self):
        self.router.data['system/resource'][0]['version']='6.49.17'
        with self.assertRaises(core.ValidationError):core.snapshot(self.router)

if __name__=='__main__':unittest.main()
