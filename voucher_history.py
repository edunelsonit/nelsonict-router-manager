"""Private local voucher archive, scoped to the connected router."""
import copy
from pricing import PriceStore

class VoucherHistory:
    def __init__(self,directory,host,identity):self.store=PriceStore(directory,host,identity)
    def read(self):return self.store.read()
    def write(self,records):self.store.write(records)

def confirmed(record):
    return [copy.deepcopy(row) for row in record['vouchers'] if row.get('creation_state')=='created' and row.get('lifecycle','active')=='active']

def select(records,batch_id=None,profile=None):
    rows=[]
    for record in records.values():
        if batch_id and record['batch']!=batch_id:continue
        for row in confirmed(record):
            if profile and profile not in (row.get('base_profile'),row.get('profile')):continue
            rows.append(row)
    return rows

def summaries(records):
    return [{'batch':r['batch'],'created':r['created'],'count':len(confirmed(r)),
             'profiles':sorted({v.get('base_profile',v['profile']) for v in confirmed(r)}),
             'incomplete':any(v.get('creation_state')!='created' for v in r['vouchers'])}
            for r in sorted(records.values(),key=lambda r:r['created'],reverse=True)]

def revoke(records,entries):
    """Keep history, but quarantine any account selected for rollback before deletion."""
    changed=False
    for entry in entries:
        if entry.get('path')!='ip/hotspot/user' or entry.get('state') not in ('created','rolled-back','uncertain'):continue
        values=entry.get('values',{});comment=values.get('comment','')
        from expiry import decode
        from core import ValidationError
        try:policy=decode(comment)
        except ValidationError:policy=None
        batch=policy['batch'] if policy else comment.removeprefix('ns-batch-')
        for row in records.get(batch,{}).get('vouchers',[]):
            if row['username']==values.get('name') and row.get('lifecycle','active')=='active':
                row['lifecycle']='revoked';changed=True
    return changed
