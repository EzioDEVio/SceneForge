'use strict';
const {app,BrowserWindow,Menu,dialog,session,shell}=require('electron');
const path=require('node:path'),fs=require('node:fs');
const {startBackend,isOwnURL}=require('./backend-process.cjs');
const {createCloseController}=require('./close-controller.cjs');
const updates=require('./updates.cjs');
let updater={check:async()=>{},setBeta:()=>{},beta:()=>false};
let window,backend,quitting=false,origin;
const smoke=process.argv.includes('--smoke-test');
let failedStartup=false;
const requestClose=createCloseController({
 confirm:async()=>smoke||failedStartup||(await dialog.showMessageBox(window,{type:'question',title:'Close SceneForge?',message:'Save your project and exit?',detail:'SceneForge saves automatically. Save and exit also waits for any pending project edits. Changes already saved will be kept.',buttons:['Save and exit','Cancel'],defaultId:1,cancelId:1,noLink:true})).response===0,
 save:async()=>smoke||failedStartup||!origin||await window.webContents.executeJavaScript('typeof window.__sceneForgePrepareClose === "function" ? window.__sceneForgePrepareClose() : false'),
 stop:()=>Promise.resolve(backend?.stop()),
 exit:()=>{quitting=true;window?.webContents.on('will-prevent-unload',e=>e.preventDefault());app.quit();},
 report:message=>dialog.showMessageBox(window,{type:'warning',title:'SceneForge is still open',message})
});
// One user-data folder name for every platform; projects from older names are migrated in boot().
app.setName('SceneForge Studio');
app.setPath('userData',path.join(app.getPath('appData'),'SceneForge Studio'));
const gotLock=app.requestSingleInstanceLock();
if(!gotLock)app.quit();
else{
 app.on('second-instance',()=>{if(window){if(window.isMinimized())window.restore();window.focus()}});
 app.on('window-all-closed',()=>app.quit());
 app.on('before-quit',e=>{if(quitting)return;e.preventDefault();void requestClose();});
 app.whenReady().then(boot).catch(fail);
}
function fail(e){
 failedStartup=true;
 if(smoke&&process.env.SCENEFORGE_SMOKE_REPORT)fs.writeFileSync(process.env.SCENEFORGE_SMOKE_REPORT,JSON.stringify({ok:false,error:String(e)}));
 else dialog.showErrorBox('SceneForge could not start',String(e.message||e));
 app.quit();
}
async function boot(){
 const dataDir=smoke?fs.mkdtempSync(path.join(app.getPath('temp'),'sceneforge-smoke-')):path.join(app.getPath('userData'),'workspace');
 const exe=process.platform==='win32'?'.exe':'';
 const resources=app.isPackaged?path.join(process.resourcesPath,'app-resources'):path.resolve(__dirname,'..');
 const binary=app.isPackaged?path.join(process.resourcesPath,'backend','sceneforge-backend'+exe):path.resolve(__dirname,'build/backend/sceneforge-backend/sceneforge-backend'+exe);
 const ffmpegDir=app.isPackaged?path.join(process.resourcesPath,'ffmpeg','bin'):path.join(__dirname,'vendor/ffmpeg/bin');
 for(const f of [binary,path.join(ffmpegDir,'ffmpeg'+exe),path.join(ffmpegDir,'ffprobe'+exe)])if(!fs.existsSync(f))throw Error('Missing packaged component: '+path.basename(f)+'. Repair the installation.');
 if(!smoke){
  // Before the backend opens (and may upgrade) the database: carry projects over from
  // the old app name, and back up the database whenever the app version changed.
  try{updates.migrateLegacyWorkspace(app.getPath('appData'),dataDir);}catch(e){console.error('workspace migration failed',e);}
  try{updates.backupOnVersionChange(dataDir,app.getVersion());}catch(e){console.error('version backup failed',e);}
 }
 window=new BrowserWindow({title:'SceneForge',width:1500,height:950,minWidth:1100,minHeight:720,show:!smoke,backgroundColor:'#202329',webPreferences:{sandbox:true,contextIsolation:true,nodeIntegration:false,webSecurity:true,partition:'sceneforge-desktop'}});
 window.on('close',e=>{if(quitting)return;e.preventDefault();void requestClose();});
 window.webContents.setWindowOpenHandler(()=>({action:'deny'}));
 window.webContents.on('will-navigate',(e,url)=>{if(!origin||!isOwnURL(url,origin))e.preventDefault()});
 window.webContents.session.setPermissionRequestHandler((_wc,_permission,callback)=>callback(false));
 await window.loadFile(path.join(__dirname,'welcome.html'));
 if(smoke)process.env.SCENEFORGE_SD_AUTOSTART='0';
 backend=startBackend({executable:binary,resources,dataDir,ffmpegDir,onExit:()=>fail(Error('The local editor stopped unexpectedly. Restart SceneForge. Your saved projects remain in the workspace.'))});
 const ready=await backend.launched;origin=ready.origin;
 const health=await fetch(origin+'/api/health',{headers:{'X-SceneForge-Token':ready.token}});if(!health.ok)throw Error('The packaged backend failed its health check.');
 window.webContents.session.webRequest.onBeforeSendHeaders({urls:[origin+'/*']},(details,callback)=>{callback({requestHeaders:{...details.requestHeaders,'X-SceneForge-Token':ready.token}})});
 Menu.setApplicationMenu(Menu.buildFromTemplate([
  {label:'File',submenu:[{label:'Open workspace folder',click:()=>shell.openPath(dataDir)},{label:'Open logs',click:()=>shell.openPath(path.join(dataDir,'logs'))},{type:'separator'},{role:'quit'}]},
  {label:'AI Engines',submenu:[{label:'Choose Stable Diffusion folder…',click:async()=>{try{const result=await dialog.showOpenDialog(window,{title:'Choose the folder containing webui-user.bat',properties:['openDirectory']});if(result.canceled)return;const response=await fetch(origin+'/api/local-image-settings',{method:'PUT',headers:{'Content-Type':'application/json','X-SceneForge-Token':ready.token},body:JSON.stringify({folder:result.filePaths[0],autostart:true})});const value=await response.json();if(!response.ok)throw Error(value.detail);const launched=await fetch(origin+'/api/local-image-start',{method:'POST',headers:{'X-SceneForge-Token':ready.token}});const state=await launched.json();await dialog.showMessageBox(window,{message:state.ready?'Stable Diffusion is ready':state.message||'Starting Stable Diffusion',detail:'The folder is saved. You can change automatic startup under Generate image → Local engine setup.'});}catch(e){dialog.showErrorBox('Local engine setup',String(e.message||e));}}}]},
  {label:'Edit',submenu:[{role:'undo'},{role:'redo'},{type:'separator'},{role:'cut'},{role:'copy'},{role:'paste'},{role:'selectAll'}]},
  {label:'View',submenu:[{role:'reload'},{role:'resetZoom'},{role:'zoomIn'},{role:'zoomOut'},{role:'togglefullscreen'}]},
  {label:'Help',submenu:[
   {label:'Check for updates…',enabled:app.isPackaged,click:()=>updater.check(true)},
   {label:'Receive beta updates',type:'checkbox',checked:updater.beta(),enabled:app.isPackaged,click:item=>updater.setBeta(item.checked)},
   {label:'Open project backups',click:()=>{fs.mkdirSync(path.join(dataDir,'backups'),{recursive:true});shell.openPath(path.join(dataDir,'backups'));}},
   {type:'separator'},
   {label:'SceneForge on GitHub',click:()=>shell.openExternal('https://github.com/EzioDEVio/SceneForge')},
   {label:'About SceneForge Studio',click:()=>dialog.showMessageBox(window,{type:'info',message:`SceneForge Studio ${app.getVersion()}`,detail:'Free and open-source software under the GNU General Public License v3.0 or later. It comes with ABSOLUTELY NO WARRANTY. Bundled components (FFmpeg, fonts, libraries) keep their own licenses; see THIRD_PARTY.md in the installation folder.\n\nProjects are stored separately from the app and are backed up before each update.'})}
  ]}
 ]));
 await window.loadURL(origin);
 if(!smoke&&app.isPackaged){
  updater=updates.setupUpdates({app,dialog,shell,getWindow:()=>window,workspaceDir:dataDir,userDataDir:app.getPath('userData'),
   log:m=>{try{fs.appendFileSync(path.join(dataDir,'logs','updates.log'),`${new Date().toISOString()} ${m}\n`);}catch{}}});
  setTimeout(()=>updater.check(false),15000);                 // after startup settles
  setInterval(()=>updater.check(false),6*60*60*1000);         // and every 6 hours
 }
 if(smoke){
  const text=await window.webContents.executeJavaScript('document.body.innerText');
  if(!text.includes('SceneForge'))throw Error('Packaged frontend did not load.');
  if(process.env.SCENEFORGE_SMOKE_REPORT)fs.writeFileSync(process.env.SCENEFORGE_SMOKE_REPORT,JSON.stringify({ok:true,version:app.getVersion()}));
  app.quit();
 }
}
