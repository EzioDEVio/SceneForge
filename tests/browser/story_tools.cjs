// Real Chromium, disposable local database, no models or providers.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),os=require('os'),{spawn}=require('child_process'),assert=require('assert/strict');
const root=path.resolve(__dirname,'../..'),data=fs.mkdtempSync(path.join(os.tmpdir(),'sf-story-browser-')),base='http://127.0.0.1:8095';let server,browser,devServer,logs='';
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function api(url,body,method='POST'){const r=await fetch(base+'/api'+url,{method,headers:{'content-type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});assert(r.ok,await r.clone().text());return r.status===204?null:r.json();}
// Playwright's waitForFunction treats a returned Promise as truthy before
// resolving it. Poll API data in Node so a false async result really retries.
async function waitForApi(url,predicate,description){
 const deadline=Date.now()+10000;let snapshot;
 do{snapshot=await api(url,undefined,'GET');
  if(predicate(snapshot))return snapshot;
  await wait(50);
 }while(Date.now()<deadline);
 assert.fail(description+' did not complete; final snapshot: '+JSON.stringify(snapshot));
}
async function waitForSceneIds(pid,expected){
 const project=await waitForApi('/projects/'+pid,p=>JSON.stringify(p.scenes.map(s=>s.id))===JSON.stringify(expected),'Batch scene operation with original ordered IDs');
 assert.deepEqual(project.scenes.map(s=>s.id),expected);
 return project.scenes;
}
async function upload(pid,name){const form=new FormData();form.append('file',new Blob([fs.readFileSync(path.join(root,'examples/fixture_assets',name))]),name);const r=await fetch(base+'/api/assets/upload?project_id='+pid,{method:'POST',body:form});assert(r.ok,await r.clone().text());return r.json();}
(async()=>{try{
 const frontend=process.env.SF_BROWSER_DEV?'http://127.0.0.1:8195':process.env.SF_BROWSER_FRONTEND_URL||base;
 if(process.env.SF_BROWSER_DEV){devServer=spawn(process.execPath,[path.join(root,'frontend/node_modules/vite/bin/vite.js'),'--config','vite.browser-tests.config.ts','--host','127.0.0.1','--port','8195'],{cwd:path.join(root,'frontend'),env:{...process.env,SF_DEV_BACKEND:base}});devServer.stderr.on('data',d=>logs+=d);for(let i=0;i<100;i++){try{if((await fetch(frontend)).ok)break;}catch{}await wait(100);}}

server=spawn('python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8095'],{cwd:path.join(root,'backend'),env:{...process.env,SCENEFORGE_DATA_DIR:data}});server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);
let up=false;for(let i=0;i<150;i++){try{if((await fetch(base+'/api/health')).ok){up=true;break;}}catch{}await wait(100);}assert(up,logs);
let p=await api('/projects',{title:'Section D UI',aspect:'16:9',fps:25});p=await api('/projects/'+p.id,undefined,'GET');const originalIds=p.scenes.map(s=>s.id),sid=p.scenes[0].id;
for(const s of p.scenes)await api('/scenes/'+s.id,{timing_mode:'fixed',requested_duration_ms:4000,font:{captions_enabled:false}},'PATCH');
for(const name of ['image1.png','image2.png']){const a=await upload(p.id,name);await api('/scenes/'+sid+'/shots',{asset_id:a.id});}
const times=[520,1000,2000,3000];await api('/projects/'+p.id,{finishing:{timeline:{version:1,tracks:{},audio_tracks:['A3'],markers:[...times.map((t,i)=>({id:'beat-'+i,time_ms:t,duration_ms:0,label:'♪',color:'purple'})),{id:'manual-first',time_ms:1520,duration_ms:0,label:'First cut',color:'amber'},{id:'manual-second',time_ms:2520,duration_ms:0,label:'Second cut',color:'amber'}]}}},'PATCH');
p=await api('/projects/'+p.id,undefined,'GET');const before=p.scenes[0].shots;
browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{}),args:['--no-sandbox','--disable-dev-shm-usage',...(process.env.CHROMIUM_SINGLE_PROCESS?['--single-process','--no-zygote','--in-process-gpu','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']:[])]});
const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(frontend);await page.getByRole('button',{name:/Section D UI Open project/}).click();await page.getByRole('button',{name:'Skip tour',exact:true}).click();
async function tools(name){await page.getByRole('button',{name:'Edit',exact:true}).click();await page.getByRole('button',{name:name+'…',exact:true}).click();return page.getByRole('dialog',{name:'Story tools',exact:true});}
let dlg=await tools('AutoCut');await dlg.getByRole('button',{name:'Preview AutoCut',exact:true}).click();await dlg.getByLabel('AutoCut preview',{exact:true}).waitFor();assert((await dlg.getByLabel('AutoCut preview',{exact:true}).innerText()).includes('5 picture clips'));assert.equal((await api('/projects/'+p.id,undefined,'GET')).scenes[0].shots.length,2);
await dlg.getByRole('button',{name:'Apply AutoCut',exact:true}).click();await dlg.getByRole('status').filter({hasText:'AutoCut applied'}).waitFor();let edited=(await api('/projects/'+p.id,undefined,'GET')).scenes[0].shots;assert.equal(edited.length,5);
await dlg.getByRole('button',{name:'Close story tools',exact:true}).click();await page.locator('.save-status').filter({hasText:'All changes saved'}).waitFor();await page.keyboard.press('Control+z');await waitForApi('/scenes/'+sid,s=>s.shots.length===2,'AutoCut Undo');assert.deepEqual((await api('/scenes/'+sid,undefined,'GET')).shots,before);await page.locator('.save-status').filter({hasText:'All changes saved'}).waitFor();await page.keyboard.press('Control+y');await waitForApi('/scenes/'+sid,s=>s.shots.length===5,'AutoCut restore');assert.deepEqual((await api('/scenes/'+sid,undefined,'GET')).shots,edited);console.log('PASS real UI AutoCut preview, Apply, Undo and Redo');
await page.getByRole('combobox',{name:'Add beat markers',exact:true}).selectOption('clear');
await waitForApi('/projects/'+p.id,p=>p.finishing_json.timeline.markers.length===2,'Manual marker persistence');
await page.locator('.save-status').filter({hasText:'All changes saved'}).waitFor();
dlg=await tools('AutoCut');const cutSource=dlg.getByRole('combobox',{name:'AutoCut beat source',exact:true});
assert.equal(await cutSource.locator('option[value="timeline"]').innerText(),'Timeline markers (2)');assert.equal(await cutSource.inputValue(),'timeline');
await cutSource.selectOption('timeline');await dlg.getByRole('button',{name:'Preview AutoCut',exact:true}).click();
await dlg.getByLabel('AutoCut preview',{exact:true}).waitFor();assert((await dlg.getByLabel('AutoCut preview',{exact:true}).innerText()).includes('3 picture clips'));assert((await dlg.getByLabel('AutoCut preview',{exact:true}).innerText()).includes('1.52s, 2.52s'));
await dlg.getByRole('button',{name:'Apply AutoCut',exact:true}).click();await dlg.getByRole('status').filter({hasText:'AutoCut applied'}).waitFor();
const manualShots=(await api('/scenes/'+sid,undefined,'GET')).shots;assert.deepEqual(manualShots.map(s=>s.duration_ms),[1520,1000,1480]);
await dlg.getByRole('button',{name:'Close story tools',exact:true}).click();await page.locator('.save-status').filter({hasText:'All changes saved'}).waitFor();await page.keyboard.press('Control+z');
await waitForApi('/scenes/'+sid,s=>s.shots.length===5,'AutoCut restore');assert.deepEqual((await api('/scenes/'+sid,undefined,'GET')).shots,edited);
console.log('PASS two ordinary timeline markers appear as an AutoCut source, preview exact cuts, apply and Undo');

dlg=await tools('Script → Scenes');await dlg.getByRole('textbox',{name:'Script to split',exact:true}).fill('Hello [1].\nThis continues.\n\nأهلا بالعالم.');await dlg.getByRole('button',{name:'Preview scenes',exact:true}).click();await dlg.getByRole('textbox',{name:'Preview scene 1 narration',exact:true}).waitFor();assert.equal(await dlg.getByRole('textbox',{name:'Preview scene 1 narration',exact:true}).inputValue(),'Hello [1].\nThis continues.');await dlg.getByRole('textbox',{name:'Preview scene 2 narration',exact:true}).fill('مرحبا بالعالم.');assert.equal((await api('/projects/'+p.id,undefined,'GET')).scenes.length,3);await dlg.getByRole('button',{name:'Add 2 scenes',exact:true}).click();await dlg.waitFor({state:'detached'});await page.getByText(/2 scenes added/).first().waitFor();let added=(await api('/projects/'+p.id,undefined,'GET')).scenes;assert.equal(added.length,5);assert.equal(added[4].spoken_text,'مرحبا بالعالم.');assert.deepEqual(added.slice(0,3).map(s=>s.id),originalIds);
// Delay each restored imported scene so the test exercises the intermediate
// four-scene state encountered in CI, without relaxing the final expectation.
let delayedRestores=0;
await page.route('**/api/scenes/*/restore',async route=>{
 if(added.slice(3).some(scene=>new URL(route.request().url()).pathname==='/api/scenes/'+scene.id+'/restore')){
  delayedRestores++;await wait(300);
 }
 await route.continue();
});
for(let cycle=0;cycle<3;cycle++){
 await page.locator('.save-status').filter({hasText:'All changes saved'}).waitFor();
 await page.keyboard.press('Control+z');
 await waitForSceneIds(p.id,originalIds);
 await page.locator('.save-status').filter({hasText:'All changes saved'}).waitFor();
 await page.keyboard.press('Control+y');
 const restored=await waitForSceneIds(p.id,added.map(s=>s.id));
 await page.locator('.save-status').filter({hasText:'All changes saved'}).waitFor();
 assert.deepEqual(restored.map(s=>s.id),added.map(s=>s.id));
 assert.deepEqual(restored.slice(0,3).map(s=>s.id),originalIds);
 assert.deepEqual(restored.slice(3).map(s=>s.spoken_text),added.slice(3).map(s=>s.spoken_text));
}
assert.equal(delayedRestores,6,'Every batch Redo must restore both imported scenes');
await page.unroute('**/api/scenes/*/restore');
console.log('PASS editable script preview, Arabic, append and three batch Undo/Redo cycles with delayed restores');
// The generated scenes must open for editing from the scene list and accept media.
await page.getByRole('button',{name:'Select scene 4: Scene 1',exact:true}).click();
let imported=page.getByRole('region',{name:'Edit Scene 1',exact:true});
await imported.waitFor();assert.equal(await imported.getByRole('textbox',{name:'Narration script',exact:true}).inputValue(),'Hello [1].\nThis continues.');
await page.getByRole('button',{name:'Select scene 5: Scene 2',exact:true}).click();
imported=page.getByRole('region',{name:'Edit Scene 2',exact:true});await imported.waitFor();assert.equal(await imported.getByRole('textbox',{name:'Narration script',exact:true}).inputValue(),'مرحبا بالعالم.');
const mediaChooser=page.waitForEvent('filechooser');
await page.getByRole('button',{name:'Storyboard scene 5',exact:true}).getByText('Add media',{exact:true}).click();
await (await mediaChooser).setFiles(path.join(root,'examples/fixture_assets/image1.png'));
await waitForApi('/scenes/'+added[4].id,s=>s.shots.length===1,'Generated scene media persistence');
assert.equal((await api('/scenes/'+added[4].id,undefined,'GET')).spoken_text,'مرحبا بالعالم.');
console.log('PASS generated scenes open from scene list, show imported narration and accept timeline media');

dlg=await tools('Project templates');await dlg.getByRole('textbox',{name:'Template name',exact:true}).fill('Reusable story');await dlg.getByRole('button',{name:'Save current project as template',exact:true}).click();await dlg.getByRole('button',{name:'Use Reusable story',exact:true}).waitFor();await dlg.getByRole('button',{name:'Close story tools',exact:true}).click();await page.getByRole('button',{name:'Projects',exact:true}).click();await page.getByRole('button',{name:'Project templates…',exact:true}).click();dlg=page.getByRole('dialog',{name:'Story tools',exact:true});await dlg.getByRole('textbox',{name:'Template name',exact:true}).fill('Template copy');await dlg.getByRole('button',{name:'Use Reusable story',exact:true}).click();await dlg.waitFor({state:'detached'});await page.getByRole('textbox',{name:'Project name',exact:true}).waitFor();assert.equal(await page.getByRole('textbox',{name:'Project name',exact:true}).inputValue(),'Template copy');const projects=await api('/projects',undefined,'GET'),copy=projects.find(v=>v.title==='Template copy');assert(copy&&copy.id!==p.id);console.log('PASS saved templates available on home and create independent project');
// Add a real video, reopen to load it, then verify stabilization has its own Undo entry.
const cp=await api('/projects/'+copy.id,undefined,'GET'),vs=cp.scenes[0].id,v=await upload(copy.id,'clip1.mp4');await api('/scenes/'+vs+'/shots',{asset_id:v.id});await page.getByRole('button',{name:'Projects',exact:true}).click();await page.getByRole('button',{name:/Template copy Open project/}).click();dlg=await tools('Stabilize video');await dlg.getByRole('slider',{name:'Stabilization strength',exact:true}).fill('80');await dlg.getByRole('button',{name:'Apply stabilization',exact:true}).click();await dlg.getByRole('status').filter({hasText:'Saved.'}).waitFor();assert.equal((await api('/scenes/'+vs,undefined,'GET')).look_json.stabilize.strength,80);await page.screenshot({path:path.join(data,'story-tools.png')});await dlg.getByRole('button',{name:'Close story tools',exact:true}).click();await page.locator('.save-status').filter({hasText:'All changes saved'}).waitFor();await page.keyboard.press('Control+z');await waitForApi('/scenes/'+vs,s=>!s.look_json.stabilize,'Stabilization Undo');await page.locator('.save-status').filter({hasText:'All changes saved'}).waitFor();await page.keyboard.press('Control+y');await waitForApi('/scenes/'+vs,s=>s.look_json.stabilize?.strength===80,'Stabilization Redo');console.log('PASS stabilization slider, save, Undo and Redo');
await page.reload();await page.getByRole('button',{name:/Template copy Open project/}).click();assert.equal((await api('/scenes/'+vs,undefined,'GET')).look_json.stabilize.strength,80);assert.equal((await api('/projects/'+copy.id,undefined,'GET')).scenes.length,5);assert.equal(errors.length,0,errors.join('\n'));fs.mkdirSync(path.join(root,'docs/qa'),{recursive:true});fs.copyFileSync(path.join(data,'story-tools.png'),path.join(root,'docs/qa/section-d-story-tools.png'));console.log('PASS persistence after reload; no browser JavaScript errors');
}catch(e){console.error(e);console.error(logs.slice(-4000));process.exitCode=1;}finally{devServer?.kill();if(browser)await browser.close();if(server){server.kill('SIGTERM');await wait(250);}fs.rmSync(data,{recursive:true,force:true});}})();
