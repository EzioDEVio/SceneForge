// Real Chromium, disposable local database, no models or providers.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),os=require('os'),{spawn}=require('child_process'),assert=require('assert/strict');
const root=path.resolve(__dirname,'../..'),data=fs.mkdtempSync(path.join(os.tmpdir(),'sf-mouse-browser-')),base='http://127.0.0.1:8097';let server,browser,devServer,logs='';
const qa=process.env.SF_QA_DIR||path.join(data,'qa');
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function api(url,body,method='POST'){const r=await fetch(base+'/api'+url,{method,headers:{'content-type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});assert(r.ok,await r.clone().text());return r.status===204?null:r.json();}
async function upload(pid,name){const form=new FormData();form.append('file',new Blob([fs.readFileSync(path.join(root,'examples/fixture_assets',name))]),name);const r=await fetch(base+'/api/assets/upload?project_id='+pid,{method:'POST',body:form});assert(r.ok,await r.clone().text());return r.json();}
(async()=>{try{
 const frontend=process.env.SF_BROWSER_DEV?'http://127.0.0.1:8197':process.env.SF_BROWSER_FRONTEND_URL||base;
 if(process.env.SF_BROWSER_DEV){devServer=spawn(process.execPath,[path.join(root,'frontend/node_modules/vite/bin/vite.js'),'--config','vite.browser-tests.config.ts','--host','127.0.0.1','--port','8197'],{cwd:path.join(root,'frontend'),env:{...process.env,SF_DEV_BACKEND:base}});devServer.stderr.on('data',d=>logs+=d);for(let i=0;i<100;i++){try{if((await fetch(frontend)).ok)break;}catch{}await wait(100);}}

server=spawn('python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8097'],{cwd:path.join(root,'backend'),env:{...process.env,SCENEFORGE_DATA_DIR:data}});server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);
let up=false;for(let i=0;i<150;i++){try{if((await fetch(base+'/api/health')).ok){up=true;break;}}catch{}await wait(100);}assert(up,logs);
let p=await api('/projects',{title:'Mouse selection',aspect:'16:9',fps:25});p=await api('/projects/'+p.id,undefined,'GET');const originalIds=p.scenes.map(s=>s.id),sid=p.scenes[0].id;
for(const s of p.scenes)await api('/scenes/'+s.id,{timing_mode:'fixed',requested_duration_ms:4000,font:{captions_enabled:false}},'PATCH');
for(const name of ['image1.png','image2.png']){const a=await upload(p.id,name);await api('/scenes/'+sid+'/shots',{asset_id:a.id});}
const video=await upload(p.id,'clip1.mp4');await api('/scenes/'+originalIds[1]+'/shots',{asset_id:video.id});
// A real uploaded WAV take proves linked narration survives the move without a provider call.
const wav=Buffer.alloc(44+8000*2);wav.write('RIFF');wav.writeUInt32LE(wav.length-8,4);wav.write('WAVEfmt ',8);wav.writeUInt32LE(16,16);wav.writeUInt16LE(1,20);wav.writeUInt16LE(1,22);wav.writeUInt32LE(8000,24);wav.writeUInt32LE(16000,28);wav.writeUInt16LE(2,32);wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(wav.length-44,40);for(let i=0;i<8000;i++)wav.writeInt16LE(Math.round(2000*Math.sin(i*2*Math.PI*440/8000)),44+i*2);
const voiceForm=new FormData();voiceForm.append('file',new Blob([wav],{type:'audio/wav'}),'test-voice.wav');const vr=await fetch(base+'/api/assets/upload?project_id='+p.id,{method:'POST',body:voiceForm});assert(vr.ok);const voice=await vr.json();await api('/scenes/'+sid+'/voice-takes/from-asset',{asset_id:voice.id});
for(const id of originalIds.slice(0,2))await api('/scenes/'+id,{subtitle_text:'Linked caption '+id.slice(0,4),font:{captions_enabled:true}},'PATCH');
await api('/projects/'+p.id,{aspect:'16:9'},'PATCH');
const times=[520,1000,2000,3000];await api('/projects/'+p.id,{finishing:{timeline:{version:1,tracks:{},audio_tracks:['A3'],markers:[...times.map((t,i)=>({id:'beat-'+i,time_ms:t,duration_ms:0,label:'♪',color:'purple'})),{id:'manual-first',time_ms:1520,duration_ms:0,label:'First cut',color:'amber'},{id:'manual-second',time_ms:2520,duration_ms:0,label:'Second cut',color:'amber'}]}}},'PATCH');
p=await api('/projects/'+p.id,undefined,'GET');const initialShots=p.scenes[0].shots;
browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{}),args:['--no-sandbox','--disable-dev-shm-usage',...(process.env.CHROMIUM_SINGLE_PROCESS?['--single-process','--no-zygote','--in-process-gpu','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']:[])]});
const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(frontend);await page.getByRole('button',{name:/Mouse selection Open project/}).click();await page.getByRole('button',{name:'Skip tour',exact:true}).click();

fs.mkdirSync(qa,{recursive:true});


const saved=()=>page.locator('.save-status').filter({hasText:'All changes saved'}).waitFor();
const read=()=>api('/projects/'+p.id,undefined,'GET');
await page.getByRole('button',{name:'Maximize timeline',exact:true}).click();
await page.getByRole('button',{name:'Compact tracks',exact:true}).click();
const v=()=>page.getByRole('button',{name:'Storyboard scene 1',exact:true});
const second=()=>page.getByRole('button',{name:'Storyboard scene 2',exact:true});
const lane=()=>page.getByLabel('Scene track',{exact:true});
let b1=await v().boundingBox(),b2=await second().boundingBox(),rect=await lane().boundingBox();
assert(b1.y>=rect.y&&b1.y+b1.height<=rect.y+rect.height,'Compact picture stays inside V1');
// Default select tool: start in the narrow empty strip beneath the pictures, then sweep across two scenes.
await page.mouse.move(b1.x+4,rect.y+rect.height-2);await page.mouse.down();await page.mouse.move(b2.x+b2.width-8,b1.y-8,{steps:20});
assert.equal(await page.locator('.scene-selection-box').count(),1);assert.equal(await page.locator('.picture-clip.multi').count(),2);
await page.screenshot({path:path.join(qa,'mouse-box-drag.png'),fullPage:true});await page.mouse.up();
assert.equal(await page.locator('.picture-clip.multi').count(),2);assert.equal(await page.locator('.narration-clip.scene-linked-selected').count(),2);assert.equal(await page.locator('.title-clip.scene-linked-selected').count(),2);assert.equal(await page.locator('.source-audio-clip-shell.scene-linked-selected').count(),1);
console.log('PASS mouse-only background box selects two scenes and linked picture/text/narration/video sound');
const before=await read();await page.screenshot({path:path.join(qa,'mouse-box-selected.png'),fullPage:true});
const target=page.getByRole('button',{name:'Storyboard scene 3',exact:true}),tb=await target.boundingBox();await v().dragTo(target,{targetPosition:{x:tb.width-4,y:15}});await saved();
let after=await read();assert.deepEqual(after.scenes.map(s=>s.id),[originalIds[2],originalIds[0],originalIds[1]]);
assert(before.scenes.find(s=>s.id===sid).voice_takes.some(t=>t.accepted),'Real accepted narration fixture');
for(const id of originalIds){const a=after.scenes.find(s=>s.id===id),b=before.scenes.find(s=>s.id===id);assert.deepEqual(a.shots,b.shots);assert.deepEqual(a.font_json,b.font_json);assert.deepEqual(a.voice_takes,b.voice_takes);}
await page.getByRole('button',{name:'Undo timeline edit',exact:true}).click();await saved();assert.deepEqual((await read()).scenes.map(s=>s.id),originalIds);
await page.getByRole('button',{name:'Redo timeline edit',exact:true}).click();await saved();assert.deepEqual((await read()).scenes.map(s=>s.id),after.scenes.map(s=>s.id));
console.log('PASS mouse-selected group moves with media/captions/audio intact and Undo/Redo');
// Explicit one-shot box mode may start on a clip, then returns to ordinary drag mode.
await page.getByRole('button',{name:'Box select scenes',exact:true}).click();let first=await v().boundingBox(),last=await page.getByRole('button',{name:'Storyboard scene 3',exact:true}).boundingBox();
await page.mouse.move(first.x+8,first.y+10);await page.mouse.down();await page.mouse.move(last.x+last.width-8,last.y+last.height-8,{steps:15});await page.mouse.up();
assert.equal(await page.locator('.picture-clip.multi').count(),3);assert.equal(await page.getByRole('button',{name:'Box select scenes',exact:true}).getAttribute('aria-pressed'),'false');
await page.getByRole('button',{name:'Box select scenes',exact:true}).click();await page.mouse.move(first.x+8,first.y+10);await page.mouse.down();await page.mouse.move(first.x+100,first.y+25);await page.keyboard.press('Escape');await page.mouse.up();assert.equal(await page.locator('.scene-selection-box').count(),0);assert.equal(await page.locator('.picture-clip.multi').count(),3);
console.log('PASS Box select starts over a clip, returns to drag mode, and Escape preserves previous selection');
await page.getByRole('button',{name:'Compact tracks',exact:true}).click();
rect=await lane().boundingBox();b1=await v().boundingBox();assert(b1.y>=rect.y&&b1.y+b1.height<=rect.y+rect.height,'Normal picture stays inside V1');
await v().click();await page.getByRole('button',{name:'Lock V1 picture track',exact:true}).click();await saved();after=await read();await v().dragTo(target,{targetPosition:{x:tb.width-4,y:15}});await saved();assert.deepEqual((await read()).scenes.map(s=>s.id),after.scenes.map(s=>s.id));
await page.getByRole('button',{name:'Unlock V1 picture track',exact:true}).click();await saved();
// Scroll/zoom, then select the two rightmost scenes by drawing backwards without modifier keys.
await page.getByLabel('Timeline zoom',{exact:true}).evaluate(el=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,'100');el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));});await page.locator('.sequence-scroll').evaluate(el=>el.scrollLeft=250);await wait(150);
await page.getByRole('button',{name:'Box select scenes',exact:true}).click();const one=await second().boundingBox(),two=await page.getByRole('button',{name:'Storyboard scene 3',exact:true}).boundingBox();
await page.mouse.move(two.x+two.width-8,two.y+two.height-8);await page.mouse.down();await page.mouse.move(one.x+8,one.y+8,{steps:20});await page.mouse.up();assert.equal(await page.locator('.picture-clip.multi').count(),2);
assert.equal(errors.length,0,errors.join('\n'));console.log('PASS picture lock, zoomed/scrolled backwards selection and no JavaScript errors');
}catch(e){if(browser){const page=browser.contexts()[0]?.pages()[0];if(page)await page.screenshot({path:path.join(qa,'mouse-failure.png'),fullPage:true}).catch(()=>{});}console.error('Failure artifacts:',data);console.error(logs.slice(-2000));throw e;}finally{if(browser)await browser.close();if(server)server.kill();if(devServer)devServer.kill();}})();
