'use strict';
// RouterOS duration values sort by time rather than their display strings.
globalThis.accountTableUtils={
 duration(value){
  if(!value||value==='unlimited'||value==='0s'||value==='0')return 0;
  const text=String(value);let total=0;
  for(const m of text.matchAll(/(\d+(?:\.\d+)?)(w|d|h|ms|m|s)/g))total+=Number(m[1])*({w:604800,d:86400,h:3600,m:60,s:1,ms:0.001}[m[2]]);
  const clock=text.match(/(\d+):(\d{2}):(\d{2}(?:\.\d+)?)/);
  if(clock)total+=Number(clock[1])*3600+Number(clock[2])*60+Number(clock[3]);
  return total;
 },
 select(users,active,{query='',profile='',status='',key='name',direction=1}){
  const state=u=>['true','yes'].includes(u.disabled)?'Disabled':active.has(u.name)?'Online':'Offline';
  const value=u=>key==='status'?state(u):key==='uptime'?this.duration(u.uptime):key==='allowance'?(this.duration(u['limit-uptime'])||Infinity):String(u[key]||'');
  const q=query.trim().toLocaleLowerCase();
  return users.filter(u=>(!q||[u.name,u.profile,state(u)].some(v=>String(v||'').toLocaleLowerCase().includes(q)))&&(!profile||u.profile===profile)&&(!status||state(u)===status)).slice().sort((a,b)=>{
   const x=value(a),y=value(b);
   const order=typeof x==='number'?(x===y?0:x<y?-1:1):x.localeCompare(y,undefined,{numeric:true,sensitivity:'base'});
   return direction*order||String(a.name).localeCompare(String(b.name),undefined,{numeric:true});
  });
 }
};
