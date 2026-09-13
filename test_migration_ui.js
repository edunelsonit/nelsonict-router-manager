'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const elements=new Map(),errors=[];let calls=[],waiting=null;
function $(id){if(!elements.has(id))elements.set(id,{value:'',checked:false,hidden:false,textContent:'',innerHTML:'',handlers:{},addEventListener(event,fn){this.handlers[event]=fn;}});return elements.get(id);}
const row={id:'a'.repeat(24),name:'Gembu',host:'192.168.88.1',username:'owner',port:8728,transport:'api',fingerprint:''};
const preview={locations:[row],destination:{data_directory:'/new/data',configured:{}},files:1,replace:0,groups:['locations'],connection_changes:[]};
const context=vm.createContext({$,JSON,Error,Object,String,escapeHTML:s=>String(s).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;'),
 run:async fn=>{try{return await fn();}catch(e){errors.push(e.message);}},
 api:async(path,data)=>{calls.push({path,data});if(waiting)return await waiting;return preview;},
 download(){},feedback(){},confirmation:async()=>false,loadLocations:async()=>{},fillLocation(){}});
vm.runInContext(fs.readFileSync('web/business.js','utf8'),context);
(async()=>{
 await $('#backup-file').handlers.change({target:{files:[{size:10,text:async()=>'{"format":"nelsonict-backup-1","files":{}}'}]}});
 assert.equal($('#backup-migration').hidden,false);assert.equal($('#backup-restore').hidden,true);
 for(const [key,value] of Object.entries(row))$('#migration-0-'+key).value=String(value);
 $('#migration-ack').checked=true;
 await $('#migration-review').handlers.click();
 assert.equal($('#backup-restore').hidden,false);assert.equal(calls.at(-1).data.location_updates[0].host,row.host);
 $('#migration-0-host').value='10.20.0.1';$('#migration-locations').handlers.input();
 assert.equal($('#backup-restore').hidden,true);
 let resolve;waiting=new Promise(r=>resolve=r);
 const pending=$('#migration-review').handlers.click();
 $('#migration-0-host').value='10.20.0.2';$('#migration-locations').handlers.input();
 resolve(preview);await pending;waiting=null;
 assert.equal($('#backup-restore').hidden,true);assert.match(errors.at(-1),/Settings changed/);
 await $('#migration-review').handlers.click();assert.equal($('#backup-restore').hidden,false);
 $('#migration-ack').checked=false;$('#migration-ack').handlers.change();
 assert.equal($('#backup-restore').hidden,true);
 console.log('Migration UI requires review and invalidates edited or stale previews.');
})().catch(e=>{console.error(e);process.exitCode=1;});
