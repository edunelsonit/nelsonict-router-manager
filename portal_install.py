"""Install generated portal pages into a fresh copy of the active directory."""
import secrets
from urllib.parse import quote
from core import ValidationError
from templates import portal_files, portal_plan, validate_template, REQUIRED_FILES

def inventory(router):
    return {x['name']:x for x in router.call('file') if x.get('name')}

def prepare(router,server,raw,directory=None):
    template=validate_template(raw)
    files=inventory(router)
    target=directory or ('flash/' if 'flash' in files else '')+'ns-portal-'+secrets.token_hex(6)
    if target in files or any(n.startswith(target+'/') for n in files):
        raise ValidationError('Destination already exists. Prepare a new installation.')
    # Reuse profile, authentication and shared-server checks without requiring uploads.
    class PlannedFiles:
        def call(self,path):
            if path=='file':return [{'name':target+'/'+f} for f in REQUIRED_FILES]
            return router.call(path)
    plan=portal_plan(PlannedFiles(),server,target,template['mode'])
    source=plan['before'].strip('/')
    if not source or source not in files or files[source].get('type')!='directory' or not files[source].get('.id'):
        raise ValidationError('The active portal directory could not be identified in router Files.')
    required=set(REQUIRED_FILES)-set(portal_files(template))
    if any(source+'/'+f not in files for f in required):
        raise ValidationError('The current portal is missing required support files. Repair it before installing.')
    plan.update(template=template,source=source,source_id=files[source]['.id'],
                source_files=sorted((n,x.get('type',''),str(x.get('size',''))) for n,x in files.items() if n.startswith(source+'/')))
    plan['warnings'][0]='The app copies the active folder, uploads and verifies the customized pages, then activates the new folder. Keep a router backup.'
    return plan

def deploy(router,plan,journal):
    fresh=prepare(router,plan['server'],plan['template'],plan['directory'])
    if any(fresh[k]!=plan[k] for k in fresh):raise ValidationError('Portal configuration or files changed. Prepare again.')
    def write(label,path,method,data,**extra):
        entry={'label':label,'path':path,'state':'pending',**extra}
        journal['entries'].append(entry);journal['save']()
        try:
            result=router.call(path,method,data)
            entry['state']='applied';journal['save']();return result
        except Exception:
            entry['state']='uncertain';journal['save']();raise
    write('Copy active portal folder','file/copy','POST',{'numbers':plan['source_id'],'name':plan['directory']})
    files=inventory(router)
    for name,kind,size in plan['source_files']:
        dest=plan['directory']+name[len(plan['source']):]
        if dest not in files or files[dest].get('type','')!=kind or str(files[dest].get('size',''))!=size:
            raise ValidationError('Portal copy is incomplete. Previous portal remains selected; inspect Files before retrying.')
    for name,contents in portal_files(plan['template']).items():
        if len(contents.encode())>60000:raise ValidationError('Portal page exceeds router file editing limit.')
        dest=plan['directory']+'/'+name
        item=files.get(dest)
        if item is None:
            item=write('Create '+dest,'file','PUT',{'name':dest,'type':'file'})
        ident=item.get('.id')
        if not ident:raise ValidationError('Uploaded file ID unavailable. Previous portal remains selected.')
        write('Upload '+dest,'file/'+quote(ident,safe=''),'PATCH',{'contents':contents})
        read=router.call('file/print','POST',{'.proplist':['.id','name','contents'],'.query':['.id='+ident]})
        if not isinstance(read,list) or len(read)!=1 or read[0].get('name')!=dest or read[0].get('contents')!=contents:
            raise ValidationError('Portal upload verification failed. Previous portal remains selected.')
    checked=portal_plan(router,plan['server'],plan['directory'],plan['mode'])
    for key in ('profile_id','profile_name','before','affected_servers','login_by'):
        if checked[key]!=plan[key]:raise ValidationError('Hotspot profile changed during upload. Review before activation.')
    write('Activate '+plan['directory'],'ip/hotspot/profile/'+quote(plan['profile_id'],safe=''),'PATCH',
          {'html-directory':plan['directory']},id=plan['profile_id'],values={'name':plan['profile_name']},
          before=plan['before'],after=plan['directory'],activation=True)
