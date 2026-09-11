"""Read-only setup review and deterministic, reviewable RouterOS repairs."""
import hashlib,json,re,shlex,time
from urllib.parse import quote
from core import ValidationError,PATHS
from expiry import decode,encode,describe_user,router_clock,ros_seconds,ENGINE_NAME,SCHEDULER_SOURCE,HOOK_SOURCE

MENUS=PATHS+['ip/hotspot/user','ip/hotspot/active','ip/hotspot/cookie','system/scheduler','ip/dns','ip/route','file']
FIELDS={'.id','name','type','interface','bridge','address','network','gateway','dst-address','ranges','disabled','running','chain','action','protocol','dst-port','src-address','out-interface','in-interface','address-pool','profile','rate-limit','shared-users','limit-uptime','uptime','login-by','html-directory','html-directory-override','interval','policy','servers','allow-remote-requests','version','board-name','free-memory','total-memory','cpu-load','size'}
def rows(value):return value if isinstance(value,list) else [value]
def canonical(comment):
    parts=','.join(x.strip() for x in str(comment).strip().split(','))
    policy=decode(parts)
    return encode(policy) if policy else None

def project(raw):
    output={}
    for menu,values in raw.items():
        if menu not in MENUS:continue
        output[menu]=[]
        for index,row in enumerate(rows(values)):
            if not isinstance(row,dict):continue
            clean={k:v for k,v in row.items() if k in FIELDS and isinstance(v,(str,int,float,bool))}
            if menu=='ip/hotspot/user':
                clean['name']='ticket-'+str(index+1)
                try:clean['expiry_metadata']=decode(canonical(row.get('comment','')) or '')
                except ValidationError:clean['expiry_metadata']='invalid'
            if menu in ('ip/hotspot/active','ip/hotspot/cookie'):
                clean.pop('name',None);clean['account']='redacted'
            if menu=='system/identity':clean['name']='router'
            if menu=='system/scheduler':clean['script_present']=bool(row.get('on-event'))
            if menu=='ip/hotspot/user/profile':clean['login_hook_present']=bool(row.get('on-login'));clean['logout_hook_present']=bool(row.get('on-logout'))
            output[menu].append(clean)
    return output

def import_file(text,kind):
    if not isinstance(text,str) or len(text.encode())>262144:raise ValidationError('Export file limit is 256 KB.')
    skipped=0
    if kind=='json':
        obj=json.loads(text);raw=obj.get('configuration',obj) if isinstance(obj,dict) else None
        if not isinstance(raw,dict):raise ValidationError('Use a setup snapshot JSON object.')
    elif kind=='rsc':
        raw={};menu=''
        for line in text.replace('\\\n',' ').splitlines():
            line=line.strip()
            if not line or line.startswith('#'):continue
            if line.startswith('/'):
                possible=line[1:].strip().replace(' ','/')
                menu=possible if possible in MENUS else '';continue
            if not menu:skipped+=1;continue
            try:words=shlex.split(line)
            except ValueError:skipped+=1;continue
            if not words or words[0] not in ('add','set'):skipped+=1;continue
            row={}
            for word in words[1:]:
                if '=' in word:
                    k,v=word.split('=',1)
                    if k in FIELDS:row[k]=v
            raw.setdefault(menu,[]).append(row)
    else:raise ValidationError('Import a .rsc text export or snapshot .json file. Binary backups are unsupported.')
    result={'source':'imported-file','configuration':project(raw),'skipped_lines':skipped,'notice':'Read-only projection. Secrets, free-text comments and scripts are omitted. RSC parsing is partial; imported files never authorize changes.'}
    if len(json.dumps(result))>300000:raise ValidationError('Projected export is too large.')
    return result

