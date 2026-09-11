"""SQLite voucher inventory and sale ledger. No router/voucher passwords stored."""
import hashlib,json,os,re,sqlite3,time,uuid
from datetime import date
from decimal import Decimal
from core import ValidationError
from pricing import validate_price

INVENTORY=('id','scope','batch','username','profile','amount','currency','payment_ref','test','available')
EVENTS=('id','voucher_id','scope','amount','currency','method','sold_at','voided_at')
def scope_key(location,identity):return hashlib.sha256(json.dumps([location,identity]).encode()).hexdigest()
def voucher_key(scope,batch,name):return hashlib.sha256(json.dumps([scope,batch,name]).encode()).hexdigest()
def money(amount,currency):
    p=validate_price(amount,currency);return int(Decimal(p['amount'])*100),p['currency']

def validate_dump(data):
    if not isinstance(data,dict) or set(data)!= {'version','inventory','events'} or data['version']!=1:raise ValidationError('Invalid sales backup.')
    ids=set();active=set();scope_ids={}
    for table,columns in [('inventory',INVENTORY),('events',EVENTS)]:
        rows=data[table]
        if not isinstance(rows,list) or len(rows)>100000:raise ValidationError('Invalid sales rows.')
        seen=set()
        for r in rows:
            if not isinstance(r,dict) or set(r)!=set(columns):raise ValidationError('Invalid sales columns.')
            if not isinstance(r['id'],str) or not 1<=len(r['id'])<=64 or r['id'] in seen:raise ValidationError('Invalid sales ID.')
            seen.add(r['id'])
            if not isinstance(r['scope'],str) or not re.fullmatch('[0-9a-f]{64}',r['scope']):raise ValidationError('Invalid sales scope.')
            if r['amount'] is not None and (type(r['amount']) is not int or not 0<=r['amount']<=99999999999):raise ValidationError('Invalid sale amount.')
            if not isinstance(r['currency'],str) or not re.fullmatch('[A-Z]{3}|',r['currency']):raise ValidationError('Invalid currency.')
            if table=='inventory':
                for k in ('batch','username','profile','payment_ref'):
                    if not isinstance(r[k],str) or len(r[k])>256:raise ValidationError('Invalid inventory field.')
                if r['test'] not in (0,1) or r['available'] not in (0,1) or r['id']!=voucher_key(r['scope'],r['batch'],r['username']):raise ValidationError('Invalid inventory identity.')
                ids.add(r['id']);scope_ids[r['id']]=r['scope']
            else:
                if r['voucher_id'] not in ids or scope_ids[r['voucher_id']]!=r['scope'] or r['amount'] is None or not r['currency']:raise ValidationError('Invalid sale link.')
                if r['method'] not in ('cash','paystack','monnify','flutterwave'):raise ValidationError('Invalid sale method.')
                for k in ('sold_at','voided_at'):
                    if r[k] is not None and (type(r[k]) is not int or not 0<=r[k]<=32503680000):raise ValidationError('Invalid sale timestamp.')
                if r['sold_at'] is None:raise ValidationError('Missing sale timestamp.')
                if r['voided_at'] is None:
                    if r['voucher_id'] in active:raise ValidationError('Duplicate active sale.')
                    active.add(r['voucher_id'])
    return data

