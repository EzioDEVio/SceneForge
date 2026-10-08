// Real Chromium, disposable local database, no models or providers.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),os=require('os'),{spawn}=require('child_process'),assert=require('assert/strict');
const root=path.resolve(__dirname,'../..'),data=fs.mkdtempSync(path.join(os.tmpdir(),'sf-owner-browser-')),base='http://127.0.0.1:8096';let server,browser,devServer,logs='';
const qa=process.env.SF_QA_DIR||path.join(data,'qa');
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function api(url,body,method='POST'){const r=await fetch(base+'/api'+url,{method,headers:{'content-type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});assert(r.ok,await r.clone().text());return r.status===204?null:r.json();}
async function upload(pid,name){const form=new FormData();form.append('file',new Blob([fs.readFileSync(path.join(root,'examples/fixture_assets',name))]),name);const r=await fetch(base+'/api/assets/upload?project_id='+pid,{method:'POST',body:form});assert(r.ok,await r.clone().text());return r.json();}
(async()=>{try{
 const frontend=process.env.SF_BROWSER_DEV?'http://127.0.0.1:8196':process.env.SF_BROWSER_FRONTEND_URL||base;
 if(process.env.SF_BROWSER_DEV){devServer=spawn(process.execPath,[path.join(root,'frontend/node_modules/vite/bin/vite.js'),'--config','vite.browser-tests.config.ts','--host','127.0.0.1','--port','8196'],{cwd:path.join(root,'frontend'),env:{...process.env,SF_DEV_BACKEND:base}});devServer.stderr.on('data',d=>logs+=d);for(let i=0;i<100;i++){try{if((await fetch(frontend)).ok)break;}catch{}await wait(100);}}

server=spawn('python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8096'],{cwd:path.join(root,'backend'),env:{...process.env,SCENEFORGE_DATA_DIR:data}});server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);
let up=false;for(let i=0;i<150;i++){try{if((await fetch(base+'/api/health')).ok){up=true;break;}}catch{}await wait(100);}assert(up,logs);
let p=await api('/projects',{title:'Owner fixes',aspect:'16:9',fps:25});p=await api('/projects/'+p.id,undefined,'GET');const originalIds=p.scenes.map(s=>s.id),sid=p.scenes[0].id;
for(const s of p.scenes)await api('/scenes/'+s.id,{timing_mode:'fixed',requested_duration_ms:4000,font:{captions_enabled:false}},'PATCH');
for(const name of ['image1.png','image2.png']){const a=await upload(p.id,name);await api('/scenes/'+sid+'/shots',{asset_id:a.id});}
await api('/projects/'+p.id,{aspect:'16:9'},'PATCH');
const times=[520,1000,2000,3000];await api('/projects/'+p.id,{finishing:{timeline:{version:1,tracks:{},audio_tracks:['A3'],markers:[...times.map((t,i)=>({id:'beat-'+i,time_ms:t,duration_ms:0,label:'♪',color:'purple'})),{id:'manual-first',time_ms:1520,duration_ms:0,label:'First cut',color:'amber'},{id:'manual-second',time_ms:2520,duration_ms:0,label:'Second cut',color:'amber'}]}}},'PATCH');
p=await api('/projects/'+p.id,undefined,'GET');const before=p.scenes[0].shots;
browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{}),args:['--no-sandbox','--disable-dev-shm-usage',...(process.env.CHROMIUM_SINGLE_PROCESS?['--single-process','--no-zygote','--in-process-gpu','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']:[])]});
const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(frontend);await page.getByRole('button',{name:/Owner fixes Open project/}).click();await page.getByRole('button',{name:'Skip tour',exact:true}).click();

fs.mkdirSync(qa,{recursive:true});

const read=()=>api('/scenes/'+sid,undefined,'GET');
const saved=()=>page.locator('.save-status').filter({hasText:'All changes saved'}).waitFor();
const editor=page.locator('.scene-editor:not([hidden])');
await page.getByRole('tab',{name:'Effects',exact:true}).click();await page.getByRole('tab',{name:/More effects/}).click();
while(await page.locator('button.fx-group-head[aria-expanded="false"]').count())await page.locator('button.fx-group-head[aria-expanded="false"]').first().click();
await page.getByRole('switch',{name:'Map route',exact:true}).click();
await page.getByLabel('Label for stop 1',{exact:true}).fill('Spain');await page.getByLabel('Label for stop 2',{exact:true}).fill('Rome');await page.getByLabel('Label for stop 3',{exact:true}).fill('London');
await page.getByRole('button',{name:'Reverse journey',exact:true}).click();
assert.equal(await page.getByLabel('Label for stop 1',{exact:true}).inputValue(),'London');
await page.getByRole('button',{name:'Reverse journey',exact:true}).click();
await editor.locator('.editor-draft-actions').getByRole('button',{name:'Apply changes',exact:true}).click();await saved();
assert.deepEqual((await read()).look_json.route.labels,['Spain','Rome','London']);
await page.getByLabel('Label for stop 3',{exact:true}).fill('London final');
await editor.locator('.editor-draft-actions').getByRole('button',{name:'Apply changes',exact:true}).click();await saved();assert.equal((await read()).look_json.route.labels[2],'London final');
await page.getByRole('button',{name:'Undo timeline edit',exact:true}).click();await saved();assert.equal((await read()).look_json.route.labels[2],'London');
await page.getByRole('button',{name:'Redo timeline edit',exact:true}).click();await saved();assert.equal((await read()).look_json.route.labels[2],'London final');
await page.getByRole('radio',{name:'Plane',exact:true}).click();await page.getByLabel('Label for stop 3',{exact:true}).fill('London');
assert.equal(await editor.locator('.route-preview-label').count(),3);
await page.screenshot({path:path.join(qa,'owner-route-layout.png'),fullPage:true});
await editor.locator('.editor-draft-actions').getByRole('button',{name:'Cancel changes',exact:true}).click();await saved();
console.log('PASS immediate final label Apply, Reverse, all completed-preview labels, Undo/Redo and marker layout');
await page.getByRole('tab',{name:'Motion',exact:true}).click();await page.getByRole('button',{name:'Push & pan right',exact:true}).click();
// Force a poll failure to verify a useful connection state and recovery, without starting a real job.
let offline=true;await page.route('**/api/scenes/*/draft-preview',r=>r.fulfill({json:{job_id:'qa-disconnected'}}));
await page.route('**/api/jobs/qa-disconnected',r=>offline?r.fulfill({status:503,json:{detail:'Disconnected test'}}):r.fulfill({json:{id:'qa-disconnected',status:'cancelled',progress:0,stage:'Stopped'}}));
await editor.getByRole('button',{name:'Render draft preview',exact:true}).click();
await editor.getByRole('button',{name:'Retry connection',exact:true}).waitFor();assert((await editor.locator('.editor-draft-companion').innerText()).includes('Cannot check the render'));
offline=false;await editor.getByRole('button',{name:'Retry connection',exact:true}).click();await editor.getByRole('button',{name:'Render draft preview',exact:true}).waitFor({state:'visible'});
await page.waitForFunction(()=>document.querySelector('.editor-draft-actions button')?.disabled===false);
await page.unroute('**/api/scenes/*/draft-preview');await page.unroute('**/api/jobs/qa-disconnected');
await editor.getByRole('button',{name:'Render draft preview',exact:true}).click();await editor.locator('.editor-draft-companion video').waitFor({timeout:120000});
await page.waitForFunction(()=>document.querySelector('.scene-editor:not([hidden]) .editor-draft-companion video')?.readyState>=2,{},{timeout:30000});
await editor.locator('.editor-draft-companion video').evaluate(v=>{v.currentTime=3.8;});await page.waitForTimeout(500);
const monitor=await editor.locator('.editor-draft-companion').boundingBox();assert(monitor.width<=440&&monitor.height<400,JSON.stringify(monitor));
assert.equal(await editor.locator('.editor-draft-companion').getByRole('button',{name:'Apply changes',exact:true}).count(),0);
await page.screenshot({path:path.join(qa,'owner-draft-preview.png'),fullPage:true});
await editor.getByRole('button',{name:'Minimize draft preview',exact:true}).click();await editor.getByRole('button',{name:'Open draft companion',exact:true}).click();await editor.locator('.editor-draft-companion video').waitFor();
await editor.locator('.editor-draft-actions').getByRole('button',{name:'Cancel changes',exact:true}).click();
console.log('PASS poll failure, Retry, real render, compact media monitor and minimize/restore');
await page.getByRole('button',{name:'Edit',exact:true}).click();await page.getByRole('button',{name:'AutoCut…',exact:true}).click();
let dlg=page.getByRole('dialog',{name:'Story tools'});await dlg.getByRole('button',{name:'Preview AutoCut',exact:true}).click();await dlg.getByLabel('AutoCut preview',{exact:true}).waitFor();await dlg.getByRole('button',{name:'Apply AutoCut',exact:true}).click();await dlg.getByRole('status').filter({hasText:'AutoCut applied'}).waitFor();await dlg.getByRole('button',{name:'Close story tools',exact:true}).click();await saved();
assert.equal(await page.getByRole('button',{name:'Storyboard scene 1',exact:true}).locator('.picture-shot').count(),5);
await page.getByRole('button',{name:'Maximize timeline',exact:true}).click();await page.screenshot({path:path.join(qa,'owner-autocut-picture-cuts.png'),fullPage:true});
await page.getByRole('button',{name:'Storyboard scene 2',exact:true}).click({modifiers:['Control']});
assert.equal(await page.locator('.picture-clip.multi').count(),2);await page.screenshot({path:path.join(qa,'owner-linked-selection.png'),fullPage:true});assert.equal(await page.locator('.narration-clip.scene-linked-selected').count(),2);
const drag=page.getByRole('button',{name:'Storyboard scene 1',exact:true}),target=page.getByRole('button',{name:'Storyboard scene 3',exact:true});
const box=await target.boundingBox();await drag.dragTo(target,{targetPosition:{x:box.width-4,y:20}});await saved();
let order=(await api('/projects/'+p.id,undefined,'GET')).scenes.map(s=>s.id);assert.deepEqual(order,[originalIds[2],originalIds[0],originalIds[1]]);
await page.getByRole('button',{name:'Undo timeline edit',exact:true}).click();await saved();assert.deepEqual((await api('/projects/'+p.id,undefined,'GET')).scenes.map(s=>s.id),originalIds);
await page.getByRole('button',{name:'Redo timeline edit',exact:true}).click();await saved();assert.deepEqual((await api('/projects/'+p.id,undefined,'GET')).scenes.map(s=>s.id),order);
await page.getByRole('separator',{name:'Resize timeline',exact:true}).focus();for(let i=0;i<14;i++)await page.keyboard.press('ArrowDown');
console.log('PASS visible picture cuts, whole-scene lane highlights, actual grouped drag and Undo/Redo');
await page.getByRole('button',{name:'Edit',exact:true}).click();await page.getByRole('button',{name:'Script → Scenes…',exact:true}).click();dlg=page.getByRole('dialog',{name:'Story tools'});
await dlg.getByRole('checkbox',{name:'Prepare imported scenes',exact:true}).check();assert.equal(await dlg.getByLabel('Script image motion',{exact:true}).locator('option').count(),16);
await dlg.getByLabel('Script scene pictures',{exact:true}).selectOption('pool');await dlg.getByRole('group',{name:'Script scene media choices',exact:true}).getByText('image1.png',{exact:true}).locator('input').check();await dlg.getByLabel('Script image motion',{exact:true}).selectOption('rise_left');
await dlg.getByLabel('Script to split',{exact:true}).fill('A scene to review.\n\nأهلا بكم في لندن.');await dlg.getByRole('button',{name:'Preview scenes',exact:true}).click();
await dlg.getByRole('button',{name:'Review script scene 2',exact:true}).click();await dlg.getByRole('button',{name:'Edit this narration',exact:true}).click();assert.equal(await dlg.getByLabel('Preview scene 2 narration',{exact:true}).evaluate(el=>document.activeElement===el),true);
await dlg.getByLabel('Script visual storyboard',{exact:true}).screenshot({path:path.join(qa,'owner-script-storyboard.png')});await dlg.getByRole('button',{name:'Add 2 scenes',exact:true}).click();await dlg.waitFor({state:'detached'});await saved();
await page.getByRole('button',{name:'Edit imported scene 2: Scene 2',exact:true}).click();await page.getByRole('region',{name:'Edit Scene 2',exact:true}).waitFor();
assert.equal(await page.getByRole('region',{name:'Edit Scene 2',exact:true}).getByRole('textbox',{name:'Narration script',exact:true}).inputValue(),'أهلا بكم في لندن.');
await page.screenshot({path:path.join(qa,'owner-added-scene-links.png'),fullPage:true});
let after=(await api('/projects/'+p.id,undefined,'GET')).scenes;assert.equal(after.length,5);assert.deepEqual(after.slice(0,3).map(s=>s.id),order);
await page.getByRole('button',{name:'Undo timeline edit',exact:true}).click();await saved();assert.equal((await api('/projects/'+p.id,undefined,'GET')).scenes.length,3);
await page.getByRole('button',{name:'Redo timeline edit',exact:true}).click();await saved();assert.deepEqual((await api('/projects/'+p.id,undefined,'GET')).scenes.map(s=>s.id),after.map(s=>s.id));
assert.equal(errors.length,0,errors.join('\n'));console.log('PASS visual storyboard, 16 motions, chosen imported scene opens editor, batch Undo/Redo, existing scenes preserved, no JS errors');
}catch(e){if(browser){const page=browser.contexts()[0]?.pages()[0];if(page)await page.screenshot({path:path.join(qa,'owner-failure.png'),fullPage:true}).catch(()=>{});}console.error('Failure artifacts:',data);console.error(logs.slice(-2000));throw e;}finally{if(browser)await browser.close();if(server)server.kill();if(devServer)devServer.kill();}})();
