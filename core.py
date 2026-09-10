"""Nelsonict Router Manager: validated, additive RouterOS v7 operations."""
import base64
import hashlib
import http.client
import ipaddress
import json
import re
import secrets
import ssl
import time
from urllib.parse import quote

class ValidationError(Exception):
    pass

class Router:
    def __init__(self, host, username, password, port=None, fingerprint='', transport='https'):
        ip = ipaddress.ip_address(host)
        if ip.is_loopback or ip.is_multicast or ip.is_unspecified or ip.is_link_local:
            raise ValidationError('Use the router LAN or VPN IP, not a loopback, link-local, or multicast address.')
        if ip.version != 4:
            raise ValidationError('This release supports IPv4 management addresses.')
        if not username or not password or ':' in username:
            raise ValidationError('Enter a router username and password. Username cannot contain a colon.')
        if transport not in ('https','http','api','api-ssl'):raise ValidationError('Choose HTTPS, HTTP, API or API-SSL.')
        if transport in ('http','api') and not any(ip in ipaddress.ip_network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')):
            raise ValidationError('Plain HTTP/API connections are limited to private LAN/VPN IPv4 addresses.')
        self.transport=transport
        self.username,self.password=username,password
        self.host, self.port = str(ip), int({'https':443,'http':80,'api':8728,'api-ssl':8729}[transport] if port in (None,'') else port)
        if not 1 <= self.port <= 65535:
            raise ValidationError('Invalid router service port.')
        self.auth = base64.b64encode(f'{username}:{password}'.encode()).decode()
        self.fingerprint = fingerprint.replace(':', '').replace(' ', '').lower()
        if self.fingerprint and not re.fullmatch(r'[0-9a-f]{64}', self.fingerprint):
            raise ValidationError('Certificate pin must be a SHA-256 fingerprint (64 hex characters).')

    def tls_context(self):
        context=ssl.create_default_context()
        if self.fingerprint:
            context.check_hostname=False;context.verify_mode=ssl.CERT_NONE
        return context

    def verify_peer(self,certificate):
        if self.fingerprint and not secrets.compare_digest(hashlib.sha256(certificate).hexdigest(),self.fingerprint):
            raise ValidationError('Router certificate does not match the trusted fingerprint. No credentials sent.')

    def call(self, path, method='GET', data=None):
        if self.transport in ('api','api-ssl'):
            from api_transport import call, APIError
            try:return call(self,path,method,data)
            except APIError as e:raise ValidationError(str(e)) from e
        connection=(http.client.HTTPSConnection(self.host,self.port,context=self.tls_context(),timeout=15)
                    if self.transport=='https' else http.client.HTTPConnection(self.host,self.port,timeout=15))
        try:
            connection.connect()
            if self.transport=='https':self.verify_peer(connection.sock.getpeercert(binary_form=True))
            # Metadata only for broad file lists; content reads are explicitly scoped.
            endpoint=path+'?.proplist=.id,name,type,size' if path=='file' and method=='GET' else path
            connection.request(method, '/rest/' + endpoint, body=None if data is None else json.dumps(data),
                               headers={'Authorization': 'Basic ' + self.auth, 'Content-Type': 'application/json'})
            response = connection.getresponse()
            raw = response.read(4 * 1024 * 1024 + 1)
            if len(raw) > 4 * 1024 * 1024:raise ValidationError('Router response too large.')
            if response.status >= 400:
                raise ValidationError(f'Router returned HTTP {response.status} for {method} {path}. Check permissions and RouterOS support.')
            return json.loads(raw) if raw else {}
        finally:connection.close()

PATHS = ['system/resource', 'system/identity', 'interface', 'interface/bridge/port',
         'ip/address', 'ip/pool', 'ip/dhcp-client', 'ip/dhcp-server', 'ip/dhcp-server/network',
         'ip/firewall/filter', 'ip/firewall/nat', 'ip/hotspot', 'ip/hotspot/profile',
         'ip/hotspot/user/profile']

def snapshot(router):
    result = {p: router.call(p) for p in PATHS}
    resources = result['system/resource']
    resource = resources[0] if isinstance(resources, list) else resources
    if not str(resource.get('version', '')).startswith('7.'):
        raise ValidationError('This application requires RouterOS v7; v6 changes are blocked.')
    return result

def digest(state):
    # Exclude traffic and resource counters; detect configuration changes and dynamic address changes.
    fields = ('name', 'type', 'interface', 'bridge', 'address', 'ranges', 'network', 'disabled',
              'chain', 'action', 'src-address', 'dst-address', 'in-interface', 'out-interface',
              'connection-state', 'hotspot', 'protocol', 'dst-port', 'place-before',
              'address-pool', 'profile', 'rate-limit', 'shared-users', 'comment', 'dynamic')
    stable = {p: [{k: row[k] for k in ('.id',) + fields if k in row} for row in rows]
              for p, rows in state.items() if p not in ('system/resource', 'system/identity')}
    return hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()

def safe_name(value, label='Name'):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,32}', value):
        raise ValidationError(f'{label} must be 1–32 letters, digits, underscores or hyphens.')
    return value

