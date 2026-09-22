'use strict';
const {app,BrowserWindow,Menu,dialog,session,shell}=require('electron');
const path=require('node:path'),fs=require('node:fs');
const {startBackend,isOwnURL}=require('./backend-process.cjs');
let window,backend,quitting=false,origin;
const smoke=process.argv.includes('--smoke-test');
const gotLock=app.requestSingleInstanceLock();
if(!gotLock)app.quit();
else{
 app.on('second-instance',()=>{if(window){if(window.isMinimized())window.restore();window.focus()}});
 app.on('window-all-closed',()=>app.quit());
 app.on('before-quit',e=>{if(quitting)return;e.preventDefault();quitting=true;Promise.resolve(backend?.stop()).finally(()=>app.quit())});
 app.whenReady().then(boot).catch(fail);
}
function fail(e){
 if(smoke&&process.env.SCENEFORGE_SMOKE_REPORT)fs.writeFileSync(process.env.SCENEFORGE_SMOKE_REPORT,JSON.stringify({ok:false,error:String(e)}));
 else dialog.showErrorBox('SceneForge could not start',String(e.message||e));
 app.quit();
}
async function boot(){
 const dataDir=smoke?fs.mkdtempSync(path.join(app.getPath('temp'),'sceneforge-smoke-')):path.join(app.getPath('userData'),'workspace');
 const resources=app.isPackaged?path.join(process.resourcesPath,'app-resources'):path.resolve(__dirname,'..');
 const binary=app.isPackaged?path.join(process.resourcesPath,'backend','sceneforge-backend.exe'):path.resolve(__dirname,'build/backend/sceneforge-backend/sceneforge-backend.exe');
 const ffmpegDir=app.isPackaged?path.join(process.resourcesPath,'ffmpeg','bin'):path.join(__dirname,'vendor/ffmpeg/bin');
 for(const f of [binary,path.join(ffmpegDir,'ffmpeg.exe'),path.join(ffmpegDir,'ffprobe.exe')])if(!fs.existsSync(f))throw Error('Missing packaged component: '+path.basename(f)+'. Repair the installation.');
 window=new BrowserWindow({width:1500,height:950,minWidth:1100,minHeight:720,show:!smoke,backgroundColor:'#202329',webPreferences:{sandbox:true,contextIsolation:true,nodeIntegration:false,webSecurity:true,partition:'sceneforge-desktop'}});
 window.webContents.setWindowOpenHandler(()=>({action:'deny'}));
 window.webContents.on('will-navigate',(e,url)=>{if(!origin||!isOwnURL(url,origin))e.preventDefault()});
 window.webContents.session.setPermissionRequestHandler((_wc,_permission,callback)=>callback(false));
 await window.loadFile(path.join(__dirname,'welcome.html'));
 backend=startBackend({executable:binary,resources,dataDir,ffmpegDir,onExit:()=>fail(Error('The local editor stopped unexpectedly. Restart SceneForge. Your saved projects remain in the workspace.'))});
 const ready=await backend.launched;origin=ready.origin;
 const health=await fetch(origin+'/api/health',{headers:{'X-SceneForge-Token':ready.token}});if(!health.ok)throw Error('The packaged backend failed its health check.');
 window.webContents.session.webRequest.onBeforeSendHeaders({urls:[origin+'/*']},(details,callback)=>{callback({requestHeaders:{...details.requestHeaders,'X-SceneForge-Token':ready.token}})});
 Menu.setApplicationMenu(Menu.buildFromTemplate([
  {label:'File',submenu:[{label:'Open workspace folder',click:()=>shell.openPath(dataDir)},{label:'Open logs',click:()=>shell.openPath(path.join(dataDir,'logs'))},{type:'separator'},{role:'quit'}]},
  {label:'Edit',submenu:[{role:'undo'},{role:'redo'},{type:'separator'},{role:'cut'},{role:'copy'},{role:'paste'},{role:'selectAll'}]},
  {label:'View',submenu:[{role:'reload'},{role:'resetZoom'},{role:'zoomIn'},{role:'zoomOut'},{role:'togglefullscreen'}]},
  {label:'Help',submenu:[{label:'About Desktop Alpha',click:()=>dialog.showMessageBox(window,{type:'info',message:'SceneForge Desktop Alpha',detail:'Core editor and FFmpeg are bundled. Local AI engines still require an existing installation in this alpha. Projects are stored separately from application files.'})}]}
 ]));
 await window.loadURL(origin);
 if(smoke){
  const text=await window.webContents.executeJavaScript('document.body.innerText');
  if(!text.includes('SceneForge'))throw Error('Packaged frontend did not load.');
  if(process.env.SCENEFORGE_SMOKE_REPORT)fs.writeFileSync(process.env.SCENEFORGE_SMOKE_REPORT,JSON.stringify({ok:true,version:app.getVersion()}));
  app.quit();
 }
}
