'use strict';
let restoreBundle=null, migrationLocations=[], reviewedRestore=null, migrationRevision=0;
function invalidateRestore(){migrationRevision++;reviewedRestore=null;$('#backup-restore').hidden=true;$('#backup-preview').hidden=true;$('#migration-status').textContent='Review the current settings before restoring.';}
function migrationUpdates(){return migrationLocations.map((row,index)=>{const result={id:row.id};for(const key of ['name','host','username','transport','port','fingerprint'])result[key]=$(`#migration-${index}-${key}`).value;return result;});}
function renderMigration(result){
 migrationLocations=result.locations;
 $('#migration-locations').innerHTML=result.locations.map((row,index)=>`<fieldset><legend>${escapeHTML(row.name)}</legend><div class="fields two">${['name','host','username','port','fingerprint'].map(key=>`<label>${escapeHTML({name:'Location name',host:'Router IPv4 address',username:'Router username',port:'Service port',fingerprint:'Trusted SHA-256 fingerprint (optional)'}[key])}<input id="migration-${index}-${key}" value="${escapeHTML(String(row[key]))}" ${key==='port'?'type="number" min="1" max="65535"':'type="text"'} autocomplete="off"></label>`).join('')}<label>Connection service<select id="migration-${index}-transport">${[['api','API · trusted LAN'],['api-ssl','API-SSL'],['http','HTTP REST · trusted LAN'],['https','HTTPS REST']].map(([value,label])=>`<option value="${value}" ${row.transport===value?'selected':''}>${label}</option>`).join('')}</select></label></div><p class="muted">Keep a custom service port if required. Verify a changed certificate fingerprint independently before connecting.</p></fieldset>`).join('');
 result.locations.forEach((row,index)=>{$(`#migration-${index}-transport`).addEventListener('change',()=>{$(`#migration-${index}-port`).value={api:8728,'api-ssl':8729,http:80,https:443}[$(`#migration-${index}-transport`).value];invalidateRestore();});});
 $('#migration-empty').hidden=!!result.locations.length;
 $('#migration-destination').textContent='Destination data folder: '+result.destination.data_directory+'\n\n'+Object.entries(result.destination.configured).map(([key,present])=>key+': '+(present?'configured':'not configured (needed only for its integration)')).join('\n');
 $('#backup-migration').hidden=false;
}
$('#migration-locations').addEventListener('input',invalidateRestore);
$('#migration-locations').addEventListener('change',invalidateRestore);
$('#migration-ack').addEventListener('change',invalidateRestore);
$('#backup-export').addEventListener('click',()=>run(async()=>{const data=await api('backup/export');download('nelsonict-backup-'+new Date().toISOString().slice(0,10)+'.json',JSON.stringify(data,null,2),'application/json');feedback('Backup downloaded. It contains voucher passwords; keep it private.');}));
$('#backup-file').addEventListener('change',e=>run(async()=>{
 restoreBundle=null;migrationLocations=[];invalidateRestore();$('#backup-migration').hidden=true;$('#migration-ack').checked=false;
 const revision=migrationRevision;const file=e.target.files[0];if(!file)return;if(file.size>12*1024*1024)throw new Error('Backup limit is 12 MB.');
 const bundle=JSON.parse(await file.text());const result=await api('backup/preview',{backup:bundle});if(revision!==migrationRevision)return;restoreBundle=bundle;renderMigration(result);
}));
$('#migration-review').addEventListener('click',()=>run(async()=>{
 invalidateRestore();if(!restoreBundle)throw new Error('Select a backup first.');
 if(!$('#migration-ack').checked)throw new Error('Confirm the migration checklist before reviewing.');
 const revision=migrationRevision;const request={backup:restoreBundle,location_updates:migrationUpdates(),migration_ack:true};
 const result=await api('backup/preview',request);if(revision!==migrationRevision)throw new Error('Settings changed while reviewing. Review again.');reviewedRestore=JSON.parse(JSON.stringify(request));
 $('#backup-preview').textContent=JSON.stringify({files:result.files,replace:result.replace,groups:result.groups,connection_changes:result.connection_changes},null,2);
 $('#backup-preview').hidden=false;$('#backup-restore').hidden=false;$('#migration-status').textContent='Settings validated. Review replacements above, disconnect the router, then restore.';
}));
$('#backup-restore').addEventListener('click',()=>run(async()=>{
 if(!reviewedRestore)throw new Error('Review the current migration settings first.');
 const request=reviewedRestore;
 if(!await confirmation('Restore application data on this computer?','Disconnect the router first. Matching files will be replaced; a recovery copy is saved automatically. No router settings or accounts are restored.','RESTORE'))return;
 if(request!==reviewedRestore)throw new Error('Settings changed. Review again before restoring.');
 const result=await api('backup/restore',{...request,confirmation:'RESTORE'});
 restoreBundle=null;invalidateRestore();$('#backup-migration').hidden=true;$('#backup-file').value='';
 await loadLocations('');fillLocation();
 feedback(`Restored ${result.restored} files. Recovery copy: ${result.recovery}. Open Connect your router, select a restored location and enter its password. Verify archives, prices, sales, NTP and printer settings before selling.`);
}));
function showOrders(result){$('#payment-orders').innerHTML=result.orders.length?result.orders.map(o=>`<tr><td>${escapeHTML(o.reference)}</td><td>${escapeHTML(o.provider||'paystack')}</td><td>${escapeHTML(o.price?.label||o.currency+' '+o.amount/100)}</td><td>${escapeHTML(o.domain)}</td><td>${escapeHTML(o.state)}</td><td>${escapeHTML(o.batch||'Not issued')}</td><td>${o.checkout_url?`<a href="${escapeHTML(o.checkout_url)}" target="_blank" rel="noopener noreferrer">Open checkout</a>`:'Unavailable'}</td></tr>`).join(''):'<tr><td colspan="7">No payment orders for this location.</td></tr>';}
$('#payment-create').addEventListener('click',()=>run(async()=>{const cfg=Object.fromEntries(new FormData($('#voucher-form')));cfg.email=$('#payment-email').value;cfg.provider=$('#payment-provider').value;cfg.customer_name=$('#payment-name').value;const result=await api('payments/create',cfg);showOrders(await api('payments/list'));feedback(`Checkout ${result.reference} created (${result.domain}). Share its link with the customer. Keep the backend connected to this location for automatic issuance.`);}));
$('#payment-refresh').addEventListener('click',()=>run(async()=>{showOrders(await api('payments/check'));feedback('Payments checked. Issued batches are available in Saved vouchers. Needs-review orders require checking the router and voucher archive before any manual replacement.');}));

