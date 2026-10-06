// Real Chromium, disposable local database, no models or providers.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),os=require('os'),{spawn}=require('child_process'),assert=require('assert/strict');
const root=path.resolve(__dirname,'../..'),data=fs.mkdtempSync(path.join(os.tmpdir(),'sf-recovered-browser-')),base='http://127.0.0.1:8107';let server,browser,devServer,logs='';
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function api(url,body,method='POST'){const r=await fetch(base+'/api'+url,{method,headers:{'content-type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});assert(r.ok,await r.clone().text());return r.status===204?null:r.json();}
async function upload(pid,name){const form=new FormData();form.append('file',new Blob([fs.readFileSync(path.join(root,'examples/fixture_assets',name))]),name);const r=await fetch(base+'/api/assets/upload?project_id='+pid,{method:'POST',body:form});assert(r.ok,await r.clone().text());return r.json();}
(async()=>{try{
 const frontend=process.env.SF_BROWSER_DEV?'http://127.0.0.1:8207':process.env.SF_BROWSER_FRONTEND_URL||base;
 if(process.env.SF_BROWSER_DEV){devServer=spawn(process.execPath,[path.join(root,'frontend/node_modules/vite/bin/vite.js'),'--config','vite.browser-tests.config.ts','--host','127.0.0.1','--port','8207'],{cwd:path.join(root,'frontend'),env:{...process.env,SF_DEV_BACKEND:base}});devServer.stderr.on('data',d=>logs+=d);for(let i=0;i<100;i++){try{if((await fetch(frontend)).ok)break;}catch{}await wait(100);}}

server=spawn('python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8107'],{cwd:path.join(root,'backend'),env:{...process.env,SCENEFORGE_DATA_DIR:data}});server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);
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
const free=page.getByRole('button',{name:'Free timeline · move clips anywhere',exact:true});
const render=page.getByRole('button',{name:'Render full video',exact:true});
const scene=()=>api('/scenes/'+sid,undefined,'GET');
const original=await scene();
await page.getByRole('tab',{name:'Motion',exact:true}).click();
await page.getByRole('button',{name:'Push & pan right',exact:true}).click();
await page.getByRole('tab',{name:'Media',exact:true}).click();
assert.equal(await free.isDisabled(),false,'A draft must not silently disable timeline entry');
assert.match(await page.locator('.save-status').innerText(),/Draft changes/);
await free.click();
await page.getByRole('alert').filter({hasText:'Apply or Cancel the Motion/Effects'}).waitFor();
assert.deepEqual((await scene()).shots,original.shots,'Blocked timeline switch committed a draft');
assert(await page.getByRole('tab',{name:'Motion',exact:true}).getAttribute('aria-selected')==='true');
await page.screenshot({path:path.join(qa,'draft-action-guidance.png'),fullPage:true});
await page.getByRole('tab',{name:'Media',exact:true}).click();
await render.click();
await page.getByRole('alert').filter({hasText:'Apply or Cancel the Motion/Effects'}).waitFor();
await page.locator('.scene-editor:not([hidden]) .editor-draft-actions').getByRole('button',{name:'Cancel changes',exact:true}).click();
console.log('PASS reproduced draft lock is actionable; timeline and export direct to Apply/Cancel; Cancel preserves source');
// Edit narration and immediately switch timelines: the queued save must flush.
const narration=page.locator('.scene-editor:not([hidden]) textarea').first();
await narration.fill('Stability test narration');
await free.click();await page.locator('.free-timeline').waitFor();
assert.equal((await scene()).spoken_text,'Stability test narration');
console.log('PASS pending narration saves before enabling free timeline');
// Repeat source/free switching without losing cuts or leaving dirty state behind.
for(let i=0;i<12;i++){
 await page.getByRole('button',{name:'Scene assembly',exact:true}).click();
 await free.click();await page.locator('.free-timeline').waitFor();
 assert((await api('/projects/'+p.id,undefined,'GET')).finishing_json.free_timeline.enabled);
}
console.log('PASS 12 repeated source/free view round trips');
// Full export from the UI must produce a real job, completed media and no error.
let exports=[];page.on('response',async r=>{if(new URL(r.url()).pathname.endsWith('/export')&&r.request().method()==='POST'&&r.ok())exports.push(await r.json());});
await render.click();
for(let i=0;i<200&&!exports.length;i++)await wait(100);
assert.equal(exports.length,1,'Full-video button failed to submit exactly one export');
let job;for(let i=0;i<600;i++){job=await api('/jobs/'+exports[0].job_id,undefined,'GET');if(['succeeded','failed','cancelled'].includes(job.status))break;await wait(200);}
assert.equal(job.status,'succeeded',JSON.stringify(job));
const media=await fetch(base+'/api/assets/'+job.artifact_asset_id+'/stream');assert(media.ok);assert((await media.arrayBuffer()).byteLength>1000);
assert.equal(errors.length,0,errors.join('\n'));
console.log('PASS full-video UI action creates and completes an actual export; media is readable; zero JS errors');
}catch(e){console.error(e);console.error(logs.slice(-1500));process.exitCode=1;}finally{await browser?.close();server?.kill();devServer?.kill();}})();