class SalesDB:
    def __init__(self,path):
        self.path=str(path)
        if self.path!=':memory:':
            from pathlib import Path
            p=Path(path)
            if p.is_symlink() or p.parent.is_symlink():raise ValidationError('Symlinked sales database refused.')
            p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            if not p.exists():os.close(os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600))
        self.db=sqlite3.connect(self.path,timeout=10);self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        version=self.db.execute('PRAGMA user_version').fetchone()[0]
        if version not in (0,1):self.close();raise ValidationError('Unsupported sales database version.')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS inventory(id TEXT PRIMARY KEY,scope TEXT NOT NULL,batch TEXT NOT NULL,username TEXT NOT NULL,profile TEXT NOT NULL,amount INTEGER,currency TEXT NOT NULL,payment_ref TEXT NOT NULL,test INTEGER NOT NULL,available INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,voucher_id TEXT NOT NULL REFERENCES inventory(id),scope TEXT NOT NULL,amount INTEGER NOT NULL,currency TEXT NOT NULL,method TEXT NOT NULL,sold_at INTEGER NOT NULL,voided_at INTEGER);
        CREATE UNIQUE INDEX IF NOT EXISTS one_active_sale ON events(voucher_id) WHERE voided_at IS NULL;
        CREATE INDEX IF NOT EXISTS inventory_scope ON inventory(scope,profile,batch);
        CREATE INDEX IF NOT EXISTS sales_period ON events(scope,sold_at);
        PRAGMA user_version=1;
        ''')
    def close(self):self.db.close()
    def sync(self,scope,archives,orders):
        with self.db:
            self.db.execute('UPDATE inventory SET available=0 WHERE scope=?',(scope,))
            for record in archives.values():
                for v in record['vouchers']:
                    if v.get('creation_state')!='created':continue
                    ident=voucher_key(scope,v['batch'],v['username']);ref=v.get('payment_reference','');order=orders.get(ref,{})
                    test=int(v.get('payment_domain')=='test' or order.get('domain')=='test')
                    amount,currency=None,''
                    if 'price_amount' in v:
                        try:amount,currency=money(v['price_amount'],v['currency'])
                        except (ValidationError,KeyError):pass
                    values=(ident,scope,v['batch'],v['username'],v.get('base_profile',v['profile']),amount,currency,ref,test,1)
                    self.db.execute('INSERT INTO inventory VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET available=1',values)
                    if ref and not test and order.get('state')=='issued' and order.get('batch')==v['batch']:
                        self.db.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?,?,?,?,NULL)',('payment-'+ref,ident,scope,order['amount'],order['currency'],order.get('provider','paystack'),int(order.get('issued_at',order.get('verified_at',order['created'])))))
    def sell(self,scope,ident,amount=None,currency=None):
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row=self.db.execute('SELECT * FROM inventory WHERE id=? AND scope=?',(ident,scope)).fetchone()
            if not row or not row['available']:raise ValidationError('Voucher is not in this location archive.')
            if row['test'] or row['payment_ref']:raise ValidationError('Payment and test vouchers cannot be marked as cash sales.')
            if self.db.execute('SELECT 1 FROM events WHERE voucher_id=? AND voided_at IS NULL',(ident,)).fetchone():raise ValidationError('Voucher already has a recorded sale.')
            if amount in (None,''):
                cents,code=row['amount'],row['currency']
                if cents is None or not code:raise ValidationError('Enter the actual sale amount and currency for this unpriced voucher.')
            else:cents,code=money(amount,currency)
            self.db.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?,NULL)',(uuid.uuid4().hex,ident,scope,cents,code,'cash',int(time.time())))
    def unsell(self,scope,ident):
        with self.db:
            row=self.db.execute('SELECT * FROM events WHERE voucher_id=? AND scope=? AND voided_at IS NULL',(ident,scope)).fetchone()
            if not row:raise ValidationError('No active sale to correct.')
            if row['method']!='cash':raise ValidationError('Online payments cannot be reversed here. Handle refunds with the provider.')
            self.db.execute('UPDATE events SET voided_at=? WHERE id=?',(int(time.time()),row['id']))
    def report(self,scope,filters):
        period=filters.get('period','daily');offset=int(filters.get('utc_offset',60))
        if period not in ('daily','monthly') or not -720<=offset<=840:raise ValidationError('Invalid report period or UTC offset.')
        start=filters.get('from','2000-01-01');end=filters.get('to','2099-12-31')
        try:
            if date.fromisoformat(start)>date.fromisoformat(end):raise ValueError()
        except (ValueError,TypeError):raise ValidationError('Use an ordered YYYY-MM-DD date range.')
        profile=filters.get('profile','');fmt='%Y-%m-%d' if period=='daily' else '%Y-%m'
        sql='''SELECT strftime(?,e.sold_at,'unixepoch',?) period,i.profile,e.currency,COUNT(*) sold,SUM(e.amount) amount_minor FROM events e JOIN inventory i ON i.id=e.voucher_id WHERE e.scope=? AND e.voided_at IS NULL AND i.test=0 AND date(e.sold_at,'unixepoch',?) BETWEEN ? AND ? AND (?='' OR i.profile=?) GROUP BY period,i.profile,e.currency ORDER BY period DESC,i.profile,e.currency'''
        modifier=f'{offset:+d} minutes'
        totals=[dict(r) for r in self.db.execute(sql,(fmt,modifier,scope,modifier,start,end,profile,profile))]
        return totals
    def inventory(self,scope,filters):
        status=filters.get('status','all');page=int(filters.get('page',0))
        if status not in ('all','sold','unsold','payment-pending','test') or page<0:raise ValidationError('Invalid inventory filter.')
        params=[scope];where='i.scope=? AND i.available=1'
        for key in ('profile','batch'):
            if filters.get(key):where+=' AND i.'+key+'=?';params.append(filters[key])
        if filters.get('query'):where+=" AND instr(lower(i.username),lower(?))>0";params.append(filters['query'])
        state="CASE WHEN i.test=1 THEN 'test' WHEN e.id IS NOT NULL THEN 'sold' WHEN i.payment_ref!='' THEN 'payment-pending' ELSE 'unsold' END"
        base=f' FROM inventory i LEFT JOIN events e ON e.voucher_id=i.id AND e.voided_at IS NULL WHERE {where}'
        counts={r['status']:r['n'] for r in self.db.execute('SELECT '+state+' status,COUNT(*) n'+base+' GROUP BY status',params)}
        if status!='all':base+=' AND ('+state+')=?';params.append(status)
        total=self.db.execute('SELECT COUNT(*)'+base,params).fetchone()[0]
        rows=[dict(r) for r in self.db.execute('SELECT i.*,e.amount sale_amount,e.currency sale_currency,e.method,e.sold_at,'+state+' status'+base+' ORDER BY i.batch DESC,i.username COLLATE NOCASE LIMIT 100 OFFSET ?',params+[page*100])]
        return {'vouchers':rows,'total':total,'page':page,'counts':counts}
    def export(self):return {'version':1,**{t:[dict(r) for r in self.db.execute('SELECT * FROM '+t)] for t in ('inventory','events')}}
    def restore(self,data):
        validate_dump(data)
        with self.db:
            self.db.execute('DELETE FROM events');self.db.execute('DELETE FROM inventory')
            for table,columns in [('inventory',INVENTORY),('events',EVENTS)]:
                self.db.executemany('INSERT INTO '+table+' VALUES('+','.join('?' for _ in columns)+')',[tuple(r[k] for k in columns) for r in data[table]])
