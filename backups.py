"""Bounded JSON backups of application data; no router configuration writes."""
import json, os, re, time
from pathlib import Path
from core import ValidationError, Router
from templates import validate_template
from pricing import validate_price

LIMIT=12*1024*1024
PATTERN=r'(templates/[A-Za-z0-9_-]{1,40}|(?:prices|vouchers|locations)/[0-9a-f]{64})\.json'
def validate(bundle):
    if not isinstance(bundle,dict) or bundle.get('format')!='nelsonict-backup-1' or not isinstance(bundle.get('files'),dict):raise ValidationError('Invalid Nelsonict backup.')
    if len(json.dumps(bundle).encode())>LIMIT or len(bundle['files'])>2000:raise ValidationError('Backup is too large.')
    for name,value in bundle['files'].items():
        if not re.fullmatch(PATTERN,name) or not isinstance(value,dict):raise ValidationError('Invalid backup path or record.')
        if name.startswith('templates/'):
            validate_template(value)
            if Path(name).stem!=value.get('id'):raise ValidationError('Template filename does not match its ID.')
        elif name.startswith('prices/'):
            for price in value.values():
                if not isinstance(price,dict) or validate_price(price.get('amount'),price.get('currency'))!=price:raise ValidationError('Invalid saved price.')
        elif name.startswith('locations/'):
            for ident,row in value.items():
                if not isinstance(row,dict) or set(row)!={'id','name','host','username','port','transport','fingerprint'} or row['id']!=ident or not re.fullmatch('[0-9a-f]{24}',ident):raise ValidationError('Invalid location record.')
                Router(row['host'],row['username'],'validation',row['port'],row['fingerprint'],row['transport'])
        else:
            for key,record in value.items():
                if not isinstance(record,dict) or record.get('batch')!=key or not re.fullmatch('[0-9a-f]{8}',key) or not isinstance(record.get('created'),(float,int)) or not isinstance(record.get('vouchers'),list):raise ValidationError('Invalid voucher archive.')
                for row in record['vouchers']:
                    if not isinstance(row,dict) or row.get('batch')!=key or any(not isinstance(row.get(k),str) or not 1<=len(row[k])<=128 for k in ('username','password','profile')) or row.get('creation_state') not in ('pending','created','uncertain','not-created'):raise ValidationError('Invalid archived voucher.')
    return bundle

def export(root):
    files={}
    for group in ('templates','prices','vouchers','locations'):
        directory=root/group
        if directory.is_symlink():raise ValidationError('Symlinked data directories are unsupported.')
        for path in directory.glob('*.json'):
            if path.is_symlink():raise ValidationError('Symlinked data files are unsupported.')
            files[group+'/'+path.name]=json.loads(path.read_text(encoding='utf-8'))
    return validate({'format':'nelsonict-backup-1','created':time.time(),'files':files})

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temp=path.with_suffix('.restore-tmp')
    if path.is_symlink() or path.parent.is_symlink() or temp.is_symlink():raise ValidationError('Symlinked destination refused.')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as out:json.dump(value,out);out.flush();os.fsync(out.fileno())
    os.replace(temp,path)

def restore(root,bundle):
    validate(bundle);before=export(root)
    recovery=root/'recovery'/('before-restore-'+str(time.time_ns())+'.json')
    write(recovery,before)
    changed=[]
    try:
        for name,value in bundle['files'].items():
            # Track intent so rollback covers errors after replacement too.
            changed.append(name);write(root/name,value)
    except Exception:
        for name in reversed(changed):
            if name in before['files']:write(root/name,before['files'][name])
            elif (root/name).exists() and not (root/name).is_symlink():(root/name).unlink()
        raise
    return {'restored':len(changed),'recovery':recovery.name}
