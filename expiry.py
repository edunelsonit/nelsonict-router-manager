"""Versioned router-owned ticket policies and a pure Python dashboard evaluator.

RouterOS scripts need acceptance testing on the exact firmware before production.
Comments are a machine-owned record: ns2,mode,duration,offset,cutoff,fixed,fallback,first,due,batch
"""
from datetime import datetime, timezone
import re
from core import ValidationError

MODES = {'elapsed','business','startup','connected','fixed'}
SECONDS = {'1d':86400,'3d':259200,'1w':604800,'28d':2419200}
ENGINE_NAME = 'ns-expiry-v2'

def ros_seconds(value):
    """Read RouterOS 1w2d3h4m5s and 1w2d03:04:05 representations strictly."""
    value = str(value or '0s')
    if value == '0': return 0
    match = re.fullmatch(r'(?:(\d+)w)?(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?', value)
    if match and any(v is not None for v in match.groups()):
        return sum(float(n or 0)*scale for n,scale in zip(match.groups(),[604800,86400,3600,60,1]))
    match = re.fullmatch(r'(?:(\d+)w)?(?:(\d+)d)?(\d+):(\d{2}):(\d{2}(?:\.\d+)?)',value)
    if match:
        w,d,h,m,s=match.groups()
        if int(m)>59 or float(s)>=60: raise ValidationError('Invalid router duration.')
        return int(w or 0)*604800+int(d or 0)*86400+int(h)*3600+int(m)*60+float(s)
    raise ValidationError('Unrecognized RouterOS duration: ' + value)

