import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from sales import SalesDB,scope_key,voucher_key,validate_dump
from core import ValidationError
import backups,server

class SalesTests(unittest.TestCase):
    def setUp(self):
        self.db=SalesDB(':memory:');self.addCleanup(self.db.close)
        self.scope=scope_key('site A','router')
        self.v={'username':'ticket1','password':'secret','profile':'daily','base_profile':'daily','batch':'1234abcd','creation_state':'created','price_amount':'500.00','currency':'NGN'}
        self.archive={'1234abcd':{'batch':'1234abcd','created':1704067200,'vouchers':[self.v]}}
        self.id=voucher_key(self.scope,'1234abcd','ticket1')
    def sync(self,orders=None):self.db.sync(self.scope,self.archive,orders or {})
    def test_unsold_then_sold_once_and_void_audit(self):
        self.sync();self.assertEqual(self.db.inventory(self.scope,{})['counts']['unsold'],1)
        self.db.sell(self.scope,self.id)
        with self.assertRaises(ValidationError):self.db.sell(self.scope,self.id)
        self.assertEqual(self.db.inventory(self.scope,{})['counts']['sold'],1)
        self.db.unsell(self.scope,self.id)
        self.assertEqual(self.db.inventory(self.scope,{})['counts']['unsold'],1)
        self.assertIsNotNone(self.db.export()['events'][0]['voided_at'])
        self.db.sell(self.scope,self.id,'400.50','NGN');self.assertEqual(len(self.db.export()['events']),2)
    def test_profile_daily_monthly_offset_and_currencies(self):
        self.sync()
        with patch('sales.time.time',return_value=1704065400):self.db.sell(self.scope,self.id) # Dec31 23:30 UTC
        report=self.db.report(self.scope,{'from':'2024-01-01','to':'2024-01-01','utc_offset':60})
        self.assertEqual(report[0]['amount_minor'],50000);self.assertEqual(report[0]['period'],'2024-01-01')
        self.assertEqual(self.db.report(self.scope,{'from':'2024-01-01','to':'2024-01-01','utc_offset':0}),[])
        self.assertEqual(self.db.report(self.scope,{'period':'monthly','utc_offset':60})[0]['period'],'2024-01')
        other={**self.v,'username':'ticket2','currency':'USD','price_amount':'2.50'};self.archive['1234abcd']['vouchers'].append(other);self.sync()
        self.db.sell(self.scope,voucher_key(self.scope,'1234abcd','ticket2'))
        self.assertEqual({x['currency'] for x in self.db.report(self.scope,{})},{'NGN','USD'})
        self.assertEqual(self.db.report(self.scope,{'profile':'absent'}),[])
    def test_verified_payment_idempotent_and_locked(self):
        self.v.update(payment_reference='ns-ref',payment_domain='live')
        orders={'ns-ref':{'state':'issued','batch':'1234abcd','amount':50000,'currency':'NGN','domain':'live','provider':'monnify','issued_at':1704067200,'created':1704060000}}
        self.sync(orders);self.sync(orders)
        self.assertEqual(len(self.db.export()['events']),1)
        self.assertEqual(self.db.inventory(self.scope,{})['counts']['sold'],1)
        with self.assertRaises(ValidationError):self.db.unsell(self.scope,self.id)
        with self.assertRaises(ValidationError):self.db.sell(self.scope,self.id)
    def test_test_payments_and_pending_not_revenue(self):
        self.v.update(payment_reference='ns-ref',payment_domain='test')
        self.sync({'ns-ref':{'state':'issued','batch':'1234abcd','domain':'test'}})
        self.assertEqual(self.db.inventory(self.scope,{})['counts']['test'],1);self.assertEqual(self.db.report(self.scope,{}),[])
        with self.assertRaises(ValidationError):self.db.sell(self.scope,self.id)
        db=SalesDB(':memory:')
        try:
            self.v['payment_domain']='live';db.sync(self.scope,self.archive,{'ns-ref':{'state':'needs-review'}})
            self.assertEqual(db.inventory(self.scope,{})['counts']['payment-pending'],1);self.assertEqual(db.report(self.scope,{}),[])
        finally:db.close()
    def test_scope_and_price_snapshot(self):
        self.sync();self.v['price_amount']='900.00';self.sync();self.db.sell(self.scope,self.id)
        self.assertEqual(self.db.export()['events'][0]['amount'],50000)
        other=scope_key('site B','router')
        self.assertEqual(self.db.inventory(other,{})['total'],0)
        with self.assertRaises(ValidationError):self.db.unsell(other,self.id)
    def test_unpriced_requires_amount_partial_excluded(self):
        self.v.pop('price_amount');self.sync()
        with self.assertRaises(ValidationError):self.db.sell(self.scope,self.id)
        self.db.sell(self.scope,self.id,'0','NGN')
        self.v['creation_state']='uncertain';self.sync()
        self.assertEqual(self.db.inventory(self.scope,{})['total'],0)
        self.assertEqual(self.db.report(self.scope,{})[0]['sold'],1)
    def test_persistence_backup_and_validated_restore(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);db=SalesDB(root/'sales.sqlite3');db.sync(self.scope,self.archive,{});db.sell(self.scope,self.id);db.close()
            bundle=backups.export(root);self.assertIn('sales/ledger.json',bundle['files']);self.assertNotIn('secret',str(bundle))
            with tempfile.TemporaryDirectory() as other:
                backups.restore(Path(other),bundle);restored=SalesDB(Path(other)/'sales.sqlite3')
                self.assertEqual(restored.report(self.scope,{})[0]['amount_minor'],50000);restored.close()
            invalid=copy.deepcopy(bundle['files']['sales/ledger.json']);invalid['events'][0]['voucher_id']='unknown'
            with self.assertRaises(ValidationError):validate_dump(invalid)
    def test_invalid_filters_and_money(self):
        self.sync()
        for cfg in ({'period':'sql'},{'utc_offset':1000},{'from':'bad'},{'from':'2025-01-01','to':'2024-01-01'}):
            with self.assertRaises(ValidationError):self.db.report(self.scope,cfg)
        with self.assertRaises(ValidationError):self.db.sell(self.scope,self.id,'-5','NGN')
        self.assertEqual(self.db.inventory(self.scope,{'query':"' OR 1=1 --"})['total'],0)
    def test_inventory_pagination(self):
        self.archive['1234abcd']['vouchers']=[{**self.v,'username':f'user{i}'} for i in range(105)];self.sync()
        self.assertEqual(len(self.db.inventory(self.scope,{})['vouchers']),100)
        self.assertEqual(len(self.db.inventory(self.scope,{'page':1})['vouchers']),5)
    def test_demo_routes_cash_and_reset(self):
        server.route('/api/demo',{})
        try:
            server.route('/api/vouchers',{'profile':'default','server':'hotspot1','duration':'1d','count':1,'confirmation':'CREATE'})
            data=server.route('/api/sales/report',{});ident=data['vouchers'][0]['id']
            server.route('/api/sales/sell',{'id':ident,'amount':'500','currency':'NGN'})
            self.assertEqual(server.route('/api/sales/report',{})['reports'][0]['amount_minor'],50000)
            server.route('/api/sales/unsell',{'id':ident,'confirmation':'CORRECT'})
            self.assertEqual(server.route('/api/sales/report',{})['reports'],[])
            server.route('/api/demo',{});self.assertEqual(server.route('/api/sales/report',{})['total'],0)
        finally:server.route('/api/disconnect',{})
