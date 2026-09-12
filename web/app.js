'use strict';
const $ = s => document.querySelector(s);
const token = new URLSearchParams(location.hash.slice(1)).get('token') || sessionStorage.getItem('ns-launch');
if(token) sessionStorage.setItem('ns-launch',token);
history.replaceState(null,'',location.pathname);
let router = null, plan = null, batch = [], busy = false, currentView='connect';
const titles = {remote:'Remote control',usermanager:'User Manager',packages:'Desktop packages',diagnostics:'AI setup walkthrough',sales:'Sales reports',connect:'Connect your router',templates:'Voucher template editor',dashboard:'Owner dashboard',wizard:'Setup your network',vouchers:'Manage hotspot access',history:'Review your changes',help:'Connection guide'};
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function feedback(message,error=false){const el=$('#feedback');el.textContent=message;el.classList.toggle('error',error);el.hidden=false;}
async function api(path,data={}){
 if(busy) throw new Error('An operation is already in progress. Please wait.');
 busy=true; document.querySelectorAll('button').forEach(b=>b.disabled=true);
 try{
  const response=await fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-App-Token':token||''},body:JSON.stringify(data)});
  const result=await response.json();
  if(!response.ok) throw new Error(result.error+(result.journal?' Change record: '+result.journal:''));
  return result;
 }finally{busy=false;document.querySelectorAll('button').forEach(b=>b.disabled=false);}
}
async function run(fn){try{await fn();}catch(e){feedback(e.message,true);}}
function view(name){
 if(['dashboard','wizard','vouchers','history','sales','usermanager'].includes(name)&&!router){feedback('Connect to a router or open demonstration mode first.',true);name='connect';}
 document.querySelectorAll('.view').forEach(x=>x.hidden=x.id!==name);
 document.querySelectorAll('nav button').forEach(x=>x.classList.toggle('selected',x.dataset.view===name));
 currentView=name;
 $('#view-title').textContent=titles[name];
 if(name==='sales'&&router)run(()=>loadSales(0));
 if(name==='history'&&router) run(loadHistory);
 if(name==='dashboard'&&router)renderOwner();
 if(name==='vouchers'&&router)run(loadProfilePrices);
 if(name==='connect'&&token)run(()=>loadLocations());
 if(name==='templates')run(()=>window.loadTemplates());
}
document.querySelectorAll('[data-view]').forEach(x=>x.addEventListener('click',()=>view(x.dataset.view)));
function options(selector,values){const current=$(selector).value;$(selector).replaceChildren(...values.map(v=>{const o=document.createElement('option');o.value=v;o.textContent=v;return o;}));if(values.includes(current))$(selector).value=current;}
function renderStatus(data){
 router=data;
 $('#sample-activity').hidden=!data.demo;
 $('#connection-status').textContent=data.demo?'Demo router':(data.location_name?data.location_name+' · ':'')+data.host;
 $('#disconnect').hidden=false;$('#mode-banner').hidden=!data.demo;
 const r=data.resource;
 $('#router-summary').innerHTML=[['ROUTER',data.identity.name],['ROUTEROS',r.version],['HARDWARE',r['board-name']||r['architecture-name']],['UPTIME',r.uptime]].map(([k,v])=>`<div class="metric"><small>${escapeHTML(k)}</small><strong>${escapeHTML(v)}</strong></div>`).join('');
 options('#lan-select',data.interfaces.filter(x=>x.type==='ether').map(x=>x.name));
 options('#wan-select',data.interfaces.map(x=>x.name));
 options('#profile-select',data.profiles.map(x=>x.name));
 options('#server-select',data.servers.filter(x=>x.disabled!=='true').map(x=>x.name));
 options('#portal-server',data.servers.map(x=>x.name));
 const previous=$('#account-profile').value;
 $('#account-profile').replaceChildren(new Option('All profiles',''),...Array.from(new Set(data.users.map(u=>u.profile||''))).filter(Boolean).sort().map(p=>new Option(p,p)));
 if(Array.from($('#account-profile').options).some(o=>o.value===previous))$('#account-profile').value=previous;
 renderAccounts();
 renderOwner();
}
$('#connection-form').addEventListener('submit',e=>{e.preventDefault();run(async()=>{const data=Object.fromEntries(new FormData(e.target));if($('#saved-location').value)data.location_id=$('#saved-location').value;feedback('Connecting and reading the router configuration…');router=null;plan=null;$('#plan').hidden=true;$('#batch-panel').hidden=true;batch=[];$('#disconnect').hidden=true;$('#mode-banner').hidden=true;$('#connection-status').textContent='Not connected';try{renderStatus(await api('connect',data));}finally{e.target.elements.password.value='';}feedback('Connected. Open the owner dashboard or choose a setup scenario.');await loadProfilePrices();view('dashboard');});});
$('#demo').addEventListener('click',()=>run(async()=>{renderStatus(await api('demo'));plan=null;batch=[];$('#plan').hidden=true;$('#batch-panel').hidden=true;feedback('Demonstration mode is ready. No real router is connected.');view('dashboard');}));
$('#disconnect').addEventListener('click',()=>run(async()=>{await api('disconnect');router=null;plan=null;batch=[];$('#plan').hidden=true;$('#batch-panel').hidden=true;$('#disconnect').hidden=true;$('#mode-banner').hidden=true;$('#connection-status').textContent='Not connected';feedback('Disconnected. Router credentials have been cleared from application memory.');view('connect');}));
$('#wizard-form').addEventListener('change',()=>{const choice=new FormData($('#wizard-form')).get('scenario');$('#new-network-fields').hidden=choice==='existing';$('#speed-fields').hidden=choice==='office';plan=null;$('#plan').hidden=true;});
$('#wizard-form').addEventListener('input',()=>{plan=null;$('#plan').hidden=true;});
$('#wizard-form').addEventListener('submit',e=>{e.preventDefault();run(async()=>{
 plan=null;$('#plan').hidden=true;feedback('Checking interfaces, subnets and existing configuration…');
 plan=await api('plan',Object.fromEntries(new FormData(e.target)));
 $('#plan-warnings').innerHTML='<div class="notice"><ul>'+plan.warnings.map(x=>`<li>${escapeHTML(x)}</li>`).join('')+'</ul></div>';
 $('#plan-steps').innerHTML=plan.operations.map(x=>`<li>${escapeHTML(x.label)}</li>`).join('');
 $('#plan-json').textContent=JSON.stringify(plan.operations,null,2);$('#apply-form').reset();$('#plan').hidden=false;
 feedback(`${plan.operations.length} additions ready for review. This plan expires in 10 minutes.`);$('#plan').scrollIntoView({behavior:'smooth',block:'start'});
});});
function download(name,content,type){const link=document.createElement('a'),url=URL.createObjectURL(new Blob([content],{type}));link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('#download-plan').addEventListener('click',()=>{if(plan)download('nelsonict-configuration-plan.json',JSON.stringify(plan,null,2),'application/json');});
$('#apply-form').addEventListener('submit',e=>{e.preventDefault();run(async()=>{if(!plan)throw new Error('Build a new plan first.');const current=plan;plan=null;$('#plan').hidden=true;feedback('Applying reviewed changes. Keep the application open…');const result=await api('apply',{plan_id:current.id,backup:$('#backup-confirm').checked,confirmation:$('#apply-confirm').value});renderStatus(await api('status'));feedback(`${result.demo?'Simulated':'Applied'} ${result.count} additions. Change record ${result.journal}.`);});});
$('#refresh-users').addEventListener('click',()=>run(async()=>{renderStatus(await api('status'));await loadProfilePrices();feedback('Router accounts refreshed.');}));
$('#voucher-form').addEventListener('submit',e=>{e.preventDefault();run(async()=>{
 const data=Object.fromEntries(new FormData(e.target));data.confirmation='CREATE';
 feedback('Creating vouchers. Do not retry if the connection is interrupted; inspect Change history first.');
 const result=await api('vouchers',data);batch=result.vouchers;
 await window.renderVoucherBatch();
 $('#batch-panel').hidden=false;e.target.elements.confirm.checked=false;renderStatus(await api('status'));feedback(`Created ${batch.length} ${result.demo?'simulated ':''}vouchers. Print or export this batch.`);
});});
$('#print').addEventListener('click',()=>{const frame=$('#batch-preview');frame.contentWindow.focus();frame.contentWindow.print();});
$('#csv').addEventListener('click',()=>{const cell=x=>{let v=String(x);if(/^[=+@\-\t\r]/.test(v))v="'"+v;return '"'+v.replace(/"/g,'""')+'"';};const rows=[['Credential mode','Username','Password','Allowance','Expiry policy','Profile','Batch','Base profile','Price','Currency'],...batch.map(v=>[v.credential_mode||'pin',v.username||v.pin,v.password||v.pin,v.allowance,v.policy||'connected',v.profile,v.batch,v.base_profile||v.profile,v.price_amount||'',v.currency||''])];download('nelsonict-vouchers.csv',rows.map(row=>row.map(cell).join(',')).join('\r\n'),'text/csv');});
function confirmation(title,message,word){return new Promise(resolve=>{const d=$('#confirm-dialog');$('#dialog-title').textContent=title;$('#dialog-text').textContent=message;$('#dialog-label').firstChild.textContent='Type '+word+' to confirm';$('#dialog-input').value='';d.returnValue='cancel';d.addEventListener('close',()=>resolve(d.returnValue==='confirm'&&$('#dialog-input').value===word),{once:true});d.showModal();});}
$('#users-body').addEventListener('click',e=>{const b=e.target.closest('[data-disable]');if(!b)return;run(async()=>{if(!await confirmation('Disable this voucher?','The account record stays. Its active sessions and login cookies will be removed.','DISABLE'))return;await api('disable',{id:b.dataset.disable,confirmation:'DISABLE'});renderStatus(await api('status'));feedback('Voucher disabled; matching sessions and cookies removed.');});});
async function loadHistory(){const {records}=await api('history');$('#history-list').innerHTML=records.length?records.map(r=>`<div class="card history-entry"><div class="card-heading"><h3>${escapeHTML(r.kind)} ${r.demo?'• demonstration':''}</h3>${!['ticket-action','diagnostic-repair','user-manager'].includes(r.kind)?`<button class="secondary" data-rollback="${escapeHTML(r.id)}">Rollback additions</button>`:''}</div><small>${escapeHTML(new Date(r.created*1000).toLocaleString())} • ${escapeHTML(r.id)}</small><ol>${r.entries.map(x=>`<li class="${x.state==='uncertain'?'uncertain':''}">${escapeHTML(x.label)} — <strong>${escapeHTML(x.state)}</strong></li>`).join('')}</ol></div>`).join(''):'<div class="card empty">No change records for this router on this computer.</div>';}
$('#refresh-history').addEventListener('click',()=>run(loadHistory));
$('#history-list').addEventListener('click',e=>{const b=e.target.closest('[data-rollback]');if(!b)return;run(async()=>{if(!await confirmation('Remove these additions?','This may disconnect clients. Only recorded additions are removed; uncertain writes require manual inspection.','ROLLBACK'))return;const result=await api('rollback',{id:b.dataset.rollback,confirmation:'ROLLBACK'});await loadHistory();renderStatus(await api('status'));feedback(`Recorded additions rolled back. ${result.uncertain} uncertain operations require manual inspection.`);});});
if(!token)feedback('Start server.py and open its private launch URL to use the application.',true);

const policyDescriptions={
 elapsed:'Expires after the selected duration from first login, including offline time. Recommended for stable electricity.',
 business:'Expires at the next selected closing time after first login. A login at or after closing gets the next day’s closing time. Duration selection is not used.',
 startup:'For used daily tickets: a later-day boot sets expiry to boot + 10 minutes, once NTP is synchronized. If the router remains on overnight, the fallback time applies. Once a deadline is recorded it never moves later. Duration selection is not used.',
 connected:'Counts accumulated online usage. Offline time does not consume the selected allowance.',
 fixed:'Expires at the selected instant, even if never used. Include an explicit UTC offset. Duration selection is not used.'
};
function expiryFields(){const mode=$('#expiry-mode').value;$('#policy-explanation').textContent=policyDescriptions[mode];$('#offset-field').hidden=!['business','startup'].includes(mode);$('#closing-field').hidden=mode!=='business';$('#fallback-field').hidden=mode!=='startup';$('#fixed-field').hidden=mode!=='fixed';$('#voucher-form [name=duration]').disabled=!['elapsed','connected'].includes(mode);}
$('#expiry-mode').addEventListener('change',expiryFields);expiryFields();
$('#preview-expiry').addEventListener('click',()=>run(async()=>{const r=await api('expiry/preview');$('#expiry-source').textContent=r.scheduler;$('#expiry-hook').textContent=r.hook;$('#expiry-install-panel').hidden=false;feedback(r.operations.length?'Review the scripts, then install the router expiry engine.':'The expected expiry engine is already installed and enabled.');}));
$('#install-expiry').addEventListener('click',()=>run(async()=>{if(!await confirmation('Install router expiry automation?','This adds a scheduler that manages tracked ns2 tickets every 30 seconds. Review the scripts and preserve a router backup.','INSTALL'))return;const result=await api('expiry/install',{confirmation:'INSTALL'});feedback(result.count?'Router expiry checker installed. Create tracked tickets below.':'Router expiry checker is already installed.');}));
function stamp(seconds){return seconds?new Date(seconds*1000).toLocaleString():'Unknown / not recorded';}
function renderOwner(){
 if(!router)return;
 const c=router.counts||{sessions:router.active.length,connected_users:new Set(router.active.map(x=>x.user)).size,overdue_active:0,expired:0};
 $('#owner-metrics').innerHTML=[['CONNECTED USERS',c.connected_users],['ACTIVE SESSIONS',c.sessions],['EXPIRED BUT ONLINE',c.overdue_active],['EXPIRED TICKETS',c.expired]].map(([k,v])=>`<div class="metric"><small>${k}</small><strong>${v}</strong></div>`).join('');
 $('#last-updated').textContent='Last refreshed: '+stamp(router.observed_at)+' • times in '+Intl.DateTimeFormat().resolvedOptions().timeZone;
 $('#clock-notice').hidden=!!router.clock?.verified;$('#clock-notice').textContent='Router clock is not verified ('+(router.clock?.ntp_status||'unavailable')+'). Calendar expiry status is unknown until NTP synchronizes.';
 const query=$('#ticket-search').value.trim().toLowerCase(),filter=$('#ticket-filter').value;
 const rows=router.users.filter(u=>u.name.toLowerCase().includes(query)).filter(u=>filter==='all'||filter==='online'&&u.session_count>0||filter==='overdue'&&u.overdue_active||filter==='expired'&&u.expiry_state==='expired'||filter==='disabled'&&['true','yes'].includes(u.disabled));
 $('#owner-tickets').innerHTML=rows.length?rows.map(u=>{
  const disabled=['true','yes'].includes(u.disabled),blocked=['expired','clock-unverified','invalid-policy'].includes(u.expiry_state);
  const status=u.overdue_active?'EXPIRED — STILL CONNECTED':disabled?'DISABLED':u.session_count?'CONNECTED':(u.expiry_state||'offline').toUpperCase();
  const first=u.first_login?stamp(u.first_login):u.expiry_state==='unused'?'Not yet activated':'Unknown — no first-login record';
  return `<tr class="${u.overdue_active?'overdue':''}"><th scope="row">${escapeHTML(u.name)}</th><td><span class="badge">${escapeHTML(status)}</span>${u.policy_error?`<small class="owner-policy-error">${escapeHTML(u.policy_error)}</small>`:''}</td><td>${escapeHTML(u.profile)}</td><td>${escapeHTML(first)}</td><td>${escapeHTML(u.expires_at?stamp(u.expires_at):u.policy==='connected'?'After connected-time allowance':u.policy==='startup'?'After next-day startup / fallback':u.expiry_state==='unused'?'Starts on first login':'Unknown')}</td><td>${escapeHTML(u.session_count||0)}</td><td>${escapeHTML(u.current_session_started?stamp(u.current_session_started)+' (estimated)':'Not connected / unavailable')}</td><td>${escapeHTML(u.policy||'legacy')}</td><td class="owner-row-actions"><div class="ticket-actions"><button class="secondary" data-ticket-action="disable" data-id="${escapeHTML(u['.id'])}" aria-label="${escapeHTML('Disable ticket '+u.name)}">${disabled?'Retry cleanup':'Disable'}</button>${u.session_count?`<button class="secondary" data-ticket-action="disconnect" data-id="${escapeHTML(u['.id'])}" aria-label="${escapeHTML('Disconnect ticket '+u.name)}">Disconnect</button>`:''}${disabled&&!blocked?`<button class="secondary" data-ticket-action="enable" data-id="${escapeHTML(u['.id'])}" aria-label="${escapeHTML('Re-enable ticket '+u.name)}">Re-enable</button>`:''}</div></td></tr>`;
 }).join(''):'<tr><td colspan="9" class="empty">No tickets match this view.</td></tr>';
 $('#owner-table-count').textContent=`Showing ${rows.length} of ${router.users.length} tickets`;

}
async function refreshOwner(){renderStatus(await api('status'));}
$('#refresh-dashboard').addEventListener('click',()=>run(refreshOwner));
$('#sample-activity').addEventListener('click',()=>run(async()=>{renderStatus(await api('demo/activity'));feedback('Sample activity loaded: two connected users, including one expired ticket. All data is simulated.');}));
$('#ticket-search').addEventListener('input',renderOwner);$('#ticket-filter').addEventListener('change',renderOwner);
$('#owner-tickets').addEventListener('click',e=>{const b=e.target.closest('[data-ticket-action]');if(!b)return;run(async()=>{const action=b.dataset.ticketAction;const message={disable:'Disables future login and removes current sessions and cookies. The account record is retained.',disconnect:'Removes current sessions and cookies. A valid ticket can log in again.',enable:'Re-enables a valid ticket without extending its expiry.'}[action];if(!await confirmation(action+' this ticket?',message,action.toUpperCase()))return;await api('ticket/action',{id:b.dataset.id,action,confirmation:action.toUpperCase()});await refreshOwner();feedback('Ticket action completed: '+action+'.');});});
setInterval(()=>{if(router&&currentView==='dashboard'&&!busy&&!document.hidden&&!$('#confirm-dialog').open){refreshOwner().catch(()=>{ $('#last-updated').textContent='STALE DATA — refresh failed. Last successful snapshot: '+stamp(router?.observed_at);});}},15000);

$('#router-transport').addEventListener('change',e=>{const kind=e.target.value;$('#connection-form').elements.port.value={api:8728,'api-ssl':8729,http:80,https:443}[kind];const secure=['https','api-ssl'].includes(kind);$('#router-certificate').hidden=!secure;$('#transport-note').textContent=secure?'The router certificate is verified before credentials are sent.':'This service sends credentials without encryption. Use a trusted management LAN.';});

let pricedProfiles=[];
function fillProfilePrice(){const profile=pricedProfiles.find(p=>p.id===$('#price-profile').value);$('#profile-amount').value=profile?.price?.amount??'';$('#profile-currency').value=profile?.price?.currency||'NGN';}
async function loadProfilePrices(){const result=await api('profiles/prices');pricedProfiles=result.profiles;for(const option of $('#profile-select').options){const p=pricedProfiles.find(x=>x.name===option.value);option.textContent=option.value+(p?.price?' · '+p.price.label:'');}const old=$('#price-profile').value;$('#price-profile').replaceChildren(...pricedProfiles.map(p=>{const el=document.createElement('option');el.value=p.id;el.textContent=p.name+(p.price?' · '+p.price.label:' · No price');return el;}));if(pricedProfiles.some(p=>p.id===old))$('#price-profile').value=old;fillProfilePrice();}
$('#price-profile').addEventListener('change',fillProfilePrice);
$('#refresh-prices').addEventListener('click',()=>run(loadProfilePrices));
$('#profile-price-form').addEventListener('submit',e=>{e.preventDefault();run(async()=>{const profile=pricedProfiles.find(p=>p.id===$('#price-profile').value);if(!profile)throw new Error('Refresh and select a user profile first.');await api('profiles/price',{id:profile.id,name:profile.name,amount:$('#profile-amount').value,currency:$('#profile-currency').value});await loadProfilePrices();feedback('Profile price saved. It applies to newly generated tickets; existing batches keep their original price.');});});

let accountSort={key:'name',direction:1};
function renderAccounts(){
 if(!router)return;
 const active=new Set(router.active.map(x=>x.user));
 const rows=accountTableUtils.select(router.users,active,{query:$('#account-search').value,profile:$('#account-profile').value,status:$('#account-status').value,...accountSort});
 $('#account-count').textContent=`Showing ${rows.length} of ${router.users.length} accounts`;
 $('#users-body').innerHTML=rows.length?rows.map(u=>{const disabled=['true','yes'].includes(u.disabled);return `<tr><td>${escapeHTML(u.name)}</td><td>${escapeHTML(u.profile)}</td><td>${escapeHTML(u.uptime||'0s')}</td><td>${escapeHTML(accountTableUtils.duration(u['limit-uptime'])?u['limit-uptime']:'unlimited')}</td><td>${disabled?'Disabled':active.has(u.name)?'Online':'Offline'}</td><td>${disabled?'—':`<button class="secondary" data-disable="${escapeHTML(u['.id'])}" ${busy?'disabled':''}>Disable</button>`}</td></tr>`;}).join(''):'<tr><td colspan="6" class="empty">'+(router.users.length?'No accounts match these filters. Reset filters to see all accounts.':'No hotspot accounts yet. Generate your first voucher batch above.')+'</td></tr>';
 document.querySelectorAll('[data-account-sort]').forEach(button=>{const selected=button.dataset.accountSort===accountSort.key;button.parentElement.setAttribute('aria-sort',selected?(accountSort.direction===1?'ascending':'descending'):'none');button.querySelector('span').textContent=selected?(accountSort.direction===1?'↑':'↓'):'↕';});
}
$('#account-search').addEventListener('input',renderAccounts);
for(const id of ['#account-profile','#account-status'])$(id).addEventListener('change',renderAccounts);
document.querySelectorAll('[data-account-sort]').forEach(button=>button.addEventListener('click',()=>{const key=button.dataset.accountSort;accountSort={key,direction:accountSort.key===key?-accountSort.direction:1};renderAccounts();}));
$('#account-reset').addEventListener('click',()=>{$('#account-search').value='';$('#account-profile').value='';$('#account-status').value='';accountSort={key:'name',direction:1};renderAccounts();});

let savedLocations=[];
async function loadLocations(selected=$('#saved-location').value){const r=await api('locations/list');savedLocations=r.locations;$('#saved-location').replaceChildren(new Option('New / manual connection',''),...savedLocations.map(x=>new Option(x.name+' · '+x.host,x.id)));if(savedLocations.some(x=>x.id===selected))$('#saved-location').value=selected;}
function fillLocation(){const row=savedLocations.find(x=>x.id===$('#saved-location').value),form=$('#connection-form');form.elements.password.value='';$('#location-name').value=row?.name||'';if(row){for(const key of ['host','username','transport','port','fingerprint'])form.elements[key].value=row[key];$('#router-transport').dispatchEvent(new Event('change'));form.elements.port.value=row.port;} }
$('#load-locations').addEventListener('click',()=>run(()=>loadLocations()));
$('#saved-location').addEventListener('change',fillLocation);
$('#new-location').addEventListener('click',()=>{$('#saved-location').value='';$('#location-name').value='';$('#connection-form').reset();$('#router-transport').dispatchEvent(new Event('change'));});
$('#save-location').addEventListener('click',()=>run(async()=>{const form=$('#connection-form');const data={id:$('#saved-location').value,name:$('#location-name').value};for(const key of ['host','username','port','transport','fingerprint'])data[key]=form.elements[key].value;const r=await api('locations/save',data);await loadLocations(r.location.id);feedback('Location settings saved. Enter the router password and connect.');}));
$('#delete-location').addEventListener('click',()=>run(async()=>{const id=$('#saved-location').value;if(!id)throw new Error('Select a saved location.');if(!await confirmation('Remove saved location?','This removes its connection settings. Router configuration and archived files are retained.','REMOVE'))return;await api('locations/delete',{id});await loadLocations('');fillLocation();feedback('Saved location removed.');}));
// Editing saved settings requires saving them before connection.
$('#connection-form').addEventListener('input',e=>{if(e.target.name!=='password'&&$('#saved-location').value){$('#saved-location').value='';feedback('Connection settings changed. Save as a location or connect manually.');}});

