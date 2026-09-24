'use strict';
// Keep confirmation/save/shutdown serialized, even when X is pressed twice.
function createCloseController({confirm,save,stop,exit,report}) {
 let pending=false;
 return async function requestClose(){
  if(pending)return;
  pending=true;
  try{
   if(!await confirm())return;
   if(!await save()){await report('Changes could not be saved, or work is still running. SceneForge will stay open. Wait for the operation to finish or resolve the save error, then try again.');return;}
   await stop();
   exit();
  }catch{await report('SceneForge could not finish saving. The application will stay open.');}
  finally{pending=false;}
 };
}
module.exports={createCloseController};
