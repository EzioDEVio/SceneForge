'use strict';
const {app,BrowserWindow,Menu,dialog,session,shell}=require('electron');
const path=require('node:path'),fs=require('node:fs');
const {startBackend,isOwnURL}=require('./backend-process.cjs');
const {createCloseController}=require('./close-controller.cjs');
const updates=require('./updates.cjs');
let updater={check:async()=>{},setBeta:()=>{},beta:()=>false};
let sdAutostartTurnedOff=false;
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
  try{sdAutostartTurnedOff=updates.reviewSdAutostart(dataDir);}catch(e){console.error('SD autostart review failed',e);}
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
 const api=async(path,opts={})=>{const r=await fetch(origin+path,{...opts,headers:{'Content-Type':'application/json','X-SceneForge-Token':ready.token,...(opts.headers||{})}});const v=await r.json().catch(()=>({}));if(!r.ok)throw Error(v.detail||('HTTP '+r.status));return v;};
 let sdSettings={};try{sdSettings=await api('/api/local-image-settings');}catch{}
 async function collectDiagnostics(){
  // Logs, versions and settings only (no API keys, no media), into a folder on the Desktop.
  const out=path.join(app.getPath('desktop'),`SceneForge-diagnostics-${new Date().toISOString().replace(/[:.]/g,'-')}`);
  fs.mkdirSync(out,{recursive:true});
  for(const f of ['desktop-backend.log','updates.log'])try{fs.copyFileSync(path.join(dataDir,'logs',f),path.join(out,f));}catch{}
  try{for(const f of fs.readdirSync(path.join(dataDir,'logs')))if(f.endsWith('.log')&&!fs.existsSync(path.join(out,f)))fs.copyFileSync(path.join(dataDir,'logs',f),path.join(out,f));}catch{}
  let health={};try{health=await api('/api/health');}catch(e){health={error:String(e)};}
  let sd={};try{sd=await api('/api/local-image-settings');}catch{}
  const info={app:app.getVersion(),electron:process.versions.electron,os:`${process.platform} ${require('node:os').release()} ${process.arch}`,
   memoryGB:+(require('node:os').totalmem()/1e9).toFixed(1),cpus:require('node:os').cpus().length,backend:health,stableDiffusion:{folderSet:!!sd.folder,autostart:!!sd.autostart},
   workspace:dataDir,appState:(()=>{try{return JSON.parse(fs.readFileSync(path.join(dataDir,'app-state.json'),'utf8'))}catch{return null}})()};
  fs.writeFileSync(path.join(out,'system.json'),JSON.stringify(info,null,2));
  await dialog.showMessageBox(window,{type:'info',message:'Diagnostics collected',detail:`A folder was created on your Desktop:\n${path.basename(out)}\n\nIt contains logs and system details only (no API keys or media). Attach its files to a GitHub issue or send them to the developer.`});
  shell.openPath(out);
 }
 const aiGuide=()=>dialog.showMessageBox(window,{type:'info',title:'AI in SceneForge',message:'AI is optional: you can make a whole video from your own photos, clips and recordings.',
  detail:'There are two kinds of AI engines:\n\n• Cloud services (OpenAI, Gemini, ElevenLabs, Together, Cloudflare, Hugging Face): fast and high quality, paid or with free allowances. Create an account on their website, copy your API key, then choose AI Engines → Add or change API keys. Keys are stored in your system\'s credential store.\n\n• Local engines (free, run on your computer): Stable Diffusion for images and Chatterbox/Kokoro for voices. They need to be installed separately; see the menu items below for step-by-step help.\n\nThen: images are generated from a scene\'s Media tab (Generate image), voices from the Audio tab (Voice & narration).',buttons:['OK']});
 Menu.setApplicationMenu(Menu.buildFromTemplate([
  {label:'File',submenu:[{label:'Open workspace folder',click:()=>shell.openPath(dataDir)},{label:'Open logs',click:()=>shell.openPath(path.join(dataDir,'logs'))},{type:'separator'},{role:'quit'}]},
  {label:'AI Engines',submenu:[
   {label:'Getting started with AI…',click:()=>aiGuide()},
   {label:'Add or change API keys (OpenAI, ElevenLabs, Gemini…)…',click:()=>window.webContents.executeJavaScript("window.dispatchEvent(new Event('sceneforge-open-settings'))")},
   {type:'separator'},
   {label:'Stable Diffusion (local images)',submenu:[
    {label:'What is this?',click:()=>dialog.showMessageBox(window,{type:'info',title:'Stable Diffusion',message:'Generate images on your own computer, free',detail:'SceneForge can use AUTOMATIC1111 Stable Diffusion WebUI if it is installed on this PC.\n\n1. Install AUTOMATIC1111 (see its GitHub page) and make sure it runs.\n2. In its webui-user.bat, add --api to COMMANDLINE_ARGS.\n3. Here, choose "Choose Stable Diffusion folder…" and pick the folder containing webui-user.bat.\n4. In a scene, use Media → Generate image and pick the local engine.\n\nIt needs a capable graphics card and takes a few minutes to start. It uses a lot of memory while running.',buttons:['OK','Open AUTOMATIC1111 on GitHub'],defaultId:0}).then(r=>{if(r.response===1)shell.openExternal('https://github.com/AUTOMATIC1111/stable-diffusion-webui')})},
    {label:'Choose Stable Diffusion folder…',click:async()=>{try{const result=await dialog.showOpenDialog(window,{title:'Choose the folder containing webui-user.bat',properties:['openDirectory']});if(result.canceled)return;const value=await api('/api/local-image-settings',{method:'PUT',body:JSON.stringify({folder:result.filePaths[0],autostart:false})});await dialog.showMessageBox(window,{message:'Stable Diffusion folder saved',detail:'Use "Start Stable Diffusion now" when you want to generate images. Automatic start is off so SceneForge opens quickly; you can turn it on in this menu.'});}catch(e){dialog.showErrorBox('Local engine setup',String(e.message||e));}}},
    {label:'Start Stable Diffusion now',click:async()=>{try{const state=await api('/api/local-image-start',{method:'POST'});await dialog.showMessageBox(window,{message:state.ready?'Stable Diffusion is ready':(state.message||'Starting Stable Diffusion… this can take a few minutes')});}catch(e){dialog.showErrorBox('Stable Diffusion',String(e.message||e));}}},
    {label:'Start automatically with SceneForge',type:'checkbox',checked:!!sdSettings.autostart,enabled:!!sdSettings.folder,click:async item=>{try{await api('/api/local-image-settings',{method:'PUT',body:JSON.stringify({folder:sdSettings.folder,autostart:item.checked})});sdSettings.autostart=item.checked;}catch(e){item.checked=!item.checked;dialog.showErrorBox('Stable Diffusion',String(e.message||e));}}}
   ]},
   {label:'Local voices (Chatterbox, Kokoro)…',click:()=>dialog.showMessageBox(window,{type:'info',title:'Local voices',message:'Free narration voices on your own computer',detail:'Chatterbox (many languages, including Arabic) and Kokoro (English) run in Docker Desktop.\n\n1. Install Docker Desktop and start it.\n2. In a scene, open Audio → Voice & narration and click Connect Chatterbox or Connect Kokoro.\n3. Choose the engine, a voice and a language, then Generate.\n\nNo account or key is needed. The first start downloads the voice model and can take several minutes.'})},
  ]},
  {label:'Edit',submenu:[{role:'undo'},{role:'redo'},{type:'separator'},{role:'cut'},{role:'copy'},{role:'paste'},{role:'selectAll'}]},
  {label:'View',submenu:[{role:'reload'},{role:'resetZoom'},{role:'zoomIn'},{role:'zoomOut'},{role:'togglefullscreen'},{type:'separator'},{label:'Developer tools (for bug reports)',accelerator:'CmdOrCtrl+Shift+I',click:()=>window.webContents.toggleDevTools()}]},
  {label:'Help',submenu:[
   {label:'Check for updates…',enabled:app.isPackaged,click:()=>updater.check(true)},
   {label:'Receive beta updates',type:'checkbox',checked:updater.beta(),enabled:app.isPackaged,click:item=>updater.setBeta(item.checked)},
   {label:'Collect diagnostics for a bug report…',click:()=>collectDiagnostics()},
   {label:'Open project backups',click:()=>{fs.mkdirSync(path.join(dataDir,'backups'),{recursive:true});shell.openPath(path.join(dataDir,'backups'));}},
   {type:'separator'},
   {label:'SceneForge on GitHub',click:()=>shell.openExternal('https://github.com/EzioDEVio/SceneForge')},
   {label:'About SceneForge Studio',click:()=>dialog.showMessageBox(window,{type:'info',message:`SceneForge Studio ${app.getVersion()}`,detail:'Free and open-source software under the GNU General Public License v3.0 or later. It comes with ABSOLUTELY NO WARRANTY. Bundled components (FFmpeg, fonts, libraries) keep their own licenses; see THIRD_PARTY.md in the installation folder.\n\nProjects are stored separately from the app and are backed up before each update.'})}
  ]}
 ]));
 await window.loadURL(origin);
 if(sdAutostartTurnedOff)setTimeout(()=>dialog.showMessageBox(window,{type:'info',title:'Stable Diffusion',message:'Stable Diffusion no longer starts automatically',
  detail:'It is a heavy engine and can slow the whole computer down while it starts. Start it when you need it: AI Engines → Stable Diffusion → Start Stable Diffusion now. To start it with SceneForge again, tick "Start automatically with SceneForge" in the same menu.'}),1500);
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
