"""Reviewed RouterOS v7 User Manager configuration; no arbitrary command endpoint."""
import hashlib,json,re,time,secrets
from urllib.parse import quote
from core import ValidationError

FIELDS={
 'user-manager':'enabled use-profiles authentication-port accounting-port certificate radsec-certificate',
 'user-manager/router':'name address shared-secret disabled coa-port protocol comment',
 'user-manager/profile':'name name-for-users validity starts-when price override-shared-users comment',
 'user-manager/limitation':'name uptime-limit download-limit upload-limit transfer-limit rate-limit-rx rate-limit-tx reset-counters-interval comment',
 'user-manager/profile-limitation':'profile limitation from-time till-time weekdays comment',
 'user-manager/user':'name password group shared-users disabled caller-id attributes comment',
 'user-manager/user/group':'name outer-auths inner-auths attributes comment',
 'user-manager/user-profile':'user profile',
 'radius':'address secret service authentication-port accounting-port timeout disabled src-address protocol certificate',
 'radius/incoming':'accept port',
 'ip/hotspot/profile':'use-radius radius-accounting radius-interim-update',
}
REQUIRED={'user-manager/router':['name','address','shared-secret'],'user-manager/profile':['name'],
 'user-manager/limitation':['name'],'user-manager/profile-limitation':['profile','limitation'],
 'user-manager/user':['name','password'],'user-manager/user/group':['name'],
 'user-manager/user-profile':['user','profile'],'radius':['address','secret','service']}
SINGLE={'user-manager','radius/incoming'}
SECRETS={'password','shared-secret','secret','otp-secret'}
READONLY=['user-manager/session','user-manager/payment','user-manager/database']

def rows(value):return value if isinstance(value,list) else [value]
def public(row):return {k:('[redacted]' if k in SECRETS else v) for k,v in row.items() if k not in ('otp-secret',)}
def snapshot(router):
    result={}
    try:
        result['user-manager']=router.call('user-manager')
    except Exception as exc:raise ValidationError('User Manager is unavailable. Install the matching RouterOS v7 user-manager package, check architecture/licence/storage and API permissions, then reconnect.') from exc
    for path in FIELDS:
        if path!='user-manager':result[path]=router.call(path)
    return result

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
def inventory(router):
    state=snapshot(router);unavailable=[]
    for path in READONLY:
        try:state[path]=router.call(path)
        except Exception:unavailable.append(path)
    # Only expose known configuration fields; operational tables use an explicit list.
    operational=set('.id name user profile active started ended uptime download upload state end-time nas-ip-address user-address status db-size free-disk-space currency price method trans-status'.split())
    return {'tables':{p:[public({k:v for k,v in row.items() if k in set(FIELDS.get(p,'').split())|operational}) for row in rows(values)] for p,values in state.items()},'fields':{p:v.split() for p,v in FIELDS.items()},'singletons':sorted(SINGLE),'unavailable':unavailable}