def build_plan(state, cfg):
    scenario = cfg.get('scenario', 'existing')
    if scenario not in ('existing', 'hotspot', 'office'):
        raise ValidationError('Unknown setup scenario.')
    prefix = 'ns-' + safe_name(cfg.get('name', 'site'), 'Site name')
    upload, download = int(cfg.get('upload', 5)), int(cfg.get('download', 10))
    if not 1 <= upload <= 10000 or not 1 <= download <= 10000:
        raise ValidationError('Speed must be between 1 and 10,000 Mbps.')
    operations = []
    def add(path, values, label):
        operations.append({'path': path, 'values': values, 'label': label})
    if any(str(row.get('name', '')).startswith(prefix + '-') for p in PATHS for row in (state[p] if isinstance(state[p], list) else [])):
        raise ValidationError('This site prefix already exists. Use voucher management or choose a different site name.')
    if scenario == 'existing':
        if not any(x.get('disabled') != 'true' for x in state['ip/hotspot']):
            raise ValidationError('No enabled hotspot found. Choose the new hotspot scenario.')
    else:
        lan, wan = cfg.get('lan', ''), cfg.get('wan', '')
        interfaces = {x['name']: x for x in state['interface']}
        if lan not in interfaces or wan not in interfaces or lan == wan:
            raise ValidationError('Select different existing LAN and WAN interfaces.')
        if interfaces[lan].get('type') != 'ether' or interfaces[lan].get('disabled') == 'true':
            raise ValidationError('New networks require an enabled, unused Ethernet port in this release.')
        for p in ('interface/bridge/port', 'ip/address', 'ip/dhcp-client', 'ip/dhcp-server', 'ip/hotspot'):
            if any(x.get('interface') == lan for x in state[p]):
                raise ValidationError(f'{lan} is already used in {p}. Use a spare port; the wizard never removes existing configuration.')
        net = ipaddress.ip_network(cfg.get('subnet', '10.50.0.0/24'), strict=True)
        if net.version != 4 or not 16 <= net.prefixlen <= 28 or not any(net.subnet_of(ipaddress.ip_network(x)) for x in ['10.0.0.0/8','172.16.0.0/12','192.168.0.0/16']):
            raise ValidationError('Choose an RFC1918 IPv4 subnet with prefix /16 through /28.')
        for row in state['ip/address']:
            if net.overlaps(ipaddress.ip_interface(row['address']).network):
                raise ValidationError('Subnet overlaps an existing router interface.')
        for row in state['ip/dhcp-server/network']:
            if net.overlaps(ipaddress.ip_network(row['address'])):
                raise ValidationError('Subnet overlaps an existing DHCP network.')
        for row in state['ip/pool']:
            for part in row.get('ranges', '').split(','):
                if not part: continue
                bounds = part.split('-')
                lo, hi = ipaddress.ip_address(bounds[0]), ipaddress.ip_address(bounds[-1])
                if int(lo) <= int(net.broadcast_address) and int(hi) >= int(net.network_address):
                    raise ValidationError('Subnet overlaps an existing address pool.')
        filters = state['ip/firewall/filter']
        if not any(x.get('chain') == 'input' and x.get('action') == 'drop' and x.get('disabled') != 'true' for x in filters):
            raise ValidationError('Set up and verify the existing WAN firewall first. This is an additive LAN wizard, not a bare-router security installer.')
        if scenario == 'hotspot' and any(x.get('action') == 'fasttrack-connection' and x.get('disabled') != 'true' for x in filters):
            raise ValidationError('Enabled FastTrack detected. Review and disable or exclude hotspot traffic in WinBox, then reconnect and build a new plan.')
        gateway = str(net.network_address + 1)
        pool = prefix + '-pool'
        # Guard new LAN IPv6 on IPv4 hotspot deployments, without changing global IPv6.
        # Require this isolated port to have no IPv6 configuration; check performed in server preflight.
        add('ip/address', {'address': gateway + '/' + str(net.prefixlen), 'interface': lan, 'comment': prefix}, 'Assign the new LAN gateway')
        add('ip/pool', {'name': pool, 'ranges': f'{net.network_address + 10}-{net.broadcast_address - 1}'}, 'Create the DHCP address pool')
        add('ip/dhcp-server/network', {'address': str(net), 'gateway': gateway, 'dns-server': '1.1.1.1,9.9.9.9', 'comment': prefix}, 'Set gateway and public DNS for clients')
        add('ip/dhcp-server', {'name': prefix + '-dhcp', 'interface': lan, 'address-pool': pool, 'lease-time': '1h', 'disabled': 'no'}, 'Enable DHCP on the spare port')
        anchor = next((x['.id'] for x in filters if x.get('dynamic') != 'true'), None)
        def rule(values, label):
            values['comment'] = prefix
            if anchor: values['place-before'] = anchor
            add('ip/firewall/filter', values, label)
        rule({'chain':'input','in-interface':lan,'protocol':'udp','dst-port':'67','action':'accept'}, 'Allow DHCP requests')
        rule({'chain':'input','in-interface':lan,'action':'drop'}, 'Block LAN access to router management (Hotspot dynamic rules remain ahead)')
        for private in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16','169.254.0.0/16'):
            rule({'chain':'forward','in-interface':lan,'dst-address':private,'action':'drop'}, 'Isolate clients from ' + private)
        accept = {'chain':'forward','in-interface':lan,'out-interface':wan,'src-address':str(net),'action':'accept'}
        if scenario == 'hotspot': accept['hotspot'] = 'auth'
        rule(accept, 'Allow authorized internet traffic' if scenario == 'hotspot' else 'Allow internet traffic')
        rule({'chain':'forward','in-interface':lan,'action':'drop'}, 'Block other forwarded traffic from the new LAN')
        add('ip/firewall/nat', {'chain':'srcnat','src-address':str(net),'out-interface':wan,'action':'masquerade','comment':prefix}, 'Masquerade the new subnet on the chosen WAN')
        if scenario == 'hotspot':
            add('ip/hotspot/profile', {'name':prefix+'-portal','hotspot-address':gateway,'login-by':'http-chap,cookie','html-directory':'hotspot','use-radius':'no'}, 'Create a local-user hotspot profile')
            add('ip/hotspot', {'name':prefix+'-hotspot','interface':lan,'address-pool':pool,'profile':prefix+'-portal','disabled':'no'}, 'Enable the hotspot')
    if scenario != 'office':
        add('ip/hotspot/user/profile', {'name':prefix+'-users','rate-limit':f'{upload}M/{download}M','shared-users':'1','add-mac-cookie':'no'}, 'Create voucher profile: one simultaneous login; no MAC binding')
    warnings = ['Take a WinBox backup and export before applying. REST changes are not a Safe Mode transaction.',
                'Keep a separate management connection. Never connect this computer through the spare port being configured.',
                'Rollback removes recorded additions only. Lost responses or loss of connectivity require manual inspection.',
                'RouterOS 7.24.2 is a requested target; this build has not been tested on real RouterOS hardware.']
    if scenario != 'existing':
        warnings += ['The WAN must already have working internet and a verified firewall. No WAN, Wi-Fi, bridge, VLAN or device-mode changes are made.',
                     'An external access point belongs on the spare port; use AP/bridge mode. Client-to-client isolation must also be enabled on that AP.',
                     'No IPv6 service may be present on the spare port. New-network apply blocks if IPv6 is enabled globally; configure IPv6 deliberately outside this release.']
    if scenario == 'hotspot':
        warnings += ['Hotspot must be permitted by device-mode; physical confirmation may be required in WinBox.',
                     'RouterOS default hotspot files must already be installed. HTTPS portal certificates and custom portal upload are not included.']
    # Install isolation before assigning addresses or enabling client services.
    priority = {'ip/firewall/filter':0,'ip/firewall/nat':1,'ip/address':2,'ip/pool':3,'ip/dhcp-server/network':4,'ip/hotspot/profile':5,'ip/hotspot/user/profile':6,'ip/hotspot':7,'ip/dhcp-server':8}
    operations.sort(key=lambda op: priority[op['path']])
    return {'scenario':scenario,'prefix':prefix,'operations':operations,'warnings':warnings,'snapshot':digest(state),'created':time.time()}

