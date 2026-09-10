"""Saved router connection settings; passwords are never persisted."""
import secrets
from core import Router, ValidationError
from pricing import PriceStore

class LocationStore:
    def __init__(self,directory):self.store=PriceStore(directory,'saved-router-locations','v1')
    def list(self):return sorted(self.store.read().values(),key=lambda x:x['name'].casefold())
    def get(self,ident):
        row=self.store.read().get(ident)
        if not row:raise ValidationError('Saved location not found. Refresh the list.')
        return row
    def save(self,data):
        name=data.get('name','').strip()
        if not name or len(name)>80 or any(ord(c)<32 for c in name):raise ValidationError('Enter a location name of 1–80 characters.')
        r=Router(data.get('host',''),data.get('username',''),'validation-only',data.get('port'),data.get('fingerprint',''),data.get('transport','api'))
        rows=self.store.read();ident=data.get('id')
        if ident and ident not in rows:raise ValidationError('Saved location no longer exists.')
        if not ident and len(rows)>=100:raise ValidationError('Maximum 100 saved locations.')
        ident=ident or secrets.token_hex(12)
        row={'id':ident,'name':name,'host':r.host,'username':r.username,'port':r.port,'transport':r.transport,'fingerprint':r.fingerprint}
        rows[ident]=row;self.store.write(rows);return row
    def delete(self,ident):
        rows=self.store.read()
        if ident not in rows:raise ValidationError('Saved location not found.')
        del rows[ident];self.store.write(rows)
