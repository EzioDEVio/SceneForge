const {test}=require('node:test');
const assert=require('node:assert/strict');
const {createCloseController}=require('../close-controller.cjs');
test('cancel leaves backend and window alive',async()=>{
 const calls=[];
 await createCloseController({confirm:async()=>false,save:async()=>calls.push('save'),stop:async()=>calls.push('stop'),exit:()=>calls.push('exit'),report:async()=>{}})();
 assert.deepEqual(calls,[]);
});
test('failed save never shuts down, retry can succeed',async()=>{
 const calls=[];let saved=false;
 const close=createCloseController({confirm:async()=>true,save:async()=>saved,stop:async()=>calls.push('stop'),exit:()=>calls.push('exit'),report:async()=>calls.push('warning')});
 await close();assert.deepEqual(calls,['warning']);
 saved=true;await close();assert.deepEqual(calls,['warning','stop','exit']);
});
test('repeated close waits for acknowledged save before backend shutdown',async()=>{
 const calls=[];let resolveSave;
 const close=createCloseController({confirm:async()=>{calls.push('confirm');return true;},save:()=>new Promise(r=>resolveSave=r),stop:async()=>calls.push('stop'),exit:()=>calls.push('exit'),report:async()=>{}});
 const first=close();await new Promise(r=>setImmediate(r));await close();
 assert.deepEqual(calls,['confirm']);resolveSave(true);await first;
 assert.deepEqual(calls,['confirm','stop','exit']);
});