def wall_seconds(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{2}:\d{2}',value):
        raise ValidationError('Enter a time as HH:MM.')
    h,m=map(int,value.split(':'))
    if h>23 or m>59: raise ValidationError('Invalid local clock time.')
    return h*3600+m*60

def policy_from_form(data,now):
    mode=data.get('expiry_mode','connected')
    if mode not in MODES: raise ValidationError('Choose a supported expiry policy.')
    duration=data.get('duration','1d')
    if duration not in SECONDS: raise ValidationError('Unsupported ticket duration.')
    offset=int(data.get('utc_offset',60))
    if not -720<=offset<=840: raise ValidationError('UTC offset must be between -720 and +840 minutes.')
    fixed=0
    if mode=='fixed':
        try:
            stamp=datetime.fromisoformat(data.get('fixed_at','').replace('Z','+00:00'))
            if stamp.tzinfo is None: raise ValueError()
            fixed=int(stamp.timestamp())
        except (ValueError,TypeError):raise ValidationError('Fixed expiry needs an ISO date/time with an explicit UTC offset.')
        if not now<fixed<=now+366*86400: raise ValidationError('Fixed expiry must be in the next 366 days.')
    return {'mode':mode,'duration':SECONDS[duration], 'offset':offset,
            'cutoff':wall_seconds(data.get('closing_time','23:59')),'fixed':fixed,
            'fallback':wall_seconds(data.get('fallback_time','10:10')),'first':0,'due':fixed,'batch':''}

def encode(p):
    return ','.join(str(x) for x in ['ns2',p['mode'],p['duration'],p['offset'],p['cutoff'],p['fixed'],p['fallback'],p['first'],p['due'],p['batch']])

def decode(comment):
    if not str(comment).startswith('ns2,'): return None
    try:
        a=comment.split(',')
        if len(a)!=10 or a[1] not in MODES or not re.fullmatch('[0-9a-f]{8}',a[9]): raise ValueError()
        p=dict(zip(['mode','duration','offset','cutoff','fixed','fallback','first','due','batch'],a[1:]))
        for k in ('duration','offset','cutoff','fixed','fallback','first','due'):p[k]=int(p[k])
        if not 1<=p['duration']<=366*86400 or not -720<=p['offset']<=840:raise ValueError()
        if not 0<=p['cutoff']<86400 or not 0<=p['fallback']<86400:raise ValueError()
        if any(p[k]<0 for k in ('fixed','first','due')):raise ValueError()
        return p
    except (ValueError,TypeError):raise ValidationError('Damaged ticket policy. Inspect the router comment before changing access.')

def deadline(p,now,boot):
    """Return a durable due date; startup due only becomes final on a later day."""
    if p['due']:return p['due']
    if p['mode']=='fixed':return p['fixed']
    first=p['first']
    if not first:return None
    shift=p['offset']*60
    day=(first+shift)//86400
    if p['mode']=='elapsed':return first+p['duration']
    if p['mode']=='business':
        due=day*86400+p['cutoff']-shift
        return due if due>first else due+86400
    if p['mode']=='startup' and (now+shift)//86400>day:
        return int(boot)+600 if (boot+shift)//86400>day else (day+1)*86400+p['fallback']-shift
    return None

def describe_user(user,sessions,now,boot,clock_ok):
    own_sessions=[s for s in sessions if s.get('user')==user.get('name')]
    result={'first_login':None,'expires_at':None,'policy':'legacy','expiry_state':'unknown',
            'overdue_active':False,'session_count':len(own_sessions),'current_session_started':None,
            'policy_error':None,'expiry_reason':None}
    if own_sessions and clock_ok:
        try:result['current_session_started']=int(now-max(ros_seconds(x.get('uptime')) for x in own_sessions))
        except ValidationError:pass
    try:
        p=decode(user.get('comment',''))
        if p:
            result['policy']=p['mode'];result['first_login']=p['first'] or None
            if p['mode']!='connected' and not clock_ok:
                result['expiry_state']='clock-unverified';return result
            if p['first']>now and clock_ok:
                result['expiry_state']='clock-unverified';return result
            due=deadline(p,now,boot)
            result['expires_at']=due
            if p['mode']=='connected':
                expired=ros_seconds(user.get('uptime'))>=p['duration']
                result['expiry_reason']='Connected-time allowance exhausted' if expired else None
            else:
                expired=bool(due and now>=due)
                result['expiry_reason']='Ticket deadline passed' if expired else None
            result['expiry_state']='expired' if expired else ('first-login-unrecorded' if ros_seconds(user.get('uptime'))>0 else 'unused') if not p['first'] else 'valid'
        else:
            limit=ros_seconds(user.get('limit-uptime','0s'))
            expired=bool(limit and ros_seconds(user.get('uptime'))>=limit)
            result['expiry_state']='expired' if expired else 'legacy-unknown'
            result['expiry_reason']='Connected-time allowance exhausted' if expired else None
        result['overdue_active']=expired and bool(own_sessions)
    except ValidationError as e:
        result['policy_error']=str(e);result['expiry_state']='invalid-policy'
    return result

# Both hook and scheduler run the same deadline arithmetic. No user input is inserted into script source.
_HEADER = '''# Nelsonict expiry v2; read/write only; machine-owned ns2 comments
:local synced ([/system ntp client get status] = "synchronized");
:local now ([:tonsec [:timestamp]] / 1000000000);
:local boot ($now - ([:tonsec [/system resource get uptime]] / 1000000000));
'''
_BODY = '''
    :local comment [/ip hotspot user get $uid comment];
    :if ([:pick $comment 0 4] = "ns2,") do={
      :do {
        :local m [:toarray $comment];
        :if ([:len $m] != 10) do={ :error "Invalid Nelsonict policy"; };
        :local mode ($m->1);
        :if (($mode != "elapsed") && ($mode != "business") && ($mode != "startup") && ($mode != "connected") && ($mode != "fixed")) do={ :error "Unknown policy"; };
        :local duration [:tonum ($m->2)];
        :local shift ([:tonum ($m->3)] * 60);
        :local cutoff [:tonum ($m->4)];
        :local fixed [:tonum ($m->5)];
        :local fallback [:tonum ($m->6)];
        :local first [:tonum ($m->7)];
        :local due [:tonum ($m->8)];
        :if (([:typeof $duration] != "num") || ([:typeof $shift] != "num") || ([:typeof $cutoff] != "num") || ([:typeof $fallback] != "num") || ([:typeof $first] != "num") || ([:typeof $due] != "num") || ([:typeof $fixed] != "num")) do={ :error "Invalid policy numbers"; };
        :if (($duration < 1) || ($duration > 31622400) || ($shift < -43200) || ($shift > 50400) || ($cutoff < 0) || ($cutoff >= 86400) || ($fallback < 0) || ($fallback >= 86400) || ($first < 0) || ($due < 0) || ($fixed < 0)) do={ :error "Invalid policy ranges"; };
        :local username [/ip hotspot user get $uid name];
        :local deny false;
        :if (($mode != "connected") && (!$synced || ($now < 1577836800) || ($first > $now))) do={
          :set deny true;
        } else={
          ACTIVATE
          :if (($first > 0) && ($due = 0)) do={
            :local day (($first + $shift) / 86400);
            :if ($mode = "elapsed") do={ :set due ($first + $duration); };
            :if ($mode = "business") do={
              :set due (($day * 86400) + $cutoff - $shift);
              :if ($due <= $first) do={ :set due ($due + 86400); };
            };
            :if (($mode = "startup") && ((($now + $shift) / 86400) > $day)) do={
              :if ((($boot + $shift) / 86400) > $day) do={ :set due ($boot + 600); } else={
                :set due ((($day + 1) * 86400) + $fallback - $shift);
              };
            };
          };
          :if ($mode = "fixed") do={ :set due $fixed; };
          :local next ("ns2," . $mode . "," . ($m->2) . "," . ($m->3) . "," . ($m->4) . "," . ($m->5) . "," . ($m->6) . "," . $first . "," . $due . "," . ($m->9));
          :if ($next != $comment) do={ /ip hotspot user set $uid comment=$next; };
          :local exhausted false;
          :if ($mode = "connected") do={
            :set exhausted (([:tonsec [/ip hotspot user get $uid uptime]] / 1000000000) >= $duration);
          };
          :if ((($due > 0) && ($now >= $due)) || $exhausted) do={
            /ip hotspot user set $uid disabled=yes;
            :set deny true;
          };
        };
        :if ([/ip hotspot user get $uid disabled]) do={ :set deny true; };
        :if ($deny) do={
          /ip hotspot active remove [find where user=$username];
          /ip hotspot cookie remove [find where user=$username];
        };
      } on-error={
        :local failedName [/ip hotspot user get $uid name];
        /ip hotspot active remove [find where user=$failedName];
        /ip hotspot cookie remove [find where user=$failedName];
        :log warning "Nelsonict expiry: inspect ticket policy or script permissions";
      };
    };
'''
ACTIVATION = ''':if (($first = 0) && $synced && ($now >= 1577836800)) do={ :set first $now; };'''
HOOK_GUARD = '''
:if (!$synced || ($now < 1577836800)) do={
  /ip hotspot active remove [find where user=$user];
  /ip hotspot cookie remove [find where user=$user];
  :error "Nelsonict login paused until NTP is synchronized";
};
'''
HOOK_SOURCE = _HEADER + HOOK_GUARD + ':foreach uid in=[/ip hotspot user find where name=$user] do={\n' + _BODY.replace('ACTIVATE',ACTIVATION) + '\n};'
SCHEDULER_SOURCE = _HEADER + ':foreach uid in=[/ip hotspot user find] do={\n' + _BODY.replace('ACTIVATE','# First activation is captured only by the login hook.') + '\n};'

def engine_operations(router):
    current=router.call('system/scheduler')
    matches=[x for x in current if x.get('name')==ENGINE_NAME]
    if matches:
        x=matches[0]
        if x.get('on-event')!=SCHEDULER_SOURCE or x.get('disabled') in ('true','yes') or ros_seconds(x.get('interval'))!=30:
            raise ValidationError('The Nelsonict expiry scheduler differs or is disabled. Inspect it in WinBox before creating tickets.')
        return []
    return [{'path':'system/scheduler','values':{'name':ENGINE_NAME,'interval':'30s','start-time':'startup',
             'on-event':SCHEDULER_SOURCE,'policy':'read,write','disabled':'no','comment':'Nelsonict expiry v2'},
             'label':'Install router expiry checker (every 30 seconds)'}]

def expiry_profile(base,batch):
    if base.get('on-login') and base.get('on-login') != HOOK_SOURCE:
        raise ValidationError('This profile has a custom login hook. Use a separate plain profile; existing automation will not be overwritten.')
    if base.get('on-logout'):
        raise ValidationError('This profile has logout automation. Use a separate plain profile for managed-expiry tickets.')
    values={k:base[k] for k in ('rate-limit','shared-users','address-pool','session-timeout','idle-timeout','keepalive-timeout','status-autorefresh','transparent-proxy','incoming-filter','outgoing-filter','incoming-packet-mark','outgoing-packet-mark','address-list','parent-queue','queue-type','insert-queue-before','open-status-page') if k in base}
    values.update({'name':'ns2-'+batch,'on-login':HOOK_SOURCE,'add-mac-cookie':'no'})
    return {'path':'ip/hotspot/user/profile','values':values,'label':'Create a dedicated expiry-aware ticket profile'}

def router_clock(router,resource):
    """Never treat the management computer's clock as verified router time."""
    try:
        ntp=router.call('system/ntp/client'); clock=router.call('system/clock')
        if isinstance(ntp,list):ntp=ntp[0]
        if isinstance(clock,list):clock=clock[0]
        raw=clock.get('gmt-offset','+00:00')
        if re.fullmatch(r'-?\d+',str(raw)):
            offset=int(raw)
            if offset>2**31:offset-=2**32
        else:
            sign=-1 if str(raw).startswith('-') else 1
            offset=sign*ros_seconds(str(raw).lstrip('+-') + (':00' if str(raw).count(':')==1 else ''))
        stamp=datetime.fromisoformat(clock['date']+'T'+clock['time']).replace(tzinfo=timezone.utc).timestamp()-offset
        ok=ntp.get('status')=='synchronized' and stamp>=1577836800
        return {'verified':ok,'now':int(stamp),'boot':int(stamp-ros_seconds(resource['uptime'])),
                'ntp_status':ntp.get('status','unknown')}
    except (ValidationError,ValueError,KeyError,IndexError,TypeError,OSError):
        return {'verified':False,'now':0,'boot':0,'ntp_status':'unavailable'}
