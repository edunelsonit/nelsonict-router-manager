"""Escaped voucher templates, credential settings and RouterOS portal packages."""
import base64
from html import escape
import io
import json
import os
from pathlib import Path
import re
import secrets
import string
import zipfile
from core import ValidationError

DEFAULT={'id':'default','name':'Nelsonict classic','brand':'NELSONICT SERVICES LIMITED','heading':'Internet access',
         'mode':'pin','accent':'#007f78','background':'#ffffff','layout':'a4','columns':3,
         'contact':'Ask the hotspot attendant for assistance.','price':'','network':'Nelsonict Wi-Fi',
         'footer':'Keep your ticket private.','show_policy':True,'show_profile':False}

def validate_template(raw):
    if not isinstance(raw,dict):raise ValidationError('Template must be an object.')
    result=dict(DEFAULT)
    for k,maximum in [('name',60),('brand',90),('heading',80),('contact',160),('price',40),('network',80),('footer',180)]:
        value=raw.get(k,result[k])
        if not isinstance(value,str) or len(value)>maximum or any(ord(c)<32 for c in value):raise ValidationError('Invalid template field: '+k)
        # RouterOS interprets $(...) in portal pages. Do not let brand text become servlet directives.
        if '$(' in value:raise ValidationError('RouterOS template directives are not allowed in custom text.')
        result[k]=value
    for k in ('accent','background'):
        value=raw.get(k,result[k])
        if not isinstance(value,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',value):raise ValidationError('Use a six-digit hex color.')
        result[k]=value
    result['mode']=raw.get('mode','pin');result['layout']=raw.get('layout','a4');result['columns']=int(raw.get('columns',3))
    if result['mode'] not in ('pin','credentials'):raise ValidationError('Choose PIN or username/password mode.')
    if result['layout'] not in ('a4','thermal58','thermal80') or result['columns'] not in (1,2,3):raise ValidationError('Invalid print layout.')
    for k in ('show_policy','show_profile'):
        if type(raw.get(k,result[k])) is not bool:raise ValidationError('Invalid visibility setting.')
        result[k]=raw.get(k,result[k])
    ident=raw.get('id','default')
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}',str(ident)):raise ValidationError('Invalid template ID.')
    result['id']=ident
    return result

class TemplateStore:
    def __init__(self,directory):self.directory=Path(directory)
    def list(self):
        rows=[dict(DEFAULT)]
        if self.directory.exists():
            for p in sorted(self.directory.glob('*.json')):
                rows.append(validate_template(json.loads(p.read_text(encoding='utf-8'))))
        return rows
    def save(self,raw):
        template=validate_template(raw)
        if template['id']=='default':template['id']='tpl-'+secrets.token_hex(6)
        self.directory.mkdir(parents=True,mode=0o700,exist_ok=True)
        target=self.directory/(template['id']+'.json');tmp=target.with_suffix('.tmp')
        fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as out:
            json.dump(template,out,ensure_ascii=False,indent=2);out.flush();os.fsync(out.fileno())
        os.replace(tmp,target)
        return template

def credential_settings(raw):
    mode=raw.get('credential_mode','pin')
    if mode not in ('pin','credentials'):raise ValidationError('Invalid credential mode.')
    prefix=str(raw.get('username_prefix','NS'))
    if not re.fullmatch(r'[A-Za-z0-9_-]{0,12}',prefix):raise ValidationError('Username prefix: up to 12 letters, digits, hyphens or underscores.')
    pin=int(raw.get('pin_length',10));user=int(raw.get('username_length',8));password=int(raw.get('password_length',12))
    if not 8<=pin<=16 or not 6<=user<=20 or not 8<=password<=32:raise ValidationError('PIN length 8–16, username suffix 6–20, password length 8–32.')
    return {'mode':mode,'prefix':prefix,'pin_length':pin,'username_length':user,'password_length':password}

def credentials(settings,used):
    for _ in range(100):
        if settings['mode']=='pin':
            name=secrets.choice('123456789')+''.join(secrets.choice(string.digits) for _ in range(settings['pin_length']-1));password=name
        else:
            alphabet='ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
            name=settings['prefix']+''.join(secrets.choice(alphabet) for _ in range(settings['username_length']))
            password=''.join(secrets.choice(alphabet+string.ascii_lowercase) for _ in range(settings['password_length']))
        if name not in used:used.add(name);return name,password
    raise ValidationError('Could not allocate unique usernames. Try a longer format.')

