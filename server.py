#!/usr/bin/env python3
"""Local browser application. Python 3.11+, no third-party packages."""
import argparse
import copy
import json
import os
from pathlib import Path
import secrets
import ssl
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from templates import TemplateStore, validate_template, print_html, portal_package, portal_plan, REQUIRED_FILES
from expiry import (encode, decode, policy_from_form, describe_user, router_clock, engine_operations, expiry_profile, HOOK_SOURCE, ENGINE_NAME, SCHEDULER_SOURCE, deadline)
from core import Router, ValidationError, snapshot, digest, build_plan, voucher_operations, execute, rollback

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.Lock()
STATE = {'router':None,'plan':None,'host':None,'demo':False,'identity':None}

from locations import LocationStore
from voucher_history import VoucherHistory, select as select_history, summaries as history_summaries
from pricing import PriceStore, validate_price, profile_key

from portal_install import prepare as prepare_portal, deploy as deploy_portal

class DemoRouter:
    def __init__(self):
        self.data = {p:[] for p in __import__('core').PATHS}
        self.data.update({
            'system/resource':[{'version':'7.x (simulated)','board-name':'Demo router','uptime':'3h12m','cpu-load':'8','free-memory':'134217728','total-memory':'268435456'}],
            'system/identity':[{'name':'Nelsonict • demonstration'}],
            'interface':[{'.id':'*1','name':'ether1','type':'ether','running':'true'},{'.id':'*2','name':'bridge','type':'bridge','running':'true'},{'.id':'*3','name':'ether5','type':'ether','running':'false'}],
            'ip/address':[{'.id':'*1','address':'192.168.88.1/24','interface':'bridge'}],
            'ip/firewall/filter':[{'.id':'*1','chain':'input','action':'drop','comment':'Example WAN protection'}],
            'ip/hotspot':[{'.id':'*1','name':'hotspot1','interface':'bridge','profile':'default','disabled':'false'}],
            'ip/hotspot/user/profile':[{'.id':'*1','name':'default','shared-users':'1'}],
            'ip/hotspot/user':[], 'ip/hotspot/active':[], 'ip/hotspot/cookie':[], 'system/scheduler':[],
            'ip/hotspot/profile':[{'.id':'*P1','name':'default','html-directory':'hotspot','login-by':'http-chap,cookie'}],
            'file':[{'name':'nelsonict-'+mode+'/'+f} for mode in ('pin','credentials') for f in REQUIRED_FILES],
            'ipv6/settings':{'disable-ipv6':'true'}, 'system/device-mode':{'hotspot':'yes'},
        })
        self.data['file'] += [{'.id':'*F0','name':'hotspot','type':'directory'}] + [{'.id':f'*F{i+1}','name':'hotspot/'+f,'type':'file','size':'12','contents':'demo support'} for i,f in enumerate(REQUIRED_FILES)]
        self.counter = 100
    def call(self,path,method='GET',data=None):
        from urllib.parse import unquote
        path = unquote(path)
        if method=='POST' and path=='file/copy':
            source=next(x['name'] for x in self.data['file'] if x.get('.id')==data['numbers'])
            for row in list(self.data['file']):
                if row['name']==source or row['name'].startswith(source+'/'):
                    self.counter+=1
                    self.data['file'].append({**row,'.id':f'*D{self.counter}','name':data['name']+row['name'][len(source):]})
            return {}
        if method=='POST' and path=='file/print':
            ident=data['.query'][0].split('=',1)[1]
            return copy.deepcopy([x for x in self.data['file'] if x.get('.id')==ident])
        if method == 'GET' and path == 'system/ntp/client': return {'status':'synchronized'}
        if method == 'GET' and path == 'system/clock':
            from datetime import datetime, timezone
            now=datetime.now(timezone.utc)
            return {'date':now.strftime('%Y-%m-%d'),'time':now.strftime('%H:%M:%S'),'gmt-offset':'+00:00'}
        if method == 'GET':
            if path in self.data: return copy.deepcopy(self.data[path])
            menu, item = path.rsplit('/',1)
            return copy.deepcopy(next(x for x in self.data.get(menu,[]) if x.get('.id')==item))
        if method == 'PUT':
            self.counter += 1
            result = {'.id':f'*D{self.counter}', **data}
            self.data.setdefault(path,[]).append(result)
            return copy.deepcopy(result)
        menu, item = path.rsplit('/',1)
        record = next(x for x in self.data[menu] if x.get('.id')==item)
        if method == 'DELETE': self.data[menu].remove(record); return {}
        if method == 'PATCH': record.update(data); return copy.deepcopy(record)
        raise ValidationError('Unsupported demo operation.')

