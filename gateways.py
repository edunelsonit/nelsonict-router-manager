"""Hosted checkout adapters for Flutterwave v3 and Monnify. NGN only."""
import base64,hashlib,http.client,json,os
from decimal import Decimal
from urllib.parse import quote,urlsplit
from core import ValidationError
PROVIDERS=('paystack','monnify','flutterwave')
def required(name):
    value=os.environ.get(name,'').strip()
    if not value:raise ValidationError('Set '+name+' on the backend.')
    return value

def mode(provider):
    if provider=='flutterwave':
        key=required('FLUTTERWAVE_SECRET_KEY')
        if key.startswith('FLWSECK_TEST-'):return 'test'
        if key.startswith('FLWSECK-'):return 'live'
        raise ValidationError('Use a Flutterwave v3 secret key.')
    if provider=='monnify':
        for name in ('MONNIFY_API_KEY','MONNIFY_SECRET_KEY','MONNIFY_CONTRACT_CODE'):required(name)
        value=os.environ.get('MONNIFY_MODE','test')
        if value in ('test','live'):return value
        raise ValidationError('MONNIFY_MODE must be test or live.')
    raise ValidationError('Unsupported payment provider.')

def merchant(provider):
    names=('FLUTTERWAVE_SECRET_KEY',) if provider=='flutterwave' else ('MONNIFY_API_KEY','MONNIFY_SECRET_KEY','MONNIFY_CONTRACT_CODE')
    return hashlib.sha256(json.dumps([provider,mode(provider)]+[required(n) for n in names]).encode()).hexdigest()

def http(host,path,authorization,data=None):
    conn=http.client.HTTPSConnection(host,timeout=10)
    try:
        conn.request('POST' if data is not None else 'GET',path,body=json.dumps(data) if data is not None else None,headers={'Authorization':authorization,'Content-Type':'application/json'})
        response=conn.getresponse();raw=response.read(1048577)
        if not 200<=response.status<300 or len(raw)>1048576:raise ValidationError('Provider request failed. Check the order before retrying.')
        result=json.loads(raw)
        if not isinstance(result,dict):raise ValidationError('Invalid provider response.')
        return result
    finally:conn.close()

def flutter(path,data=None):
    result=http('api.flutterwave.com',path,'Bearer '+required('FLUTTERWAVE_SECRET_KEY'),data)
    if result.get('status')!='success' or not isinstance(result.get('data'),dict):raise ValidationError('Flutterwave rejected the request.')
    return result['data']

def monnify(path,data=None):
    host='sandbox.monnify.com' if mode('monnify')=='test' else 'api.monnify.com'
    auth=base64.b64encode((required('MONNIFY_API_KEY')+':'+required('MONNIFY_SECRET_KEY')).encode()).decode()
    result=http(host,'/api/v1/auth/login','Basic '+auth,{})
    token=result.get('responseBody',{}).get('accessToken')
    if result.get('requestSuccessful') is not True or not isinstance(token,str) or not token:raise ValidationError('Monnify authentication failed.')
    result=http(host,path,'Bearer '+token,data)
    if result.get('requestSuccessful') is not True or not isinstance(result.get('responseBody'),dict):raise ValidationError('Monnify rejected the request.')
    return result['responseBody']

def redirect(provider):
    name=provider.upper()+'_REDIRECT_URL';url=required(name);p=urlsplit(url)
    if p.scheme!='https' or not p.hostname or p.username or p.password:raise ValidationError(name+' must be an HTTPS receipt page URL.')
    return url

def checkout_url(provider,url):
    hosts={'flutterwave':{'checkout.flutterwave.com'},'monnify':{'checkout.monnify.com','sdk.monnify.com','sandbox.sdk.monnify.com'}}
    p=urlsplit(url)
    if p.scheme!='https' or p.hostname not in hosts[provider] or p.username or p.password or p.port not in (None,443):raise ValidationError('Unexpected provider checkout URL.')
    return url

def initialize(order):
    provider=order['provider'];amount=order['price']['amount']
    if provider=='flutterwave':
        result=flutter('/v3/payments',{'tx_ref':order['reference'],'amount':amount,'currency':'NGN','redirect_url':redirect(provider),'customer':{'email':order['email']},'customizations':{'title':'Nelsonict hotspot voucher'}})
        return {'checkout_url':checkout_url(provider,result.get('link',''))}
    result=monnify('/api/v1/merchant/transactions/init-transaction',{'amount':float(Decimal(amount)),'customerName':order['customer_name'],'customerEmail':order['email'],'paymentReference':order['reference'],'paymentDescription':'Hotspot voucher','currencyCode':'NGN','contractCode':required('MONNIFY_CONTRACT_CODE'),'redirectUrl':redirect(provider)})
    if result.get('paymentReference')!=order['reference'] or not result.get('transactionReference'):raise ValidationError('Monnify initialization reference mismatch.')
    return {'checkout_url':checkout_url(provider,result.get('checkoutUrl','')),'provider_reference':result['transactionReference']}

def minor(amount):
    value=Decimal(str(amount))*100
    if not value.is_finite() or value!=value.to_integral_value() or value<0:raise ValidationError('Invalid verified amount.')
    return int(value)

def verify(order):
    provider=order['provider']
    if provider=='flutterwave':
        r=flutter('/v3/transactions/verify_by_reference?tx_ref='+quote(order['reference'],safe=''))
        return {'status':'success' if r.get('status')=='successful' else 'pending','reference':r.get('tx_ref'),'amount':minor(r.get('amount',0)),'currency':r.get('currency'),'domain':mode(provider),'customer':r.get('customer',{})}
    if not order.get('provider_reference'):raise ValidationError('Reconcile interrupted Monnify initialization in the merchant dashboard.')
    r=monnify('/api/v2/transactions/'+quote(order['provider_reference'],safe=''))
    if r.get('transactionReference')!=order['provider_reference']:raise ValidationError('Monnify transaction reference mismatch.')
    return {'status':'success' if r.get('paymentStatus')=='PAID' else 'pending','reference':r.get('paymentReference'),'amount':minor(r.get('amountPaid',0)),'currency':r.get('currency'),'domain':mode(provider),'customer':r.get('customer',{})}