def print_html(raw,rows=None,demo=False):
    t=validate_template(raw)
    if rows is None:
        rows=[{'username':'1234567890' if t['mode']=='pin' else 'NS7K2PM9AX','password':'1234567890' if t['mode']=='pin' else 'vN8dK3tP7hQ2','credential_mode':t['mode'],'allowance':'1d','policy':'elapsed','profile':'Sample profile'}]
        demo=True
    if not isinstance(rows,list) or len(rows)>100:raise ValidationError('Render at most 100 vouchers.')
    cards=[]
    for row in rows:
        if not isinstance(row,dict):raise ValidationError('Invalid voucher record.')
        username=str(row.get('username',row.get('pin','')));password=str(row.get('password',row.get('pin','')))
        if not username or not password or max(len(username),len(password))>128:raise ValidationError('Missing or oversized voucher credentials.')
        if t['mode']=='pin' and username!=password:raise ValidationError('PIN layout cannot hide a separate password. Select username/password layout.')
        fields=f'<label>PIN</label><strong>{escape(username)}</strong>' if t['mode']=='pin' else f'<label>Username</label><strong>{escape(username)}</strong><label>Password</label><strong>{escape(password)}</strong>'
        hint='Enter this PIN in the PIN login page. On a two-field page, use it in both fields.' if t['mode']=='pin' else 'Enter the username and password exactly as printed.'
        extras=''
        if t['show_policy']:extras+=f'<p>{escape(str(row.get("allowance","")))} · {escape(str(row.get("policy","connected")))} validity</p>'
        if t['show_profile']:extras+=f'<p>Profile: {escape(str(row.get("profile","")))}</p>'
        cards.append(f'<article><header>{escape(t["brand"])} {"• SAMPLE / DEMO" if demo else ""}</header><h2>{escape(t["heading"])}</h2><p>{escape(t["network"])}</p>{fields}{extras}<p class="price">{escape(t["price"])}</p><small>{hint}</small><p>{escape(t["contact"])}</p><footer>{escape(t["footer"])}</footer></article>')
    width={'a4':'210mm','thermal58':'58mm','thermal80':'80mm'}[t['layout']]
    columns=t['columns'] if t['layout']=='a4' else 1
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(t['name'])}</title><style>
*{{box-sizing:border-box}}body{{font:14px system-ui,sans-serif;color:#18333e;margin:0;padding:8mm;background:#edf3f5}}main{{max-width:{width};margin:auto;display:grid;grid-template-columns:repeat({columns},minmax(0,1fr));gap:4mm}}article{{background:{t['background']};border:1px dashed {t['accent']};border-top:5px solid {t['accent']};padding:5mm;break-inside:avoid;overflow-wrap:anywhere}}header{{font-size:10px;font-weight:800;letter-spacing:.4px;color:{t['accent']}}}h2{{font-size:17px;margin:10px 0}}label{{font-size:11px;display:block;margin-top:10px}}strong{{display:block;font:700 19px ui-monospace,monospace;letter-spacing:1px}}p{{font-size:12px;margin:8px 0}}small,footer{{font-size:10px}}footer{{border-top:1px solid #ddd;padding-top:8px;margin-top:10px}}.price{{font-weight:bold}}@page{{size:{'A4' if t['layout']=='a4' else 'auto'};margin:8mm}}@media print{{body{{background:white;padding:0}}}}@media screen and (max-width:500px){{main{{grid-template-columns:1fr}}}}
</style></head><body><main>{''.join(cards)}</main></body></html>'''

def portal_files(raw):
    t=validate_template(raw)
    fields='<label for="ticket-pin">Ticket PIN</label><input id="ticket-pin" name="ticket-pin" inputmode="numeric" autocomplete="off" required maxlength="16" pattern="[0-9]{8,16}">' if t['mode']=='pin' else '<label for="ticket-user">Username</label><input id="ticket-user" autocomplete="username" required maxlength="128"><label for="ticket-pass">Password</label><input id="ticket-pass" type="password" autocomplete="current-password" required maxlength="128">'
    extract="var username=document.getElementById('ticket-pin').value.trim();var password=username;" if t['mode']=='pin' else "var username=document.getElementById('ticket-user').value.trim();var password=document.getElementById('ticket-pass').value;"
    page='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Internet login</title><link rel="stylesheet" href="portal.css"></head><body><main><header>BRAND</header><h1>HEADING</h1><p>NETWORK</p>$(if error)<p class="error">Login failed. Check your ticket or contact the attendant.</p>$(endif)<p id="login-error" class="error" role="alert"></p><form id="ticket-form">FIELDS<button type="submit">Connect to internet</button></form><form id="router-login" action="$(link-login-only)" method="post"><input type="hidden" name="username"><input type="hidden" name="password"><input type="hidden" name="popup" value="false"></form><p>CONTACT</p><footer>FOOTER</footer></main>$(if chap-id)<script src="md5.js"></script>$(endif)<script>
document.getElementById('ticket-form').addEventListener('submit',function(event){event.preventDefault();EXTRACT
var form=document.getElementById('router-login');form.action=location.protocol+'//'+location.host+'/login';form.elements.username.value=username;
$(if chap-id)
if(typeof hexMD5!=='function'){document.getElementById('login-error').textContent='Login support file is missing. Contact the attendant.';return;}
form.elements.password.value=hexMD5('$(chap-id)'+password+'$(chap-challenge)');
$(else)
if(location.protocol!=='https:'){document.getElementById('login-error').textContent='Secure login is unavailable. Contact the attendant.';return;}
form.elements.password.value=password;
$(endif)
form.submit();});
</script></body></html>'''
    replacements={'BRAND':escape(t['brand']),'HEADING':escape(t['heading']),'NETWORK':escape(t['network']),'CONTACT':escape(t['contact']),'FOOTER':escape(t['footer']),'FIELDS':fields,'EXTRACT':extract}
    page=re.sub(r'\b(BRAND|HEADING|NETWORK|CONTACT|FOOTER|FIELDS|EXTRACT)\b',lambda m:replacements[m.group(0)],page)
    css=f'''*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#102c39;font:16px system-ui,sans-serif;color:#153640;padding:20px}}main{{width:100%;max-width:420px;background:{t['background']};border-radius:14px;padding:30px;border-top:7px solid {t['accent']}}}header{{font-weight:800;font-size:13px;color:{t['accent']}}}h1{{font-size:26px}}label{{display:block;margin:18px 0 7px}}input{{font:inherit;width:100%;padding:13px;border:1px solid #8299a3;border-radius:6px}}button{{width:100%;padding:14px;margin:22px 0;background:{t['accent']};color:white;border:0;border-radius:6px;font-size:16px;font-weight:700}}footer,p{{font-size:14px;line-height:1.5}}.error{{color:#a63623}}'''
    return {'login.html':page,'flogin.html':page,'portal.css':css}

def portal_package(raw):
    t=validate_template(raw);folder='nelsonict-'+t['mode']
    files=portal_files(t)
    instructions=f'''NELSONICT PORTAL INSTALLATION — {t['mode']}\n\n1. In WinBox, identify IP > Hotspot > Server Profiles > HTML Directory for the target server. Download a backup of that entire folder.\n2. On your computer COPY that entire folder to a NEW folder named {folder}. Keep the original router folder unchanged.\n3. Replace login.html and flogin.html and add portal.css using the files in this package. KEEP the original md5.js, alogin.html, status.html, logout.html, redirect.html and other default files. This package is an overlay, not a complete RouterOS hotspot directory.\n4. Upload the completed new folder through WinBox Files. On flash-based routers use flash/{folder}. Keep all original support files.\n5. In Nelsonict Template Editor, choose the hotspot server and enter the actual uploaded directory, then Check installation. Review every affected server if the profile is shared.\n6. Confirm INSTALL PORTAL to switch the HTML Directory. The application records the prior directory and provides restore. No authentication-method or credential conversion is performed.\n7. Test a new customer login. PIN mode requires username=password. Username/password mode accepts separate credentials (PIN users can enter the same PIN twice). The page supports RouterOS HTTP-CHAP using its original md5.js, or HTTPS. It refuses plaintext HTTP-PAP fallback.\n8. If login fails, restore the previous directory in the app or in WinBox. Do not delete the old folder.\n\nPrinted ticket appearance is independent of portal activation. Customize and save both deliberately. No real-router compatibility claim is made until acceptance testing.\n'''
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
        for name,content in files.items():z.writestr(folder+'/'+name,content)
        z.writestr('INSTALL.txt',instructions);z.writestr('template.json',json.dumps(t,indent=2))
    return {'filename':folder+'-portal.zip','base64':base64.b64encode(stream.getvalue()).decode(),'directory':folder}

REQUIRED_FILES=('login.html','flogin.html','portal.css','md5.js','alogin.html','status.html','logout.html','redirect.html')
def portal_plan(router,server_name,directory,mode):
    if mode not in ('pin','credentials'):raise ValidationError('Select a portal mode.')
    if not isinstance(directory,str) or not re.fullmatch(r'(?:flash/)?[A-Za-z0-9_-]{1,48}',directory):raise ValidationError('Use a single folder name, optionally prefixed with flash/.')
    servers=router.call('ip/hotspot')
    server=next((x for x in servers if x.get('name')==server_name),None)
    if not server:raise ValidationError('Select an existing hotspot server.')
    profile=next((x for x in router.call('ip/hotspot/profile') if x.get('name')==server.get('profile')),None)
    if not profile:raise ValidationError('Hotspot server profile not found.')
    if profile.get('html-directory-override') not in (None,'','none'):raise ValidationError('This profile has an HTML directory override. Review it in WinBox before using the installer.')
    if not set(str(profile.get('login-by','')).split(',')) & {'http-chap','https'}:raise ValidationError('Profile must already allow HTTP-CHAP or HTTPS. Authentication settings are not changed automatically.')
    names={x.get('name') for x in router.call('file')}
    missing=[f for f in REQUIRED_FILES if directory+'/'+f not in names]
    if missing:raise ValidationError('Upload the completed portal folder first. Missing: '+', '.join(missing))
    before=profile.get('html-directory','hotspot')
    if before==directory:raise ValidationError('This folder is already selected. Use a new folder for each update so rollback remains possible.')
    return {'profile_id':profile['.id'],'profile_name':profile['name'],'before':before,'directory':directory,'mode':mode,
            'server':server_name,'affected_servers':[x['name'] for x in servers if x.get('profile')==profile['name']],
            'login_by':profile.get('login-by',''),
            'warnings':['Keep the old folder and a router backup. File presence checks do not validate uploaded file contents.',
                        'Changing a shared server profile changes the login page for every listed server.',
                        'PIN mode requires username and password to be identical; existing separate-password tickets will not work on that page.',
                        'Template changes do not change existing credentials or ticket expiry.']}