def active_router():
    if STATE['router'] is None: raise ValidationError('Connect to a router or open demonstration mode first.')
    return STATE['router']

def new_network_checks(router,cfg):
    if cfg.get('scenario') == 'existing': return
    ipv6 = router.call('ipv6/settings')
    if isinstance(ipv6,list): ipv6=ipv6[0]
    if ipv6.get('disable-ipv6') not in ('true','yes'):
        raise ValidationError('New-network setup requires IPv6 disabled on this router in this release. Review IPv6 in WinBox; the wizard will not disable it globally.')
    if cfg.get('scenario') == 'hotspot':
        mode = router.call('system/device-mode')
        if isinstance(mode,list): mode=mode[0]
        if mode.get('hotspot') not in ('yes','true'):
            raise ValidationError('Hotspot is not permitted by device-mode. Enable it with the required physical confirmation first.')

def new_journal(kind):
    ident = str(time.time_ns()) + '-' + secrets.token_hex(4)
    journal = {'id':ident,'kind':kind,'host':STATE['host'],'identity':STATE['identity'],'location_id':STATE.get('location_id'),'demo':STATE['demo'],'created':time.time(),'entries':[]}
    def save():
        if journal['demo']: return
        DATA.mkdir(mode=0o700,exist_ok=True)
        target = DATA / (ident + '.json')
        temp = DATA / (ident + '.tmp')
        fd = os.open(temp, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump({k:v for k,v in journal.items() if k!='save'},f,indent=2)
            f.flush(); os.fsync(f.fileno())
        os.replace(temp,target)
    journal['save']=save
    STATE['last_journal']=journal
    if journal['demo']:STATE.setdefault('demo_journals',{})[ident]=journal
    return journal

def public_status():
    r=active_router()
    resource=r.call('system/resource'); identity=r.call('system/identity')
    resource=resource[0] if isinstance(resource,list) else resource
    clock=router_clock(r,resource)
    users=r.call('ip/hotspot/user'); sessions=r.call('ip/hotspot/active')
    visible=[]
    for x in users:
        row={k:v for k,v in x.items() if k in ('.id','name','profile','server','uptime','limit-uptime','bytes-in','bytes-out','disabled')}
        row.update(describe_user(x,sessions,clock['now'],clock['boot'],clock['verified']))
        visible.append(row)
    return {'demo':STATE['demo'],'host':STATE['host'],'resource':resource,
            'identity':identity[0] if isinstance(identity,list) else identity,'location_id':STATE.get('location_id'),'location_name':STATE.get('location_name'),'transport':getattr(r,'transport','demo'),
            'interfaces':r.call('interface'),
            'profiles':[{k:v for k,v in x.items() if k in ('.id','name','rate-limit','shared-users')} for x in r.call('ip/hotspot/user/profile')],
            'servers':r.call('ip/hotspot'),'users':visible,
            'active':[{k:v for k,v in x.items() if k in ('.id','user','address','uptime','bytes-in','bytes-out')} for x in sessions],
            'clock':clock,'observed_at':time.time(),
            'counts':{'sessions':len(sessions),'connected_users':len(set(x.get('user') for x in sessions)),
                      'overdue_active':sum(x['overdue_active'] for x in visible),
                      'expired':sum(x['expiry_state']=='expired' for x in visible)}}

def ticket_action(r,data):
    action=data.get('action')
    if action not in ('disable','enable','disconnect') or data.get('confirmation')!=action.upper():
        raise ValidationError('Confirm the selected ticket action.')
    uid=data.get('id','')
    user=next((u for u in r.call('ip/hotspot/user') if u.get('.id')==uid),None)
    if not user:raise ValidationError('Local hotspot account no longer exists. Refresh first.')
    if action=='enable':
        resource=r.call('system/resource');resource=resource[0] if isinstance(resource,list) else resource
        clock=router_clock(r,resource)
        status=describe_user(user,[],clock['now'],clock['boot'],clock['verified'])
        if status['expiry_state'] in ('expired','clock-unverified','invalid-policy'):
            raise ValidationError('This ticket is expired or its expiry cannot be verified. Issue a new ticket or repair the policy/time first.')
    from urllib.parse import quote
    journal=new_journal('ticket-action')
    entry={'path':'ip/hotspot/user','id':uid,'label':action+' ticket '+user['name'],'state':'pending','values':{'name':user['name']},'action':action}
    journal['entries'].append(entry);journal['save']()
    try:
        if action in ('disable','enable'):
            r.call('ip/hotspot/user/'+quote(uid,safe=''),'PATCH',{'disabled':'yes' if action=='disable' else 'no'})
            entry['state']='account-updated';journal['save']()
        if action in ('disable','disconnect'):
            for menu in ('ip/hotspot/active','ip/hotspot/cookie'):
                for row in r.call(menu):
                    if row.get('user')==user['name']:r.call(menu+'/'+quote(row['.id'],safe=''),'DELETE')
        entry['state']='applied';journal['save']()
    except Exception:
        entry['state']='partial' if entry['state']=='account-updated' else 'uncertain';journal['save']();raise
    return {'ok':True,'journal':journal['id'],'action':action}

def voucher_archive():
    if STATE['demo']:return copy.deepcopy(STATE.setdefault('demo_vouchers',{}))
    return VoucherHistory(DATA/'vouchers',STATE.get('location_id') or STATE['host'],STATE['identity']).read()

def save_voucher_archive(records):
    if STATE['demo']:STATE['demo_vouchers']=copy.deepcopy(records)
    else:VoucherHistory(DATA/'vouchers',STATE.get('location_id') or STATE['host'],STATE['identity']).write(records)

def profile_prices():
    if STATE['demo']:return STATE.setdefault('demo_prices',{})
    return PriceStore(DATA/'prices',STATE.get('location_id') or STATE['host'],STATE['identity']).read()

def save_profile_prices(values):
    if STATE['demo']:STATE['demo_prices']=values
    else:PriceStore(DATA/'prices',STATE.get('location_id') or STATE['host'],STATE['identity']).write(values)

def route(path,data):
    if path=='/api/locations/list':return {'locations':LocationStore(DATA/'locations').list()}
    if path=='/api/locations/save':return {'location':LocationStore(DATA/'locations').save(data)}
    if path=='/api/locations/delete':
        if data.get('id')==STATE.get('location_id'):raise ValidationError('Disconnect this location before removing it.')
        LocationStore(DATA/'locations').delete(data.get('id'));return {'ok':True}
    if path=='/api/templates/list':return {'templates':TemplateStore(DATA/'templates').list()}
    if path=='/api/templates/save':return {'template':TemplateStore(DATA/'templates').save(data.get('template'))}
    if path=='/api/templates/render':return {'html':print_html(data.get('template'),data.get('vouchers'),bool(data.get('demo',False)))}
    if path=='/api/templates/export':return portal_package(data.get('template'))
    if path=='/api/connect':
        location=LocationStore(DATA/'locations').get(data['location_id']) if data.get('location_id') else None
        if location:data={**location,'password':data.get('password','')}
        STATE.update(router=None,plan=None,upload_plan=None,portal_plan=None,host=None,identity=None,location_id=None,location_name=None,last_journal=None)
        r=Router(data.get('host',''),data.get('username',''),data.get('password',''),data.get('port'),data.get('fingerprint',''),data.get('transport','https'))
        s=snapshot(r)
        ident=s['system/identity']; ident=ident[0] if isinstance(ident,list) else ident
        STATE.update(router=r,host=r.host,identity=ident.get('name'),demo=False,location_id=location['id'] if location else None,location_name=location['name'] if location else None)
        return public_status()
    if path=='/api/demo':
        STATE.update(router=DemoRouter(),host='Demonstration only',identity='demo',location_id=None,location_name=None,demo=True,plan=None,upload_plan=None,portal_plan=None,last_journal=None,demo_journals={},demo_prices={},demo_vouchers={})
        return public_status()
    if path=='/api/disconnect':
        STATE.update(router=None,plan=None,upload_plan=None,portal_plan=None,host=None,identity=None,demo=False,last_journal=None,location_id=None,location_name=None)
        return {'ok':True}
    r=active_router()
    if path=='/api/status': return public_status()
    if path=='/api/vouchers/history':
        return {'batches':history_summaries(voucher_archive())}
    if path=='/api/vouchers/reprint':
        if not data.get('batch') and not data.get('profile'):raise ValidationError('Select a batch or profile.')
        offset=int(data.get('offset',0))
        if offset<0:raise ValidationError('Invalid page offset.')
        rows=select_history(voucher_archive(),data.get('batch'),data.get('profile'))
        return {'vouchers':rows[offset:offset+100],'total':len(rows),'offset':offset,'demo':STATE['demo']}
    if path=='/api/vouchers/import':
        records=voucher_archive();known={v['username'] for record in records.values() for v in record['vouchers']};added=skipped=0
        for user in r.call('ip/hotspot/user'):
            if user.get('name') in known:continue
            comment=str(user.get('comment',''))
            try:policy=decode(comment)
            except ValidationError:skipped+=1;continue
            batch_id=policy.get('batch') if policy else (comment[9:] if comment.startswith('ns-batch-') else None)
            if not batch_id or not __import__('re').fullmatch('[0-9a-f]{8}',batch_id) or not user.get('password'):skipped+=1;continue
            record=records.setdefault(batch_id,{'batch':batch_id,'created':time.time(),'vouchers':[]})
            name=user['name'];password=user['password']
            record['vouchers'].append({'username':name,'password':password,'pin':name if name==password else None,'credential_mode':'pin' if name==password else 'credentials','profile':user.get('profile',''),'base_profile':user.get('profile',''),'batch':batch_id,'creation_state':'created','allowance':user.get('limit-uptime',''),'price_label':'','policy':policy.get('mode','connected') if policy else 'connected'})
            known.add(name);added+=1
        save_voucher_archive(records)
        return {'added':added,'skipped':skipped}
    if path=='/api/profiles/prices':
        prices=profile_prices()
        return {'profiles':[{'id':x['.id'],'name':x['name'],'price':prices.get(profile_key(x))} for x in r.call('ip/hotspot/user/profile')]}
    if path=='/api/profiles/price':
        profile=next((x for x in r.call('ip/hotspot/user/profile') if x.get('.id')==data.get('id') and x.get('name')==data.get('name')),None)
        if not profile:raise ValidationError('Profile changed or no longer exists. Refresh the profile list.')
        price=None if data.get('amount')=='' else validate_price(data.get('amount'),data.get('currency'))
        prices=profile_prices();key=profile_key(profile)
        if price is None:prices.pop(key,None)
        else:prices[key]=price
        save_profile_prices(prices)
        return {'ok':True,'price':price}

    if path=='/api/plan':
        STATE['plan']=None
        current=snapshot(r)
        plan=build_plan(current,data)
        new_network_checks(r,data)
        plan['id']=secrets.token_urlsafe(24)
        plan['config']=data
        STATE['plan']=plan
        return plan
    if path=='/api/apply':
        plan=STATE['plan']
        if not plan or data.get('plan_id')!=plan['id'] or time.time()-plan['created']>600:
            raise ValidationError('Plan expired or unavailable. Build and review a new plan.')
        if data.get('confirmation')!='APPLY' or data.get('backup') is not True:
            raise ValidationError('Confirm your backup and enter APPLY after reviewing the plan.')
        if digest(snapshot(r)) != plan['snapshot']:
            STATE['plan']=None
            raise ValidationError('Router configuration changed. Build a fresh plan before applying.')
        new_network_checks(r,plan['config'])
        journal=new_journal('setup')
        STATE['plan']=None  # Consume before first write; no duplicate click/replay.
        execute(r,plan['operations'],journal)
        return {'ok':True,'journal':journal['id'],'count':len(journal['entries']),'demo':STATE['demo']}
    if path=='/api/portal/prepare':
        STATE['upload_plan']=None
        plan=prepare_portal(r,data.get('server'),data.get('template'))
        plan.update(id=secrets.token_urlsafe(24),created=time.time(),host=STATE['host'],identity=STATE['identity'],demo=STATE['demo'])
        STATE['upload_plan']=plan
        return plan
    if path=='/api/portal/deploy':
        plan=STATE.get('upload_plan')
        if not plan or data.get('plan_id')!=plan['id'] or time.time()-plan['created']>600:raise ValidationError('Prepare a fresh portal installation.')
        if data.get('confirmation')!='INSTALL PORTAL':raise ValidationError('Confirm INSTALL PORTAL after reviewing affected servers.')
        if any(plan[k]!=STATE[k] for k in ('host','identity','demo')):raise ValidationError('Router connection changed. Prepare again.')
        STATE['upload_plan']=None
        journal=new_journal('portal-deploy')
        deploy_portal(r,plan,journal)
        return {'ok':True,'journal':journal['id'],'directory':plan['directory']}
    if path=='/api/portal/plan':
        STATE['portal_plan']=None
        plan=portal_plan(r,data.get('server'),data.get('directory'),data.get('mode'))
        plan.update(id=secrets.token_urlsafe(24),created=time.time(),host=STATE['host'],identity=STATE['identity'],demo=STATE['demo'])
        STATE['portal_plan']=plan
        return plan
    if path=='/api/portal/install':
        plan=STATE.get('portal_plan')
        if not plan or data.get('plan_id')!=plan['id'] or time.time()-plan['created']>600:raise ValidationError('Portal plan expired. Check the installation again.')
        if data.get('confirmation')!='INSTALL PORTAL':raise ValidationError('Confirm INSTALL PORTAL after reviewing affected servers.')
        if plan['host']!=STATE['host'] or plan['identity']!=STATE['identity'] or plan['demo']!=STATE['demo']:raise ValidationError('Router connection changed. Check the installation again.')
        fresh=portal_plan(r,plan['server'],plan['directory'],plan['mode'])
        if any(fresh[k]!=plan[k] for k in fresh):raise ValidationError('Router portal configuration changed. Check the installation again.')
        from urllib.parse import quote
        journal=new_journal('portal-install')
        entry={'path':'ip/hotspot/profile','id':plan['profile_id'],'label':'Activate '+plan['directory'],'state':'pending','values':{'name':plan['profile_name']},'before':plan['before'],'after':plan['directory']}
        journal['entries'].append(entry);journal['save']();STATE['portal_plan']=None
        try:
            r.call('ip/hotspot/profile/'+quote(plan['profile_id'],safe=''),'PATCH',{'html-directory':plan['directory']})
            entry['state']='applied';journal['save']()
        except Exception:entry['state']='uncertain';journal['save']();raise
        return {'ok':True,'journal':journal['id']}
    if path=='/api/expiry/preview':
        return {'operations':engine_operations(r),'hook':HOOK_SOURCE,'scheduler':SCHEDULER_SOURCE,
                'notice':'Runs every 30 seconds on the router; requires synchronized NTP. Review and lab-test on your RouterOS version.'}
    if path=='/api/expiry/install':
        if data.get('confirmation')!='INSTALL':raise ValidationError('Review the router automation and enter INSTALL.')
        resource=r.call('system/resource');resource=resource[0] if isinstance(resource,list) else resource
        if not router_clock(r,resource)['verified']:raise ValidationError('Enable and synchronize router NTP before installing the expiry engine.')
        operations=engine_operations(r)
        journal=new_journal('expiry-engine')
        execute(r,operations,journal)
        return {'ok':True,'count':len(operations),'journal':journal['id']}
    if path=='/api/vouchers':
        profile=data.get('profile'); server=data.get('server')
        base=next((x for x in r.call('ip/hotspot/user/profile') if x.get('name')==profile),None)
        if not base: raise ValidationError('Profile no longer exists.')
        if server not in [x['name'] for x in r.call('ip/hotspot') if x.get('disabled')!='true']: raise ValidationError('Select an enabled hotspot server.')
        if data.get('confirmation')!='CREATE': raise ValidationError('Confirm voucher creation.')
        operations,vouchers=voucher_operations(profile,server,data.get('count',1),data.get('duration','1d'),[x['name'] for x in r.call('ip/hotspot/user')],data)
        # Legacy API callers can still request connected-time tickets without installing automation.
        if 'expiry_mode' in data:
            if engine_operations(r):raise ValidationError('Install the router expiry engine from Vouchers & users first.')
            resource=r.call('system/resource');resource=resource[0] if isinstance(resource,list) else resource
            clock=router_clock(r,resource)
            if not clock['verified']:raise ValidationError('Router NTP must be synchronized before creating tracked tickets.')
            policy=policy_from_form(data,clock['now']);policy['batch']=vouchers[0]['batch']
            profile_op=expiry_profile(base,policy['batch'])
            for op,voucher in zip(operations,vouchers):
                op['values']['profile']=profile_op['values']['name']
                op['values']['comment']=encode(policy)
                if policy['mode']!='connected':op['values']['limit-uptime']='0s'
                voucher.update(profile=profile_op['values']['name'],policy=policy['mode'],allowance=data.get('duration','1d') if policy['mode'] in ('elapsed','connected') else policy['mode'])
            operations.insert(0,profile_op)
        price=profile_prices().get(profile_key(base))
        for voucher in vouchers:
            voucher['base_profile']=profile
            if price:voucher.update(price_amount=price['amount'],currency=price['currency'],price_label=price['label'])
        journal=new_journal('vouchers')
        records=voucher_archive()
        record={'batch':vouchers[0]['batch'],'created':time.time(),'vouchers':[{**v,'creation_state':'pending'} for v in vouchers]}
        records[record['batch']]=record
        save_voucher_archive(records)  # Preserve credentials before any router write.
        try:execute(r,operations,journal)
        finally:
            states={e['values'].get('name'):e['state'] for e in journal['entries'] if e['path']=='ip/hotspot/user'}
            for v in record['vouchers']:v['creation_state']=states.get(v['username'],'not-created')
            save_voucher_archive(records)
        return {'vouchers':vouchers,'journal':journal['id'],'demo':STATE['demo']}
    if path=='/api/disable':return ticket_action(r,{**data,'action':'disable'})
    if path=='/api/ticket/action':return ticket_action(r,data)
    if path=='/api/demo/activity':
        if not STATE['demo']:raise ValidationError('Sample activity is available only in demonstration mode.')
        now=int(time.time())
        for name,first,due,active in [('9000000001',now-7200,now+86400,True),('9000000002',now-90000,now-3600,True),('9000000003',0,0,False)]:
            existing=next((u for u in r.call('ip/hotspot/user') if u['name']==name),None)
            if existing:continue
            policy={'mode':'elapsed','duration':86400,'offset':60,'cutoff':86340,'fixed':0,'fallback':36600,'first':first,'due':due,'batch':'de000001'}
            r.call('ip/hotspot/user','PUT',{'name':name,'profile':'default','server':'hotspot1','comment':encode(policy),'uptime':'1h' if first else '0s','disabled':'no'})
            if active:r.call('ip/hotspot/active','PUT',{'user':name,'address':'10.50.0.'+name[-1],'uptime':'15m'})
        return public_status()
    if path=='/api/history':
        records=[]
        if DATA.exists():
            for f in sorted(DATA.glob('*.json'),reverse=True)[:50]:
                record=json.loads(f.read_text())
                if record.get('location_id')==STATE.get('location_id') and record['host']==STATE['host'] and record['identity']==STATE['identity']: records.append(record)
        if STATE['demo'] and STATE.get('last_journal'):
            records=[{k:v for k,v in row.items() if k!='save'} for row in reversed(list(STATE.get('demo_journals',{}).values()))]
        return {'records':records}
    if path=='/api/rollback':
        if data.get('confirmation')!='ROLLBACK': raise ValidationError('Enter ROLLBACK to remove the recorded additions.')
        ident=data.get('id','')
        import re
        if not re.fullmatch(r'[0-9]+-[0-9a-f]{8}',ident): raise ValidationError('Invalid change record.')
        journal=STATE.get('demo_journals',{}).get(ident) if STATE['demo'] else STATE.get('last_journal')
        if not journal or journal['id']!=ident:
            f=DATA/(ident+'.json')
            if not f.exists(): raise ValidationError('Change record not found.')
            journal=json.loads(f.read_text())
            def save():
                temp=f.with_suffix('.tmp')
                fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
                with os.fdopen(fd,'w') as handle:
                    json.dump({k:v for k,v in journal.items() if k!='save'},handle,indent=2)
                    handle.flush(); os.fsync(handle.fileno())
                os.replace(temp,f)
            journal['save']=save
        if journal.get('location_id')!=STATE.get('location_id') or journal['host']!=STATE['host'] or journal['identity']!=STATE['identity'] or journal['demo']!=STATE['demo']:
            raise ValidationError('This change record belongs to another router or mode.')
        if journal['kind'] in ('portal-install','portal-deploy'):
            from urllib.parse import quote
            for entry in journal['entries']:
                if journal['kind']=='portal-deploy' and not entry.get('activation'):continue
                if entry['state']=='rolled-back':continue
                current=r.call('ip/hotspot/profile/'+quote(entry['id'],safe=''))
                if isinstance(current,list):current=current[0]
                if current.get('name')!=entry['values']['name'] or current.get('html-directory')!=entry['after'] or current.get('html-directory-override') not in (None,'','none'):
                    raise ValidationError('Portal changed after installation; inspect in WinBox before restoring.')
                r.call('ip/hotspot/profile/'+quote(entry['id'],safe=''),'PATCH',{'html-directory':entry['before']})
                entry['state']='rolled-back';journal['save']()
            return {'ok':True,'uncertain':0}
        if journal['kind']=='ticket-action':raise ValidationError('Ticket actions have no automatic rollback. Use the explicit enable/disable controls.')
        if journal['kind']=='expiry-engine' and any(str(x.get('comment','')).startswith('ns2,') for x in r.call('ip/hotspot/user')):
            raise ValidationError('Managed tickets still depend on the expiry engine. Do not remove it while those tickets exist.')
        rollback(r,journal['entries'],journal['save'])
        return {'ok':True,'uncertain':sum(x['state']=='uncertain' for x in journal['entries'])}
    raise ValidationError('Unknown operation.')

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass  # Avoid logging URLs or request bodies.
    def send(self,status,body,kind='application/json'):
        raw=json.dumps(body).encode() if kind=='application/json' else body
        self.send_response(status)
        self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers(); self.wfile.write(raw)
    def valid_host(self):
        return self.headers.get('Host')==urlsplit(getattr(self.server,'app_origin',f'http://127.0.0.1:{self.server.server_port}')).netloc
    def do_GET(self):
        if not self.valid_host(): return self.send(403,{'error':'Use the exact private launch address.'})
        name={'/':'index.html','/app.js':'app.js','/table-utils.js':'table-utils.js','/style.css':'style.css','/templates.js':'templates.js'}.get(urlsplit(self.path).path)
        if not name: return self.send(404,{'error':'Not found'})
        kind={'index.html':'text/html; charset=utf-8','app.js':'text/javascript; charset=utf-8','table-utils.js':'text/javascript; charset=utf-8','templates.js':'text/javascript; charset=utf-8','style.css':'text/css; charset=utf-8'}[name]
        self.send(200,(ROOT/'web'/name).read_bytes(),kind)
    def do_POST(self):
        if not self.valid_host() or self.headers.get('Origin')!=getattr(self.server,'app_origin',f'http://127.0.0.1:{self.server.server_port}') or not secrets.compare_digest(self.headers.get('X-App-Token',''),TOKEN):
            return self.send(403,{'error':'Open the private launch URL printed by the application.'})
        try:
            if self.headers.get('Content-Type')!='application/json': raise ValidationError('JSON required.')
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<131072: raise ValidationError('Request size invalid.')
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict): raise ValidationError('JSON object required.')
            with LOCK: result=route(self.path,data)
            self.send(200,result)
        except (ValidationError,ValueError,KeyError,TypeError) as e:
            self.send(400,{'error':str(e),'journal':(STATE.get('last_journal') or {}).get('id')})
        except ssl.SSLError:
            self.send(400,{'error':'TLS certificate verification failed. Install a trusted certificate or enter its independently verified SHA-256 pin.'})
        except Exception:
            self.send(502,{'error':'Router request or local journal write failed. Check connectivity, selected router service, permissions and disk space. If a write was running, inspect Change history before retrying.','journal':(STATE.get('last_journal') or {}).get('id')})

