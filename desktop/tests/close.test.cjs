const {test}=require('node:test');
const assert=require('node:assert/strict');
const {createCloseController}=require('../close-controller.cjs');

const make=(decision,result={ready:true})=>{
 const calls=[];
 const close=createCloseController({
  confirm:async()=>decision,
  prepare:async(save,exiting)=>{calls.push('prepare:'+save+':'+exiting);return result;},
  stop:async()=>calls.push('stop'),exit:()=>calls.push('exit'),report:async(reason)=>calls.push('report:'+reason),
 });
 return {calls,close};
};

test('Cancel leaves backend and window alive',async()=>{
 const {calls,close}=make('cancel');await close();assert.deepEqual(calls,[]);
});
test('Save writes changes and leaves SceneForge open',async()=>{
 const {calls,close}=make('save');await close();assert.deepEqual(calls,['prepare:true:false']);
});
test('Don’t save skips project flush and exits after close preflight',async()=>{
 const {calls,close}=make('discard');await close();assert.deepEqual(calls,['prepare:false:true','stop','exit']);
});
test('Save and exit saves before backend shutdown',async()=>{
 const {calls,close}=make('save-and-exit');await close();assert.deepEqual(calls,['prepare:true:true','stop','exit']);
});
test('Active work blocks Don’t save exit',async()=>{
 const {calls,close}=make('discard',{ready:false,reason:'active-work'});await close();
 assert.deepEqual(calls,['prepare:false:true','report:active-work']);
});
test('Failed save keeps app open for recovery',async()=>{
 const {calls,close}=make('save-and-exit',{ready:false,reason:'save-failed'});await close();
 assert.deepEqual(calls,['prepare:true:true','report:save-failed']);
});
test('Repeated close requests do not duplicate an in-flight save or shutdown',async()=>{
 const calls=[];let resolvePrepare;
 const close=createCloseController({confirm:async()=>{calls.push('confirm');return 'save-and-exit';},prepare:()=>new Promise(r=>resolvePrepare=r),stop:async()=>calls.push('stop'),exit:()=>calls.push('exit'),report:async reason=>calls.push('report:'+reason)});
 const first=close();await new Promise(r=>setImmediate(r));await close();
 assert.deepEqual(calls,['confirm']);resolvePrepare({ready:true});await first;assert.deepEqual(calls,['confirm','stop','exit']);
});
