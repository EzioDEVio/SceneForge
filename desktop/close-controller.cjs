'use strict';
// Serialize the native close flow so repeated X presses cannot duplicate saves or shutdown.
function createCloseController({confirm,prepare,stop,exit,report}) {
 let pending=false;
 return async function requestClose(){
  if(pending)return;
  pending=true;
  try{
   const decision=await confirm();
   if(decision===false||decision==='cancel'||decision==null)return;
   const shouldSave=decision==='save'||decision==='save-and-exit';
   const shouldExit=decision!=='save';
   const result=await prepare(shouldSave,shouldExit);
   if(!result?.ready){await report(result?.reason||'save-failed');return;}
   if(!shouldExit)return;
   await stop();
   exit();
  }catch{await report('save-failed');}
  finally{pending=false;}
 };
}
module.exports={createCloseController};
