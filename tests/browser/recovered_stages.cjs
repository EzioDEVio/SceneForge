// Real Chromium, disposable local database, no models or providers.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),os=require('os'),{spawn}=require('child_process'),assert=require('assert/strict');
const root=path.resolve(__dirname,'../..'),data=fs.mkdtempSync(path.join(os.tmpdir(),'sf-recovered-browser-')),base='http://127.0.0.1:8095';let server,browser,devServer,logs='';
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function api(url,body,method='POST'){const r=await fetch(base+'/api'+url,{method,headers:{'content-type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});assert(r.ok,await r.clone().text());return r.status===204?null:r.json();}
async function upload(pid,name){const form=new FormData();form.append('file',new Blob([fs.readFileSync(path.join(root,'examples/fixture_assets',name))]),name);const r=await fetch(base+'/api/assets/upload?project_id='+pid,{method:'POST',body:form});assert(r.ok,await r.clone().text());return r.json();}
(async()=>{try{
 const frontend=process.env.SF_BROWSER_DEV?'http://127.0.0.1:8195':process.env.SF_BROWSER_FRONTEND_URL||base;
 if(process.env.SF_BROWSER_DEV){devServer=spawn(process.execPath,[path.join(root,'frontend/node_modules/vite/bin/vite.js'),'--config','vite.browser-tests.config.ts','--host','127.0.0.1','--port','8195'],{cwd:path.join(root,'frontend'),env:{...process.env,SF_DEV_BACKEND:base}});devServer.stderr.on('data',d=>logs+=d);for(let i=0;i<100;i++){try{if((await fetch(frontend)).ok)break;}catch{}await wait(100);}}

server=spawn('python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8095'],{cwd:path.join(root,'backend'),env:{...process.env,SCENEFORGE_DATA_DIR:data}});server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);
let up=false;for(let i=0;i<150;i++){try{if((await fetch(base+'/api/health')).ok){up=true;break;}}catch{}await wait(100);}assert(up,logs);
let p=await api('/projects',{title:'Recovered stages',aspect:'16:9',fps:25});p=await api('/projects/'+p.id,undefined,'GET');const originalIds=p.scenes.map(s=>s.id),sid=p.scenes[0].id;
for(const s of p.scenes)await api('/scenes/'+s.id,{timing_mode:'fixed',requested_duration_ms:4000,font:{captions_enabled:false}},'PATCH');
for(const name of ['image1.png','image2.png']){const a=await upload(p.id,name);await api('/scenes/'+sid+'/shots',{asset_id:a.id});}
await api('/projects/'+p.id,{aspect:'16:9'},'PATCH');
const times=[520,1000,2000,3000];await api('/projects/'+p.id,{finishing:{timeline:{version:1,tracks:{},audio_tracks:['A3'],markers:[...times.map((t,i)=>({id:'beat-'+i,time_ms:t,duration_ms:0,label:'♪',color:'purple'})),{id:'manual-first',time_ms:1520,duration_ms:0,label:'First cut',color:'amber'},{id:'manual-second',time_ms:2520,duration_ms:0,label:'Second cut',color:'amber'}]}}},'PATCH');
p=await api('/projects/'+p.id,undefined,'GET');const before=p.scenes[0].shots;
browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{}),args:['--no-sandbox','--disable-dev-shm-usage',...(process.env.CHROMIUM_SINGLE_PROCESS?['--single-process','--no-zygote','--in-process-gpu','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']:[])]});
const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(frontend);await page.getByRole('button',{name:/Recovered stages Open project/}).click();await page.getByRole('button',{name:'Skip tour',exact:true}).click();

const qa=process.env.SF_QA_DIR||path.join(data,'qa');fs.mkdirSync(qa,{recursive:true});
const read=()=>api('/scenes/'+sid,undefined,'GET');
async function saved(){await page.locator('.save-status').filter({hasText:'All changes saved'}).waitFor();}
async function apply(){await page.locator('.scene-editor:not([hidden]) .editor-draft-actions').getByRole('button',{name:'Apply changes',exact:true}).click();await saved();}
let original=await read();
await page.getByRole('tab',{name:'Motion',exact:true}).click();
await page.getByRole('button',{name:'Push & pan right',exact:true}).click();
assert.deepEqual((await read()).shots,original.shots,'Draft motion saved too early');
await page.getByRole('tab',{name:'Effects',exact:true}).click();await page.getByRole('button',{name:'Warm',exact:true}).click();
assert.equal((await read()).effect_preset,original.effect_preset,'Draft effect saved too early');
await page.locator('.editor-draft-actions').getByRole('button',{name:'Render draft preview',exact:true}).click();
await page.locator('.editor-draft-companion video').waitFor({timeout:120000});
assert.deepEqual(await read(),original,'Preview replaced saved scene');
await page.screenshot({path:path.join(qa,'recovered-draft-preview.png'),fullPage:true});
await apply();assert.equal((await read()).effect_preset,'warm');assert.equal((await read()).shots[0].motion_json.type,'push_right');
await page.getByRole('button',{name:'Undo timeline edit',exact:true}).click();await saved();assert.equal((await read()).effect_preset,original.effect_preset);assert.equal((await read()).shots[0].motion_json.type,original.shots[0].motion_json.type);
await page.getByRole('button',{name:'Redo timeline edit',exact:true}).click();await saved();assert.equal((await read()).effect_preset,'warm');
console.log('PASS isolated Motion/Effects draft, rendered preview, atomic Apply, Undo/Redo');
await page.getByRole('tab',{name:'Motion',exact:true}).click();await page.getByRole('button',{name:'Pull & pan left',exact:true}).click();await page.locator('.editor-draft-actions').getByRole('button',{name:'Cancel changes',exact:true}).click();assert.equal((await read()).shots[0].motion_json.type,'push_right');
console.log('PASS Cancel preserves saved values');
for(const size of [{width:1280,height:720},{width:1366,height:768}]){await page.setViewportSize(size);for(const tab of ['Media','Motion','Effects','Overlays','Text','Audio']){await page.getByRole('tab',{name:tab,exact:true}).click();const guide=page.getByRole('navigation',{name:'Inspector sections'});await guide.getByRole('list',{name:'Jump to section'}).getByRole('button').first().click();assert(await page.locator('[data-inspector-section]:focus').count());const box=await guide.boundingBox();assert(box.x>=0&&box.x+box.width<=size.width+1);}}
console.log('PASS section navigation, focus and six tabs at two laptop sizes');
for(const theme of ['dark','light','midnight','warm']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await page.getByRole('tab',{name:'Text',exact:true}).click();assert(await page.locator('.text-preview-footer').isVisible());await page.screenshot({path:path.join(qa,'recovered-theme-'+theme+'.png'),fullPage:true});}
console.log('PASS fixed Text preview and four theme captures');
await page.evaluate(()=>document.documentElement.dataset.theme='dark');
await page.getByRole('button',{name:'Maximize timeline',exact:true}).click();await page.getByRole('button',{name:'Compact tracks',exact:true}).click();await page.getByRole('button',{name:'Fit timeline',exact:true}).click();
console.log('PASS actual timeline maximize, compact and fit pointer targets');
await page.reload();await page.getByRole('button',{name:/Recovered stages Open project/}).click();assert.equal((await read()).shots[0].motion_json.type,'push_right');assert.equal(errors.length,0,errors.join('\n'));
console.log('PASS save/reopen and no browser JavaScript errors');
}catch(e){console.error(e);console.error(logs.slice(-1500));process.exitCode=1;}finally{await browser?.close();server?.kill();devServer?.kill();}})();
