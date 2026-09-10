"""Paystack hosted checkout and verified, at-most-once voucher issuance."""
import hashlib,http.client,json,os,re,secrets,time
from decimal import Decimal
from urllib.parse import quote,urlsplit
from core import ValidationError
from pricing import PriceStore

def mode():
    key=os.environ.get('PAYSTACK_SECRET_KEY','')
    if key.startswith('sk_test_'):return 'test'
    if key.startswith('sk_live_'):return 'live'
    raise ValidationError('Set PAYSTACK_SECRET_KEY on the backend before accepting payments.')
def merchant():return hashlib.sha256(os.environ.get('PAYSTACK_SECRET_KEY','').encode()).hexdigest()
def request(path,data=None):
    mode();conn=http.client.HTTPSConnection('api.paystack.co',timeout=10)
    try:
        conn.request('POST' if data else 'GET',path,body=json.dumps(data) if data else None,headers={'Authorization':'Bearer '+os.environ['PAYSTACK_SECRET_KEY'],'Content-Type':'application/json'})
        response=conn.getresponse();raw=response.read(1048577)
        if response.status!=200 or len(raw)>1048576:raise ValidationError('Payment provider request failed. Check the order before retrying.')
        result=json.loads(raw)
        if result.get('status') is not True or not isinstance(result.get('data'),dict):raise ValidationError('Invalid payment provider response.')
        return result['data']
    finally:conn.close()

class Orders:
    def __init__(self,directory,scope,identity):self.store=PriceStore(directory,scope,identity)
    def create(self,email,price,config,profile_id,profile_snapshot=None):
        domain=mode()
        if not isinstance(email,str) or len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise ValidationError('Enter the customer email address.')
        if price.get('currency')!='NGN' or Decimal(price['amount'])<=0:raise ValidationError('Payments currently require a positive NGN profile price.')
        records=self.store.read()
        if sum(x['state'] in ('initializing','pending') for x in records.values())>=50:raise ValidationError('Resolve pending orders before adding more.')
        ref='ns-'+secrets.token_hex(16)
        order={'reference':ref,'email':email,'amount':int(Decimal(price['amount'])*100),'currency':'NGN','price':price,'config':config,'profile_id':profile_id,'profile_snapshot':profile_snapshot,'domain':domain,'merchant':merchant(),'state':'initializing','created':time.time()}
        records[ref]=order;self.store.write(records)
        result=request('/transaction/initialize',{'email':email,'amount':str(order['amount']),'currency':'NGN','reference':ref})
        url=result.get('authorization_url','');parsed=urlsplit(url)
        if result.get('reference')!=ref or parsed.scheme!='https' or parsed.hostname!='checkout.paystack.com':raise ValidationError('Invalid hosted checkout response.')
        order.update(state='pending',checkout_url=url);self.store.write(records)
        return order
    def reconcile(self,issue):
        records=self.store.read()
        checked=0
        for ref,order in sorted(records.items(),key=lambda pair:pair[1].get('checked',0)):
            if order['state'] not in ('pending','initializing') or order['merchant']!=merchant():continue
            if checked>=3:break
            checked+=1;order['checked']=time.time();self.store.write(records)
            try:
                result=request('/transaction/verify/'+quote(ref,safe=''))
                if result.get('status')!='success':continue
                if result.get('reference')!=ref or type(result.get('amount')) is not int or result['amount']!=order['amount'] or result.get('currency')!=order['currency'] or result.get('domain')!=order['domain'] or str(result.get('customer',{}).get('email','')).casefold()!=order['email'].casefold():
                    order['state']='verification-mismatch';self.store.write(records);continue
                # Intent saved before any router write; never automatically repeat issuance.
                order['state']='issuing';self.store.write(records)
                try:
                    result=issue(order)
                    order.update(state='issued',batch=result['vouchers'][0]['batch'],journal=result['journal'])
                except Exception:order['state']='needs-review'
                self.store.write(records)
            except Exception:continue  # Network failure leaves pending; no issue before verification.
        return records
