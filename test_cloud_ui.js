'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('web/app.js','utf8');
const apiSource=source.slice(source.indexOf('const cloudRequests='),source.indexOf('async function run('));
const pending=[];const buttons=[{disabled:false}];
const context=vm.createContext({Set,Error,JSON,document:{querySelectorAll:()=>buttons},fetch:(url)=>new Promise(resolve=>pending.push({url,resolve}))});
vm.runInContext("let busy=false;const token='test';"+apiSource,context);
function resolve(url){const i=pending.findIndex(p=>p.url===url);assert(i>=0);pending.splice(i,1)[0].resolve({ok:true,json:async()=>({ok:true})});}
(async()=>{
 const ai=vm.runInContext("api('diagnostics/ai')",context);
 assert.equal(buttons[0].disabled,false);
 const status=vm.runInContext("api('status')",context);
 assert.equal(buttons[0].disabled,true);resolve('/api/status');await status;
 assert.equal(buttons[0].disabled,false);resolve('/api/diagnostics/ai');await ai;
 const payment=vm.runInContext("api('payments/check')",context);
 const rejected=assert.rejects(payment,/Connection changed/);
 const disconnect=vm.runInContext("api('disconnect')",context);
 resolve('/api/disconnect');await disconnect;resolve('/api/payments/check');await rejected;
 assert.equal(buttons[0].disabled,false);
 console.log('Cloud requests keep owner controls available; stale results rejected.');
})().catch(e=>{console.error(e);process.exitCode=1;});