def inspect(router,profile='',batch=''):
    raw={};unavailable=[]
    for menu in dict.fromkeys(MENUS):
        try:raw[menu]=router.call(menu)
        except Exception:unavailable.append(menu)
    resource=rows(raw.get('system/resource',{}))[0];clock=router_clock(router,resource)
    users=rows(raw.get('ip/hotspot/user',[]));sessions=rows(raw.get('ip/hotspot/active',[]));cookies=rows(raw.get('ip/hotspot/cookie',[]))
    fixes=[];findings=[]
    def add(kind,path,row,after,reason,**extra):
        key=kind+':'+row['.id']
        fixes.append({'id':key,'kind':kind,'path':path,'resource_id':row['.id'],'name':row.get('name',''),'before':{k:row.get(k,'') for k in ('name','comment','profile','disabled','limit-uptime','on-login','on-logout','on-event','interval','policy') if k in row or k in after},'after':after,'reason':reason,**extra})
    if not clock['verified']:findings.append('Router time is not verified. Calendar-expiry actions are withheld; synchronize NTP first.')
    for row in users:
        if profile and row.get('profile')!=profile:continue
        comment=row.get('comment','')
        try:normalized=canonical(comment);p=decode(normalized or '')
        except ValidationError:
            findings.append('A ticket has damaged expiry metadata; its original first-login/deadline cannot be inferred safely.');continue
        if batch and (p.get('batch') if p else str(comment).removeprefix('ns-batch-'))!=batch:continue
        after={}
        if normalized and normalized!=comment:after['comment']=normalized
        status=describe_user({**row,'comment':normalized or comment},sessions,clock['now'],clock['boot'],clock['verified'])
        expired=status['expiry_state']=='expired'
        if p:
            expected=p['duration'] if p['mode']=='connected' else 0
            try:limit=ros_seconds(row.get('limit-uptime','0s'))
            except ValidationError:limit=-1
            engine_ready=any(x.get('name')==ENGINE_NAME and x.get('on-event')==SCHEDULER_SOURCE and x.get('disabled') not in ('yes','true') for x in rows(raw.get('system/scheduler',[])))
            hook_ready=any(x.get('name')==row.get('profile') and x.get('on-login')==HOOK_SOURCE for x in rows(raw.get('ip/hotspot/user/profile',[])))
            if limit!=expected:
                if p['mode']=='connected' or expired or (engine_ready and hook_ready and status['expiry_state'] in ('valid','unused')):after['limit-uptime']=str(expected)+'s'
                else:findings.append('An uptime-limit repair is withheld until expiry automation and activation metadata are verified.')
        if expired and (after or row.get('disabled') not in ('true','yes') or any(x.get('user')==row.get('name') for x in sessions+cookies)):
            after['disabled']='yes'
            add('expired-ticket','ip/hotspot/user',row,after,'Disable an expired ticket, preserve/canonicalize its policy and remove sessions/cookies.')
        elif after:add('ticket-metadata','ip/hotspot/user',row,after,'Normalize machine comment and/or align uptime limit to the existing expiry policy.')
        if not p and not str(comment).startswith('ns-batch-'):findings.append('Legacy or untracked ticket found. Policy conversion requires explicit dates and is not inferred by AI.')
    for row in rows(raw.get('system/scheduler',[])):
        if row.get('name')==ENGINE_NAME:
            if row.get('comment')!='Nelsonict expiry v2':findings.append('Expiry scheduler ownership is uncertain; manual review required.');continue
            after={k:v for k,v in {'on-event':SCHEDULER_SOURCE,'interval':'30s','disabled':'no','policy':'read,write'}.items() if ({'true':'yes','false':'no'}.get(str(row.get(k)),str(row.get(k))) if k=='disabled' else row.get(k))!=v}
            if after and clock['verified']:add('expiry-engine','system/scheduler',row,after,'Restore the app-owned expiry scheduler to the bundled version.')
    if not any(x.get('name')==ENGINE_NAME for x in rows(raw.get('system/scheduler',[]))):findings.append('Expiry scheduler is missing. Use Vouchers & users → Review / install engine.')
    for row in rows(raw.get('ip/hotspot/user/profile',[])):
        if profile and row.get('name')!=profile:continue
        match=re.fullmatch('ns2-([0-9a-f]{8})',row.get('name',''))
        if not match or row.get('on-login') or row.get('on-logout') or (batch and batch!=match[1]):continue
        members=[u for u in users if u.get('profile')==row['name']]
        try:owned=bool(members) and all(decode(canonical(u.get('comment','')) or '')['batch']==match[1] for u in members)
        except (ValidationError,TypeError,KeyError):owned=False
        if owned:add('missing-hook','ip/hotspot/user/profile',row,{'on-login':HOOK_SOURCE},'Restore a missing login hook on a verified managed batch profile.')
    if len(fixes)>1000:raise ValidationError('More than 1,000 repairs. Narrow the profile or batch filter.')
    if raw.get('ip/hotspot') and any(x.get('action')=='fasttrack-connection' for x in rows(raw.get('ip/firewall/filter',[]))):findings.append('FastTrack rules exist alongside Hotspot. Review exclusions and bandwidth enforcement before changing firewall rules.')
    return {'source':'live-router','observed_at':time.time(),'clock':clock,'configuration':project(raw),'tickets':[{'id':u['.id'],'name':u.get('name',''),'profile':u.get('profile',''),'comment':u.get('comment',''),'protected':str(u.get('comment','')).strip().startswith(('ns2','ns-batch-'))} for u in users if not profile or u.get('profile')==profile],'unavailable':unavailable,'findings':list(dict.fromkeys(findings)),'fixes':fixes,'filters':{'profile':profile,'batch':batch}}

