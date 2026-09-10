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
from core import Router, ValidationError, snapshot, digest, build_plan, voucher_operations, execute, rollback

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.Lock()
STATE = {'router':None,'plan':None,'host':None,'demo':False,'identity':None}

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
            'ip/hotspot/user':[], 'ip/hotspot/active':[], 'ip/hotspot/cookie':[],
            'ipv6/settings':{'disable-ipv6':'true'}, 'system/device-mode':{'hotspot':'yes'},
        })
        self.counter = 100
    def call(self,path,method='GET',data=None):
        from urllib.parse import unquote
        path = unquote(path)
        if method == 'GET':
            if path in self.data: return copy.deepcopy(self.data[path])
            menu, item = path.rsplit('/',1)
            return copy.deepcopy(next(x for x in self.data.get(menu,[]) if x['.id']==item))
        if method == 'PUT':
            self.counter += 1
            result = {'.id':f'*D{self.counter}', **data}
            self.data.setdefault(path,[]).append(result)
            return copy.deepcopy(result)
        menu, item = path.rsplit('/',1)
        record = next(x for x in self.data[menu] if x['.id']==item)
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
    journal = {'id':ident,'kind':kind,'host':STATE['host'],'identity':STATE['identity'],'demo':STATE['demo'],'created':time.time(),'entries':[]}
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
    return journal

def public_status():
    r=active_router()
    resource=r.call('system/resource'); identity=r.call('system/identity')
    return {'demo':STATE['demo'],'host':STATE['host'],'resource':resource[0] if isinstance(resource,list) else resource,
            'identity':identity[0] if isinstance(identity,list) else identity,
            'interfaces':r.call('interface'),'profiles':r.call('ip/hotspot/user/profile'),'servers':r.call('ip/hotspot'),
            'users':[{k:v for k,v in x.items() if k in ('.id','name','profile','server','uptime','limit-uptime','bytes-in','bytes-out','disabled','comment')} for x in r.call('ip/hotspot/user')],
            'active':[{k:v for k,v in x.items() if k in ('.id','user','address','uptime','bytes-in','bytes-out')} for x in r.call('ip/hotspot/active')]}

