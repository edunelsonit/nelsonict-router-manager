'use strict';
const $ = s => document.querySelector(s);
const token = new URLSearchParams(location.hash.slice(1)).get('token') || sessionStorage.getItem('ns-launch');
if(token) sessionStorage.setItem('ns-launch',token);
history.replaceState(null,'',location.pathname);
let router = null, plan = null, batch = [], busy = false;
const titles = {connect:'Connect your router',wizard:'Setup your network',vouchers:'Manage hotspot access',history:'Review your changes',help:'Connection guide'};
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
 if(['wizard','vouchers','history'].includes(name)&&!router){feedback('Connect to a router or open demonstration mode first.',true);name='connect';}
 document.querySelectorAll('.view').forEach(x=>x.hidden=x.id!==name);
 document.querySelectorAll('nav button').forEach(x=>x.classList.toggle('selected',x.dataset.view===name));
 $('#view-title').textContent=titles[name];
 if(name==='history'&&router) run(loadHistory);
}
document.querySelectorAll('[data-view]').forEach(x=>x.addEventListener('click',()=>view(x.dataset.view)));
function options(selector,values){const current=$(selector).value;$(selector).replaceChildren(...values.map(v=>{const o=document.createElement('option');o.value=v;o.textContent=v;return o;}));if(values.includes(current))$(selector).value=current;}
function renderStatus(data){
 router=data;
 $('#connection-status').textContent=data.demo?'Demo router':data.host;
 $('#disconnect').hidden=false;$('#mode-banner').hidden=!data.demo;
 const r=data.resource;
 $('#router-summary').innerHTML=[['ROUTER',data.identity.name],['ROUTEROS',r.version],['HARDWARE',r['board-name']||r['architecture-name']],['UPTIME',r.uptime]].map(([k,v])=>`<div class="metric"><small>${escapeHTML(k)}</small><strong>${escapeHTML(v)}</strong></div>`).join('');
 options('#lan-select',data.interfaces.filter(x=>x.type==='ether').map(x=>x.name));
 options('#wan-select',data.interfaces.map(x=>x.name));
 options('#profile-select',data.profiles.map(x=>x.name));
 options('#server-select',data.servers.filter(x=>x.disabled!=='true').map(x=>x.name));
 const active=new Set(data.active.map(x=>x.user));
 $('#users-body').innerHTML=data.users.length?data.users.map(u=>`<tr><td>${escapeHTML(u.name)}</td><td>${escapeHTML(u.profile)}</td><td>${escapeHTML(u.uptime||'0s')} / ${escapeHTML(u['limit-uptime']||'unlimited')}</td><td>${['true','yes'].includes(u.disabled)?'Disabled':active.has(u.name)?'Online':'Offline'}</td><td>${(u.comment||'').startsWith('ns-batch-')&&!['true','yes'].includes(u.disabled)?`<button class="secondary" data-disable="${escapeHTML(u['.id'])}">Disable</button>`:'—'}</td></tr>`).join(''):'<tr><td colspan="5" class="empty">No hotspot accounts yet. Generate your first voucher batch above.</td></tr>';
}
$('#connection-form').addEventListener('submit',e=>{e.preventDefault();run(async()=>{const data=Object.fromEntries(new FormData(e.target));feedback('Connecting securely and reading the router configuration…');router=null;plan=null;$('#plan').hidden=true;$('#batch-panel').hidden=true;batch=[];$('#disconnect').hidden=true;$('#mode-banner').hidden=true;$('#connection-status').textContent='Not connected';try{renderStatus(await api('connect',data));}finally{e.target.elements.password.value='';}feedback('Connected. Choose a scenario to build a configuration plan.');view('wizard');});});
$('#demo').addEventListener('click',()=>run(async()=>{renderStatus(await api('demo'));plan=null;batch=[];$('#plan').hidden=true;$('#batch-panel').hidden=true;feedback('Demonstration mode is ready. No real router is connected.');view('wizard');}));
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
$('#refresh-users').addEventListener('click',()=>run(async()=>{renderStatus(await api('status'));feedback('Router accounts refreshed.');}));
$('#voucher-form').addEventListener('submit',e=>{e.preventDefault();run(async()=>{
 const data=Object.fromEntries(new FormData(e.target));data.confirmation='CREATE';
 feedback('Creating vouchers. Do not retry if the connection is interrupted; inspect Change history first.');
 const result=await api('vouchers',data);batch=result.vouchers;
 $('#voucher-cards').innerHTML=batch.map(v=>`<div class="ticket"><small>NELSONICT SERVICES LIMITED${result.demo?' • DEMO':''}</small><strong>${escapeHTML(v.pin)}</strong><span>${escapeHTML(v.allowance)} total online time</span><small>Username & password: use this PIN</small><small>Profile: ${escapeHTML(v.profile)}</small></div>`).join('');
 $('#batch-panel').hidden=false;e.target.elements.confirm.checked=false;renderStatus(await api('status'));feedback(`Created ${batch.length} ${result.demo?'simulated ':''}vouchers. Print or export this batch.`);
});});
$('#print').addEventListener('click',()=>window.print());
$('#csv').addEventListener('click',()=>{const cell=x=>{let v=String(x);if(/^[=+@\-\t\r]/.test(v))v="'"+v;return '"'+v.replace(/"/g,'""')+'"';};const rows=[['PIN','Connected time','Profile','Batch'],...batch.map(v=>[v.pin,v.allowance,v.profile,v.batch])];download('nelsonict-vouchers.csv',rows.map(row=>row.map(cell).join(',')).join('\r\n'),'text/csv');});
function confirmation(title,message,word){return new Promise(resolve=>{const d=$('#confirm-dialog');$('#dialog-title').textContent=title;$('#dialog-text').textContent=message;$('#dialog-label').firstChild.textContent='Type '+word+' to confirm';$('#dialog-input').value='';d.returnValue='cancel';d.addEventListener('close',()=>resolve(d.returnValue==='confirm'&&$('#dialog-input').value===word),{once:true});d.showModal();});}
$('#users-body').addEventListener('click',e=>{const b=e.target.closest('[data-disable]');if(!b)return;run(async()=>{if(!await confirmation('Disable this voucher?','The account record stays. Its active sessions and login cookies will be removed.','DISABLE'))return;await api('disable',{id:b.dataset.disable,confirmation:'DISABLE'});renderStatus(await api('status'));feedback('Voucher disabled; matching sessions and cookies removed.');});});
async function loadHistory(){const {records}=await api('history');$('#history-list').innerHTML=records.length?records.map(r=>`<div class="card history-entry"><div class="card-heading"><h3>${escapeHTML(r.kind)} ${r.demo?'• demonstration':''}</h3><button class="secondary" data-rollback="${escapeHTML(r.id)}">Rollback additions</button></div><small>${escapeHTML(new Date(r.created*1000).toLocaleString())} • ${escapeHTML(r.id)}</small><ol>${r.entries.map(x=>`<li class="${x.state==='uncertain'?'uncertain':''}">${escapeHTML(x.label)} — <strong>${escapeHTML(x.state)}</strong></li>`).join('')}</ol></div>`).join(''):'<div class="card empty">No change records for this router on this computer.</div>';}
$('#refresh-history').addEventListener('click',()=>run(loadHistory));
$('#history-list').addEventListener('click',e=>{const b=e.target.closest('[data-rollback]');if(!b)return;run(async()=>{if(!await confirmation('Remove these additions?','This may disconnect clients. Only recorded additions are removed; uncertain writes require manual inspection.','ROLLBACK'))return;const result=await api('rollback',{id:b.dataset.rollback,confirmation:'ROLLBACK'});await loadHistory();renderStatus(await api('status'));feedback(`Recorded additions rolled back. ${result.uncertain} uncertain operations require manual inspection.`);});});
if(!token)feedback('Start server.py and open its private launch URL to use the application.',true);