def ai_payload(review):
    # No original ticket usernames/PINs, raw comments or script bodies in the cloud payload.
    return {k:v for k,v in review.items() if k not in ('fixes','context','id','tickets')} | {'available_fixes':[{'id':f['id'],'kind':f['kind'],'reason':f['reason']} for f in review.get('fixes',[])]}

def apply_fixes(router,fixes,journal):
    for fix in fixes:
        path=fix['path']+'/'+quote(fix['resource_id'],safe='')
        current=rows(router.call(path))[0]
        if any(current.get(k,'')!=v for k,v in fix['before'].items()):raise ValidationError('A reviewed object changed. Collect a fresh snapshot before continuing.')
        entry={'path':fix['path'],'id':fix['resource_id'],'label':fix['reason'],'state':'pending','values':{'name':fix['name']},'before':fix['before'],'after':fix['after']}
        journal['entries'].append(entry);journal['save']()
        try:
            router.call(path,'PATCH',fix['after']);entry['state']='updated';journal['save']()
            if fix['kind']=='expired-ticket':
                for menu in ('ip/hotspot/active','ip/hotspot/cookie'):
                    for row in router.call(menu):
                        if row.get('user')==fix['name']:router.call(menu+'/'+quote(row['.id'],safe=''),'DELETE')
            checked=rows(router.call(path))[0]
            normalize=lambda v:{'true':'yes','false':'no'}.get(str(v),str(v))
            def same(k,value):
                if k in ('limit-uptime','interval'):
                    try:return ros_seconds(checked.get(k,'0s'))==ros_seconds(value)
                    except ValidationError:return False
                return normalize(checked.get(k,''))==normalize(value)
            if any(not same(k,v) for k,v in fix['after'].items()):raise ValidationError('Repair verification failed. Inspect the change record before retrying.')
            entry['state']='applied';journal['save']()
        except Exception:entry['state']='uncertain';journal['save']();raise

def comment_plan(router,ids,comment):
    if not isinstance(ids,list) or not 1<=len(ids)<=1000 or len(set(ids))!=len(ids):raise ValidationError('Select 1–1,000 distinct ticket IDs.')
    if not isinstance(comment,str) or len(comment)>240 or any(ord(c)<32 for c in comment) or comment.strip().startswith(('ns2','ns-batch-')):raise ValidationError('Use an ordinary note up to 240 characters; reserved metadata prefixes are blocked.')
    users={r['.id']:r for r in router.call('ip/hotspot/user')};fixes=[]
    for ident in ids:
        row=users.get(ident)
        if not row:raise ValidationError('A selected ticket no longer exists.')
        if str(row.get('comment','')).strip().startswith(('ns2','ns-batch-')):raise ValidationError('Managed expiry and batch comments cannot be replaced with notes. Use metadata repair to preserve their structure.')
        if row.get('comment','')==comment:continue
        fixes.append({'id':'legacy-note:'+ident,'kind':'legacy-note','path':'ip/hotspot/user','resource_id':ident,'name':row['name'],'before':{'name':row['name'],'comment':row.get('comment',''),'profile':row.get('profile','')},'after':{'comment':comment},'reason':'Replace an explicitly selected legacy ticket comment. Review any external automation that uses it.'})
    return fixes
