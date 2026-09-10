"""Local, router-scoped profile prices; money is stored as decimal text."""
import hashlib
import json
import os
from pathlib import Path
import re
from decimal import Decimal
from core import ValidationError

def validate_price(amount,currency):
    if not isinstance(currency,str) or not re.fullmatch(r'[A-Z]{3}',currency):
        raise ValidationError('Use a three-letter currency code, for example NGN or USD.')
    if not isinstance(amount,str) or not re.fullmatch(r'(?:0|[1-9][0-9]{0,8})(?:\.[0-9]{1,2})?',amount):
        raise ValidationError('Enter a price from 0 to 999999999.99 with at most two decimal places.')
    value=Decimal(amount)
    return {'amount':format(value,'.2f'),'currency':currency,'label':currency+' '+format(value,',.2f')}

class PriceStore:
    def __init__(self,directory,host,identity):
        key=hashlib.sha256(json.dumps([host,identity]).encode()).hexdigest()
        self.path=Path(directory)/(key+'.json')
    def read(self):
        return json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {}
    def write(self,values):
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        temp=self.path.with_suffix('.tmp')
        fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as out:
            json.dump(values,out,ensure_ascii=False);out.flush();os.fsync(out.fileno())
        os.replace(temp,self.path)

def profile_key(profile):return json.dumps([profile.get('.id'),profile['name']])