def main():
    parser=argparse.ArgumentParser(description='Nelsonict Router Manager — local management application')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--listen',default='127.0.0.1',help='127.0.0.1 or a private LAN/VPN IPv4 address')
    parser.add_argument('--tls-cert',help='TLS server certificate PEM, required for phone access')
    parser.add_argument('--tls-key',help='TLS private key PEM, required for phone access')
    args=parser.parse_args()
    import ipaddress
    ip=ipaddress.ip_address(args.listen)
    private=any(ip.version==4 and ip in ipaddress.ip_network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16'))
    if args.listen!='127.0.0.1' and not private:parser.error('Bind to an explicit private LAN/VPN IPv4 address, not 0.0.0.0 or a public address.')
    if args.listen!='127.0.0.1' and not (args.tls_cert and args.tls_key):parser.error('Phone access requires --tls-cert and --tls-key. HTTP is local-only.')
    if bool(args.tls_cert)!=bool(args.tls_key):parser.error('Provide both TLS certificate and key.')
    server=ThreadingHTTPServer((args.listen,args.port),Handler)
    scheme='http'
    if args.tls_cert:
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version=ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(args.tls_cert,args.tls_key)
        server.socket=context.wrap_socket(server.socket,server_side=True)
        scheme='https'
    server.app_origin=f'{scheme}://{args.listen}:{server.server_port}'
    server.daemon_threads=True
    url=f'{server.app_origin}/#token={TOKEN}'
    print('Nelsonict Router Manager 0.3.0 — local pilot build\nKeep this terminal open. Press Ctrl+C to stop.\nPrivate launch URL:\n'+url,flush=True)
    if not args.no_browser: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__=='__main__': main()