def prepare(router,data):
    path=data.get('path');action=data.get('action');values=data.get('values',{});ident=data.get('id','')
    if path not in FIELDS or action not in ('create','update','delete'):raise ValidationError('Unsupported User Manager operation.')
    if path in SINGLE and action!='update':raise ValidationError('Settings can only be updated.')
    if path=='ip/hotspot/profile' and action!='update':raise ValidationError('Select an existing hotspot server profile to update.')
    if not isinstance(values,dict) or set(values)-set(FIELDS[path].split()):raise ValidationError('Unknown configuration field.')
    if action=='delete':values={}
    elif not values:raise ValidationError('Enter at least one setting.')
    for key,value in values.items():
        if not isinstance(value,str) or len(value)>1024 or any(ord(c)<32 for c in value):raise ValidationError('Use plain text values of at most 1,024 characters.')
        if key in ('enabled','disabled','use-profiles','use-radius','radius-accounting','accept') and value not in ('yes','no'):raise ValidationError(key+' must be yes or no.')
        if key in ('authentication-port','accounting-port','coa-port','port') and (not value.isdigit() or not 1<=int(value)<=65535):raise ValidationError('Invalid port.')
        if key in SECRETS and (not value or value=='[redacted]'):raise ValidationError('Enter a new secret, or omit the field to retain it.')
    if action=='create' and any(not values.get(k) for k in REQUIRED.get(path,[])):raise ValidationError('Required fields: '+', '.join(REQUIRED[path]))
    state=snapshot(router)
    if action!='create' and path not in SINGLE:
        if not isinstance(ident,str) or not re.fullmatch(r'\*[A-Za-z0-9]+',ident):raise ValidationError('Select an existing row ID.')
        before=next((r for r in rows(state[path]) if r.get('.id')==ident),None)
        if before is None:raise ValidationError('Selected record no longer exists.')
    else:before=rows(state[path])[0] if path in SINGLE else {}
    if action=='create' and values.get('name') and any(r.get('name')==values['name'] for r in rows(state[path])):raise ValidationError('That name already exists.')
    # Resolve references before writes; RouterOS validates further service-specific rules.
    references={'user-manager/user-profile':{'user':'user-manager/user','profile':'user-manager/profile'},'user-manager/profile-limitation':{'profile':'user-manager/profile','limitation':'user-manager/limitation'},'user-manager/user':{'group':'user-manager/user/group'}}
    for field,target in references.get(path,{}).items():
        if field in values and not any(r.get('name')==values[field] for r in rows(state[target])):raise ValidationError('Create the referenced '+field+' first.')
    return {'id':secrets.token_urlsafe(24),'created':time.time(),'fingerprint':digest(state),'path':path,'action':action,'target':ident,'values':values,'before':before}

def preview(plan):return {k:(public(v) if k in ('values','before') else v) for k,v in plan.items() if k!='fingerprint'}
def apply(router,plan,journal):
    if time.time()-plan['created']>600 or digest(snapshot(router))!=plan['fingerprint']:raise ValidationError('Configuration changed or review expired. Prepare again.')
    path=plan['path'];action=plan['action'];ident=plan['target'];values=plan['values']
    entry={'path':path,'label':action+' '+path,'state':'pending','before':public(plan['before']),'values':public(values)}
    journal['entries'].append(entry);journal['save']()
    try:
        target=path+('/'+quote(ident,safe='') if ident and path not in SINGLE else '')
        if path in SINGLE:result=router.call(path+'/set','POST',values)
        else:result=router.call(target,{'create':'PUT','update':'PATCH','delete':'DELETE'}[action],values if action!='delete' else None)
        if action=='create':
            if not isinstance(result,dict) or not result.get('.id'):raise ValidationError('No created ID returned; inspect the router.')
            ident=result['.id']
        entry['id']=ident
        if action=='delete':
            if any(r.get('.id')==ident for r in rows(router.call(path))):raise ValidationError('Delete verification failed; inspect the journal.')
        else:
            checked=rows(router.call(path if path in SINGLE else path+'/'+quote(ident,safe='')))[0]
            def same(key,value):
                actual=str(checked.get(key,''));expected=str(value)
                if key in ('enabled','disabled','accept','use-profiles','use-radius','radius-accounting'):
                    return {'true':'yes','false':'no'}.get(actual,actual)==expected
                if key in ('validity','uptime-limit','timeout','radius-interim-update','from-time','till-time') and expected!='unlimited':
                    from expiry import ros_seconds
                    return ros_seconds(actual)==ros_seconds(expected)
                if key in ('service','weekdays','outer-auths','inner-auths'):
                    return set(actual.split(','))==set(expected.split(','))
                if key in ('rate-limit-rx','rate-limit-tx'):
                    def rate(v):
                        match=re.fullmatch(r'(\d+)([kKmMgG]?)',v)
                        return int(match[1])*{'':1,'k':1000,'m':1000000,'g':1000000000}[match[2].lower()] if match else v
                    return rate(actual)==rate(expected)
                if key=='price':
                    from decimal import Decimal
                    return Decimal(actual)==Decimal(expected)
                return actual==expected
            if any(not same(k,v) for k,v in values.items() if k not in SECRETS):raise ValidationError('Readback differs from the reviewed settings. Inspect the router and journal.')
        entry['state']='applied';journal['save']()
    except Exception:entry['state']='uncertain';journal['save']();raise
    return {'ok':True,'notice':'Refresh User Manager and test authentication/accounting. Disabling a User Manager user does not by itself guarantee immediate session disconnection.'}