DURATIONS = {'1d':'1d','3d':'3d','1w':'7d','28d':'28d'}
def voucher_operations(profile, server, count, duration, existing_names, options=None):
    if not profile or not server:
        raise ValidationError('Select a profile and hotspot server.')
    count = int(count)
    if not 1 <= count <= 100 or duration not in DURATIONS:
        raise ValidationError('Choose 1–100 vouchers and a supported connected-time allowance.')
    from templates import credential_settings, credentials
    settings=credential_settings(options or {})
    used = set(existing_names)
    batch = secrets.token_hex(4)
    operations, vouchers = [], []
    for _ in range(count):
        name,password=credentials(settings,used)
        values = {'name':name,'password':password,'server':server,'profile':profile,'limit-uptime':DURATIONS[duration],'comment':'ns-batch-'+batch}
        operations.append({'path':'ip/hotspot/user','values':values,'label':'Create voucher ' + name})
        vouchers.append({'pin':name if settings['mode']=='pin' else None,'username':name,'password':password,'credential_mode':settings['mode'],'allowance':DURATIONS[duration],'profile':profile,'batch':batch})
    return operations, vouchers

def execute(router, operations, journal):
    """No blind retries. Journal every intent before issuing the write."""
    for op in operations:
        entry = {'path':op['path'],'label':op['label'],'state':'pending','values':{k:v for k,v in op['values'].items() if k != 'password'}}
        journal['entries'].append(entry)
        journal['save']()
        try:
            result = router.call(op['path'], 'PUT', op['values'])
            if not isinstance(result, dict) or not result.get('.id'):
                raise ValidationError('Write response did not return a resource ID; inspect the router before continuing.')
            entry.update(id=result['.id'], state='created')
            journal['save']()
        except Exception:
            entry['state'] = 'uncertain'
            journal['save']()
            raise

def rollback(router, entries, save):
    for entry in reversed(entries):
        if entry['state'] != 'created': continue
        current = router.call(entry['path'] + '/' + quote(entry['id'], safe=''))
        if isinstance(current,list): current = current[0] if current else {}
        expected = entry['values']
        for k, value in expected.items():
            if k == 'place-before': continue
            norm = lambda v: {'yes':'true','no':'false'}.get(str(v),str(v))
            if norm(current.get(k)) != norm(value):
                raise ValidationError('Rollback stopped: an added object changed since application. Inspect it manually.')
        router.call(entry['path'] + '/' + quote(entry['id'], safe=''), 'DELETE')
        entry['state'] = 'rolled-back'
        save()
