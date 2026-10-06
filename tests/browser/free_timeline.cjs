// Real Chromium, disposable local database, no models or providers.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),os=require('os'),{spawn}=require('child_process'),assert=require('assert/strict');
const root=path.resolve(__dirname,'../..'),data=fs.mkdtempSync(path.join(os.tmpdir(),'sf-mouse-browser-')),base='http://127.0.0.1:8098';let server,browser,devServer,logs='';
const qa=process.env.SF_QA_DIR||path.join(data,'qa');
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function api(url,body,method='POST'){const r=await fetch(base+'/api'+url,{method,headers:{'content-type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});assert(r.ok,await r.clone().text());return r.status===204?null:r.json();}
async function upload(pid,name){const form=new FormData();form.append('file',new Blob([fs.readFileSync(path.join(root,'examples/fixture_assets',name))]),name);const r=await fetch(base+'/api/assets/upload?project_id='+pid,{method:'POST',body:form});assert(r.ok,await r.clone().text());return r.json();}
(async()=>{try{
 const frontend=process.env.SF_BROWSER_DEV?'http://127.0.0.1:8198':process.env.SF_BROWSER_FRONTEND_URL||base;
 if(process.env.SF_BROWSER_DEV){devServer=spawn(process.execPath,[path.join(root,'frontend/node_modules/vite/bin/vite.js'),'--config','vite.browser-tests.config.ts','--host','127.0.0.1','--port','8198'],{cwd:path.join(root,'frontend'),env:{...process.env,SF_DEV_BACKEND:base}});devServer.stderr.on('data',d=>logs+=d);for(let i=0;i<100;i++){try{if((await fetch(frontend)).ok)break;}catch{}await wait(100);}}

server=spawn('python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8098'],{cwd:path.join(root,'backend'),env:{...process.env,SCENEFORGE_DATA_DIR:data}});server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);
let up=false;for(let i=0;i<150;i++){try{if((await fetch(base+'/api/health')).ok){up=true;break;}}catch{}await wait(100);}assert(up,logs);
let p=await api('/projects',{title:'Free timeline owner test',aspect:'16:9',fps:25});p=await api('/projects/'+p.id,undefined,'GET');const originalIds=p.scenes.map(s=>s.id),sid=p.scenes[0].id;
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
const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(frontend);await page.getByRole('button',{name:/Free timeline owner test Open project/}).click();await page.getByRole('button',{name:'Skip tour',exact:true}).click();


fs.mkdirSync(qa,{recursive:true});
await page.getByRole('button',{name:'Free timeline · move clips anywhere',exact:true}).click();
await page.getByRole('region',{name:'Free timeline editor'}).count().catch(()=>{});
const read=()=>api('/projects/'+p.id,undefined,'GET');
const ready=()=>page.waitForFunction(()=>!Array.from(document.querySelectorAll('.free-timeline header button')).find(b=>b.textContent==='Scene assembly')?.disabled);
await ready();
const resizeHandle=page.getByRole('separator',{name:'Resize free timeline',exact:true});let dock=page.locator('.free-timeline'),initialHeight=await dock.evaluate(e=>e.getBoundingClientRect().height);let hr=await resizeHandle.boundingBox();await page.mouse.move(hr.x+hr.width/2,hr.y+hr.height/2);await page.mouse.down();await page.mouse.move(hr.x+hr.width/2,hr.y-130,{steps:12});await page.mouse.up();assert((await dock.evaluate(e=>e.getBoundingClientRect().height))>initialHeight+100);
await resizeHandle.focus();await page.keyboard.press('Home');assert.equal(await dock.evaluate(e=>e.getBoundingClientRect().height),240);await page.keyboard.press('End');assert.equal(await dock.evaluate(e=>e.getBoundingClientRect().height),740);await page.getByRole('button',{name:'Minimize free timeline',exact:true}).click();assert.equal(await page.locator('.free-scroll').isVisible(),false);await page.getByRole('button',{name:'Restore minimized free timeline',exact:true}).click();assert(await page.locator('.free-scroll').isVisible());
await page.screenshot({path:path.join(qa,'free-resize-review.png'),fullPage:true});console.log('PASS mouse divider, keyboard bounds and Minimize/Restore without clip changes');
await page.getByRole('button',{name:'Maximize free timeline',exact:true}).click();let before=await read(),clips=before.finishing_json.free_timeline.clips;assert.equal(clips.length,2);assert.equal(before.scenes.length,3);
const first=()=>page.locator('[data-free-key="scene:'+clips[0].id+'"]');await first().scrollIntoViewIfNeeded();let b=await first().boundingBox();
await page.mouse.move(b.x+30,b.y+12);await page.mouse.down();await page.mouse.move(b.x+230,b.y-40,{steps:15});await page.mouse.up();await ready();
let after=await read(),placed=after.finishing_json.free_timeline.clips.find(c=>c.id===clips[0].id);assert(placed.start_ms>2500);assert.equal(placed.track,4);assert.deepEqual(after.scenes.map(s=>s.id),originalIds);assert.deepEqual(after.scenes[0].shots,initialShots);
console.log('PASS mouse drag into empty time and another track without a target scene; source order/media unchanged');
await page.getByRole('button',{name:'Undo',exact:true}).click();await ready();assert.equal((await read()).finishing_json.free_timeline.clips[0].start_ms,0);
await page.getByRole('button',{name:'Redo',exact:true}).click();await ready();assert.equal((await read()).finishing_json.free_timeline.clips[0].start_ms,placed.start_ms);
await page.getByRole('button',{name:'Box select free clips',exact:true}).click();const b1=await first().boundingBox(),b2=await page.locator('[data-free-key="scene:'+clips[1].id+'"] ').boundingBox();
await page.mouse.move(b1.x+3,b1.y+3);await page.mouse.down();await page.mouse.move(b2.x+b2.width-3,b2.y+b2.height-3,{steps:15});await page.mouse.up();assert.equal(await page.locator('.free-clip.selected').count(),2);
b=await first().boundingBox();await page.mouse.move(b.x+20,b.y+10);await page.mouse.down();await page.mouse.move(b.x+90,b.y+10,{steps:15});await page.mouse.up();await ready();after=await read();const shifted=after.finishing_json.free_timeline.clips;assert.equal(shifted[0].start_ms-placed.start_ms,1000);assert.equal(shifted[1].start_ms-clips[1].start_ms,1000);
console.log('PASS box-selected source scenes move together into empty space, Undo/Redo exact');
await page.screenshot({path:path.join(qa,'free-timeline-placement.png'),fullPage:true});
// Highlight just a one-second middle excerpt by mouse, isolate it, move it to another lane.
await first().scrollIntoViewIfNeeded();b=await first().boundingBox();await page.getByRole('button',{name:'Highlight free timeline range',exact:true}).click();await page.mouse.move(b.x+70,b.y+2);await page.mouse.down();await page.mouse.move(b.x+140,b.y+b.height-2,{steps:15});await page.mouse.up();await page.getByRole('button',{name:'Split highlighted range',exact:true}).click();await ready();after=await read();assert.equal(after.finishing_json.free_timeline.clips.length,4);const pieces=after.finishing_json.free_timeline.clips.filter(c=>c.scene_id===sid).sort((a,b)=>a.start_ms-b.start_ms);assert.deepEqual(pieces.map(c=>c.source_in_ms),[0,1000,2000]);assert.deepEqual(pieces.map(c=>c.duration_ms),[1000,1000,2000]);assert.equal(await page.locator('.free-clip.selected').count(),1);
const middle=page.locator('[data-free-key="scene:'+pieces[1].id+'"]');b=await middle.boundingBox();await page.mouse.move(b.x+20,b.y+10);await page.mouse.down();await page.mouse.move(b.x-50,b.y-42,{steps:15});await page.mouse.up();await ready();after=await read();assert.equal(after.finishing_json.free_timeline.clips.find(c=>c.id===pieces[1].id).track,3);assert.equal(after.finishing_json.free_timeline.clips.find(c=>c.id===pieces[1].id).source_in_ms,1000);
console.log('PASS mouse-highlighted middle section splits at both ends and moves up/left without changing source excerpt');
await page.getByRole('button',{name:'Add Text box at playhead',exact:true}).click();await ready();after=await read();assert(after.finishing_json.layer_clips.some(c=>c.kind==='text_box'));
const text=page.locator('.free-layer').first();await text.scrollIntoViewIfNeeded();b=await text.boundingBox();await page.mouse.move(b.x+20,b.y+12);await page.mouse.down();await page.mouse.move(b.x+90,b.y+64,{steps:15});await page.mouse.up();await ready();after=await read();assert.equal(after.finishing_json.layer_clips[0].track,1);assert.equal(after.finishing_json.layer_clips[0].start_ms,1000);
await page.getByRole('button',{name:'Open free preview',exact:true}).click();assert.equal(await page.getByLabel('Free timeline preview',{exact:true}).count(),1);await page.getByRole('button',{name:'Close free preview',exact:true}).click();
// Drop a real audio asset into an empty audio lane, then move it with the mouse.
const audioLane=page.locator('[data-free-row="6"]');await audioLane.scrollIntoViewIfNeeded();const ar=await audioLane.boundingBox();const dragData=await page.evaluateHandle(v=>{const d=new DataTransfer();d.setData('application/x-sceneforge-assets',JSON.stringify([v]));return d;},voice);await audioLane.dispatchEvent('drop',{dataTransfer:dragData,clientX:ar.x+140,clientY:ar.y+10});await ready();after=await read();assert.equal(after.finishing_json.audio_clips.length,1);const sound=page.locator('.free-audio');await sound.scrollIntoViewIfNeeded();b=await sound.boundingBox();await page.mouse.move(b.x+10,b.y+12);await page.mouse.down();await page.mouse.move(b.x+80,b.y+64,{steps:15});await page.mouse.up();await ready();after=await read();assert.equal(after.finishing_json.audio_clips[0].start_ms,3000);assert.equal(after.finishing_json.audio_clips[0].track,'A4');
console.log('PASS real audio drop into empty space and mouse move across independent audio tracks');
const persisted=(await read()).finishing_json;const savedHeight=await page.evaluate(()=>Object.entries(localStorage).find(([k])=>k.startsWith('sceneforge.freeHeight.'))?.[1]);await page.reload();await page.getByRole('button',{name:/Free timeline owner test Open project/}).click();await page.locator('.free-timeline').waitFor();assert.deepEqual((await read()).finishing_json,persisted);assert.equal(String(await dock.evaluate(e=>e.getBoundingClientRect().height)),savedHeight);assert.equal(errors.length,0,errors.join('\n'));

// Repeated playhead cuts must keep selecting the next editable right excerpt.
const sourceBefore=(await read()).scenes;
let target=(await read()).finishing_json.free_timeline.clips.find(c=>c.duration_ms>=2000);
assert(target);let clip=page.locator('[data-free-key="scene:'+target.id+'"]');await clip.scrollIntoViewIfNeeded();await clip.click();
let splitCount=(await read()).finishing_json.free_timeline.clips.length;
for(const offset of [400,800,1200]) {
 await page.getByLabel('Free timeline playhead seconds',{exact:true}).fill(String((target.start_ms+offset)/1000));
 await page.getByRole('button',{name:'Split at playhead',exact:true}).click();
 await page.waitForFunction(n=>document.querySelectorAll('.free-scene').length===n,++splitCount);await ready();
 assert.equal(await page.locator('.free-scene.selected').count(),1);
 const selectedId=(await page.locator('.free-scene.selected').getAttribute('data-free-key')).slice(6);
 assert.equal((await read()).finishing_json.free_timeline.clips.find(c=>c.id===selectedId).source_in_ms,target.source_in_ms+offset);
}

const cutFinishing=(await read()).finishing_json;
await page.getByRole('button',{name:'Undo',exact:true}).click();await ready();
assert.equal((await read()).finishing_json.free_timeline.clips.length,splitCount-1);
await page.getByRole('button',{name:'Redo',exact:true}).click();await ready();
assert.deepEqual((await read()).finishing_json,cutFinishing);
assert.deepEqual((await read()).scenes,sourceBefore);
const editedFinishing=(await read()).finishing_json;
await page.getByRole('button',{name:'Scene assembly',exact:true}).click();await page.locator('.picture-clip').first().waitFor();
assert((await read()).finishing_json.free_timeline.enabled,'Viewing sources must keep free export active');
assert.deepEqual((await read()).finishing_json,editedFinishing);
await page.getByRole('status').filter({hasText:'Original source scenes'}).waitFor();
await page.getByRole('button',{name:'Free timeline · move clips anywhere',exact:true}).click();await page.locator('.free-timeline').waitFor();
assert.deepEqual((await read()).finishing_json,editedFinishing);
console.log('PASS three consecutive playhead cuts select right excerpts; source view preserves edits and active free export');
await page.getByRole('button',{name:'Scene assembly',exact:true}).click();
await page.getByRole('button',{name:'Use Scene assembly for export',exact:true}).click();
await page.waitForFunction(()=>!document.querySelector('button[disabled]')?.textContent?.includes('Use Scene assembly'));
for(let i=0;i<100&&(await read()).finishing_json.free_timeline.enabled;i++)await wait(50);
assert.equal((await read()).finishing_json.free_timeline.enabled,false);
assert.deepEqual((await read()).finishing_json.free_timeline.clips,editedFinishing.free_timeline.clips);
await page.getByRole('button',{name:'Free timeline · move clips anywhere',exact:true}).click();await page.locator('.free-timeline').waitFor();await ready();
assert.deepEqual((await read()).finishing_json.free_timeline,editedFinishing.free_timeline);
console.log('PASS cut Undo/Redo and explicit source-assembly export mode preserve every free excerpt');

await page.screenshot({path:path.join(qa,'free-timeline-range.png'),fullPage:true});await page.getByRole('button',{name:'AI Engines',exact:true}).click();await page.getByRole('button',{name:'AI providers · API keys',exact:true}).click();const providersPanel=page.getByRole('dialog',{name:'AI engines & providers'});await providersPanel.locator('.provider-connection').first().waitFor();assert.equal(await providersPanel.locator('.provider-connection').count(),8);await providersPanel.locator('summary').filter({hasText:'OpenAI · Images'}).click();await providersPanel.getByLabel('OpenAI API key',{exact:true}).waitFor();assert(await providersPanel.getByRole('button',{name:'Save OpenAI provider',exact:true}).isDisabled());await providersPanel.locator('summary').filter({hasText:'ElevenLabs · Voice'}).click();assert.equal(await providersPanel.getByLabel('ElevenLabs API key',{exact:true}).getAttribute('type'),'password');await providersPanel.getByLabel('ElevenLabs API key',{exact:true}).scrollIntoViewIfNeeded();await page.screenshot({path:path.join(qa,'providers-expand-review.png'),fullPage:true});await providersPanel.locator('summary').filter({hasText:'ElevenLabs · Voice'}).click();assert.equal(await providersPanel.getByLabel('ElevenLabs API key',{exact:true}).isVisible(),false);await providersPanel.getByRole('button',{name:'Close',exact:true}).click();assert.equal(errors.length,0,errors.join('\n'));console.log('PASS AI provider menu, eight inline setup forms, accessible expansion and empty-key save guard; no paid calls');console.log('PASS independent text moves freely, preview opens/closes, project survives reload with no JS errors');
}catch(e){if(browser){const page=browser.contexts()[0]?.pages()[0];if(page)await page.screenshot({path:path.join(qa,'free-failure.png'),fullPage:true}).catch(()=>{});}console.error(e);console.error(logs.slice(-2000));throw e;}finally{if(browser)await browser.close();if(server)server.kill();if(devServer)devServer.kill();}})();