def route(path,data):
    if path=='/api/connect':
        STATE.update(router=None,plan=None,host=None,identity=None)
        r=Router(data.get('host',''),data.get('username',''),data.get('password',''),data.get('port',443),data.get('fingerprint',''))
        s=snapshot(r)
        ident=s['system/identity']; ident=ident[0] if isinstance(ident,list) else ident
        STATE.update(router=r,host=r.host,identity=ident.get('name'),demo=False)
        return public_status()
    if path=='/api/demo':
        STATE.update(router=DemoRouter(),host='Demonstration only',identity='demo',demo=True,plan=None,last_journal=None)
        return public_status()
    if path=='/api/disconnect':
        STATE.update(router=None,plan=None,host=None,identity=None,demo=False,last_journal=None)
        return {'ok':True}
    r=active_router()
    if path=='/api/status': return public_status()
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
    if path=='/api/vouchers':
        profile=data.get('profile'); server=data.get('server')
        if profile not in [x['name'] for x in r.call('ip/hotspot/user/profile')]: raise ValidationError('Profile no longer exists.')
        if server not in [x['name'] for x in r.call('ip/hotspot') if x.get('disabled')!='true']: raise ValidationError('Select an enabled hotspot server.')
        if data.get('confirmation')!='CREATE': raise ValidationError('Confirm voucher creation.')
        operations,vouchers=voucher_operations(profile,server,data.get('count',1),data.get('duration','1d'),[x['name'] for x in r.call('ip/hotspot/user')])
        journal=new_journal('vouchers')
        execute(r,operations,journal)
        return {'vouchers':vouchers,'journal':journal['id'],'demo':STATE['demo']}
    if path=='/api/disable':
        uid=data.get('id','')
        user=next((u for u in r.call('ip/hotspot/user') if u.get('.id')==uid),None)
        if not user or not user.get('comment','').startswith('ns-batch-'):
            raise ValidationError('Only vouchers created by this application can be disabled here.')
        if data.get('confirmation')!='DISABLE': raise ValidationError('Confirm disabling this voucher.')
        from urllib.parse import quote
        r.call('ip/hotspot/user/'+quote(uid,safe=''),'PATCH',{'disabled':'yes'})
        # Retain user/accounting row while removing login sessions and cookies.
        for menu in ('ip/hotspot/active','ip/hotspot/cookie'):
            for row in r.call(menu):
                if row.get('user')==user['name']:
                    r.call(menu+'/'+quote(row['.id'],safe=''),'DELETE')
        return {'ok':True}
    if path=='/api/history':
        records=[]
        if DATA.exists():
            for f in sorted(DATA.glob('*.json'),reverse=True)[:50]:
                record=json.loads(f.read_text())
                if record['host']==STATE['host']: records.append(record)
        if STATE['demo'] and STATE.get('last_journal'):
            records=[{k:v for k,v in STATE['last_journal'].items() if k!='save'}]
        return {'records':records}
    if path=='/api/rollback':
        if data.get('confirmation')!='ROLLBACK': raise ValidationError('Enter ROLLBACK to remove the recorded additions.')
        ident=data.get('id','')
        import re
        if not re.fullmatch(r'[0-9]+-[0-9a-f]{8}',ident): raise ValidationError('Invalid change record.')
        journal=STATE.get('last_journal')
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
        if journal['host']!=STATE['host'] or journal['identity']!=STATE['identity'] or journal['demo']!=STATE['demo']:
            raise ValidationError('This change record belongs to another router or mode.')
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
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers(); self.wfile.write(raw)
    def valid_host(self):
        return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'
    def do_GET(self):
        if not self.valid_host(): return self.send(403,{'error':'Use the 127.0.0.1 launch address.'})
        name={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}.get(urlsplit(self.path).path)
        if not name: return self.send(404,{'error':'Not found'})
        kind={'index.html':'text/html; charset=utf-8','app.js':'text/javascript; charset=utf-8','style.css':'text/css; charset=utf-8'}[name]
        self.send(200,(ROOT/'web'/name).read_bytes(),kind)
    def do_POST(self):
        if not self.valid_host() or self.headers.get('Origin')!=f'http://127.0.0.1:{self.server.server_port}' or not secrets.compare_digest(self.headers.get('X-App-Token',''),TOKEN):
            return self.send(403,{'error':'Open the private launch URL printed by the application.'})
        try:
            if self.headers.get('Content-Type')!='application/json': raise ValidationError('JSON required.')
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<32768: raise ValidationError('Request size invalid.')
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict): raise ValidationError('JSON object required.')
            with LOCK: result=route(self.path,data)
            self.send(200,result)
        except (ValidationError,ValueError,KeyError,TypeError) as e:
            self.send(400,{'error':str(e),'journal':(STATE.get('last_journal') or {}).get('id')})
        except ssl.SSLError:
            self.send(400,{'error':'TLS certificate verification failed. Install a trusted certificate or enter its independently verified SHA-256 pin.'})
        except Exception:
            self.send(502,{'error':'Router request or local journal write failed. Check connectivity, HTTPS, permissions and disk space. If a write was running, inspect Change history before retrying.','journal':(STATE.get('last_journal') or {}).get('id')})

def main():
    parser=argparse.ArgumentParser(description='Nelsonict Router Manager — local management application')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    server.daemon_threads=True
    url=f'http://127.0.0.1:{server.server_port}/#token={TOKEN}'
    print('Nelsonict Router Manager 0.1.0 — local pilot build\nKeep this terminal open. Press Ctrl+C to stop.\nPrivate launch URL:\n'+url,flush=True)
    if not args.no_browser: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__=='__main__': main()
