// Real Chromium + FastAPI acceptance test. Uses an isolated temporary database.
// npm install playwright (test tooling only); npx playwright install chromium
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),{spawn}=require('node:child_process');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..'),data=fs.mkdtempSync(path.join(os.tmpdir(),'sceneforge-qa-'));
const output=process.env.SCENEFORGE_SCREENSHOTS||path.join(data,'screenshots');fs.mkdirSync(output,{recursive:true});
const base='http://127.0.0.1:8019';
let logs='',browser,server,project;
const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function api(url,body,method='POST'){
 const r=await fetch(base+'/api'+url,{method,headers:body instanceof FormData?{}:{'content-type':'application/json'},body:body===undefined?undefined:body instanceof FormData?body:JSON.stringify(body)});
 const result=await r.json();assert.ok(r.ok,JSON.stringify(result));return result;
}
async function shot(scene,file){const form=new FormData();form.append('file',new Blob([fs.readFileSync(file)],{type:file.endsWith('.mp4')?'video/mp4':'image/png'}),path.basename(file));const asset=await api('/assets/upload?project_id='+project.id,form);await api('/scenes/'+scene.id+'/shots',{asset_id:asset.id,motion:{type:'static'},fit:'contain'});}
async function layout(page,name){
 const boxes=await page.evaluate(()=>{
   const box=s=>{const r=document.querySelector(s).getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,b:r.bottom,r:r.right};};
   return {pageH:document.documentElement.scrollHeight,innerH:innerHeight,pageW:document.documentElement.scrollWidth,innerW:innerWidth,dock:box('.sequence-dock'),viewer:box('.scene-editor:not([hidden]) .preview-card'),canvas:box('.scene-editor:not([hidden]) .preview-canvas'),tabs:box('.scene-editor:not([hidden]) .inspector-tabs'),inspector:box('.scene-editor:not([hidden]) .inspector'),ruler:box('.sequence-ruler')};
 });
 assert.ok(boxes.pageH<=boxes.innerH+1,`${name}: page overflow ${JSON.stringify(boxes)}`);
 assert.ok(boxes.pageW<=boxes.innerW+1,`${name}: horizontal overflow`);
 assert.ok(boxes.dock.b<=boxes.innerH+1&&boxes.dock.h>=249,`${name}: dock clipped`);
 assert.ok(boxes.viewer.b<=boxes.dock.y+1,`${name}: viewer under timeline`);
 assert.ok(boxes.tabs.y>=boxes.inspector.y&&boxes.tabs.b<=boxes.dock.y,`${name}: inspector tabs hidden`);
 assert.ok(Math.min(boxes.canvas.w,boxes.canvas.h)>60&&Math.max(boxes.canvas.w,boxes.canvas.h)>100,`${name}: preview collapsed ${JSON.stringify(boxes.canvas)}`);
 const aligned=await page.evaluate(()=>['track-video-label','track-audio-label','track-text-label'].map((n,i)=>Math.abs(document.querySelector('.'+n).getBoundingClientRect().y-document.querySelector('.'+['picture-track','narration-track','titles-track'][i]).getBoundingClientRect().y)<1));assert.ok(aligned.every(Boolean),name+': track alignment');
 await page.screenshot({path:path.join(output,name+'.png')});console.log('PASS layout '+name);
}
(async()=>{
 try{
  server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8019'],{cwd:path.join(root,'backend'),env:{...process.env,SCENEFORGE_DATA_DIR:data}});
  server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);
  let ready=false;for(let i=0;i<100;i++){try{const r=await fetch(base+'/api/health');if(r.ok){ready=true;break;}}catch{}await delay(100);}assert.ok(ready,logs);
  project=await api('/projects',{title:'Workspace review · Empty',aspect:'16:9',language:'ar'});
  project=await api('/projects/'+project.id,undefined,'GET');
  browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH,args:['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}: {})});
  const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('dialog',dialog=>dialog.accept(dialog.type()==='prompt'?dialog.defaultValue():undefined));
  await page.goto(base);await page.getByRole('button',{name:/Workspace review · Empty Open project/}).click();
  await page.getByRole('button',{name:'Storyboard scene 1',exact:true}).waitFor();
  assert.equal(await page.locator('.picture-clip.placeholder').count(),3);
  await layout(page,'empty-1440');
  await page.setViewportSize({width:1366,height:768});await layout(page,'empty-1366');
  await page.setViewportSize({width:1920,height:1080});await layout(page,'empty-1920');
  await page.getByRole('tab',{name:'Audio',exact:true}).click();
  await page.locator('.scene-editor:not([hidden]) .inspector-body').evaluate(e=>e.scrollTop=e.scrollHeight);
  await layout(page,'audio-scrolled-1920');
  const original=(await page.locator('.sequence-dock').boundingBox()).height;
  await page.getByRole('separator',{name:'Resize timeline'}).focus();await page.keyboard.press('ArrowUp');
  assert.equal((await page.locator('.sequence-dock').boundingBox()).height,original+20);
  await page.keyboard.press('ArrowDown');console.log('PASS keyboard resize');
  // File import must populate a pool without changing the authored timeline.
  await page.getByRole('button',{name:'Media Pool',exact:true}).click();
  const poolChooser=page.waitForEvent('filechooser');await page.getByRole('button',{name:'Import files',exact:true}).click();await (await poolChooser).setFiles(path.join(root,'examples/fixture_assets/image1.png'));
  await page.getByRole('checkbox',{name:'Select media image1.png',exact:true}).waitFor();
  assert.equal((await api('/projects/'+project.id,undefined,'GET')).scenes.length,3,'import does not create scenes');
  await page.getByRole('button',{name:'Preview image1.png',exact:true}).click();await page.getByRole('dialog',{name:'Media preview'}).waitFor();await page.getByRole('button',{name:'Close media preview'}).click();
  await page.getByRole('checkbox',{name:'Select media image1.png',exact:true}).check();await page.getByRole('button',{name:'Add to timeline',exact:true}).click();await page.waitForFunction(()=>document.querySelectorAll('.picture-clip').length===4);
  await page.getByRole('button',{name:'Delete selected scene',exact:true}).click();await page.waitForFunction(()=>document.querySelectorAll('.picture-clip').length===3);
  assert.equal((await api('/assets?project_id='+project.id,undefined,'GET')).length,1,'deletion retains pool asset');
  await page.screenshot({path:path.join(output,'media-pool-1920.png')});
  console.log('PASS pool import, preview, explicit timeline insertion and media retention');
  // Populate using actual API uploads, including a video source and an empty placeholder.
  for(let i=0;i<3;i++){await shot(project.scenes[i],path.join(root,'examples/fixture_assets',i===2?'clip1.mp4':`image${i+1}.png`));await api('/scenes/'+project.scenes[i].id,{title:['01 · Bell Labs','02 · Silicon Valley','03 · Archive'][i],timing_mode:'fixed',requested_duration_ms:[6000,5000,6000][i],subtitle_text:i===1?'بداية عصر جديد':'',transition_in:{type:i===1?'dissolve':i===2?'wipe_left':'cut',duration_ms:i?500:0}},'PATCH');}
  await api('/projects/'+project.id+'/scenes',{title:'04 · Next chapter'});
  await api('/projects/'+project.id,{title:'Origins of computing · Review'},'PATCH');
  await page.reload();await page.getByRole('button',{name:/Origins of computing · Review Open project/}).click();
  await page.setViewportSize({width:1440,height:900});
  await page.getByRole('button',{name:'Storyboard scene 2',exact:true}).click();
  await page.getByRole('button',{name:'Transitions',exact:true}).click();
  await layout(page,'populated-1440');
  await page.getByRole('button',{name:'Go to timeline start'}).click();
  await page.getByRole('button',{name:'Next frame',exact:true}).click();assert.ok(Number(await page.getByRole('slider',{name:'Timeline playhead'}).getAttribute('aria-valuenow'))>0);
  await page.getByRole('button',{name:'Previous frame',exact:true}).click();assert.equal(Number(await page.getByRole('slider',{name:'Timeline playhead'}).getAttribute('aria-valuenow')),0);console.log('PASS editing frame-step arrows');
  await page.getByRole('button',{name:'Storyboard scene 2',exact:true}).click();
  // Transition palette must write to the backend, not just change CSS.
  await page.getByRole('button',{name:'Fade through black',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('select[aria-label="Incoming transition"]')?.value==='fade_through_black');
  const stored=await api('/scenes/'+project.scenes[1].id,undefined,'GET');assert.equal(stored.transition_in_json.type,'fade_through_black');
  console.log('PASS transition palette persists');
  const resizeBox=await page.getByRole('separator',{name:'Resize timeline'}).boundingBox();await page.mouse.move(resizeBox.x+resizeBox.width/2,resizeBox.y+3);await page.mouse.down();await page.mouse.move(resizeBox.x+resizeBox.width/2,resizeBox.y-37);await page.mouse.up();
  assert.ok((await page.locator('.sequence-dock').boundingBox()).height>=365);console.log('PASS pointer resize');
  await page.getByRole('button',{name:'Fit timeline',exact:true}).click();
  const ruler=await page.getByRole('slider',{name:'Timeline playhead'}).boundingBox();await page.mouse.click(ruler.x+340,ruler.y+12);assert.ok(Number(await page.getByRole('slider',{name:'Timeline playhead'}).getAttribute('aria-valuenow'))>0);console.log('PASS ruler seek');
  await page.getByRole('button',{name:'Storyboard scene 1',exact:true}).dragTo(page.getByRole('button',{name:'Storyboard scene 3',exact:true}));
  for(let i=0;i<30;i++){const p=await api('/projects/'+project.id,undefined,'GET');if(p.scenes[2].id===project.scenes[0].id)break;await delay(100);}
  const reordered=await api('/projects/'+project.id,undefined,'GET');assert.equal(reordered.scenes[2].id,project.scenes[0].id);console.log('PASS drag reorder persists');
  await page.getByRole('button',{name:'Storyboard scene 2',exact:true}).click();await page.getByRole('button',{name:'Effects',exact:true}).click();await page.getByRole('button',{name:'Noir',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.library-presets button[aria-pressed="true"]')?.textContent==='Noir');console.log('PASS effect library apply');
  await page.setViewportSize({width:1366,height:768});await layout(page,'populated-1366');
  // Test portrait media canvas within the same fixed workspace.
  await page.getByRole('combobox',{name:'Project aspect ratio'}).selectOption('9:16');await page.waitForFunction(()=>document.querySelector('.scene-editor:not([hidden]) .preview-canvas')?.getAttribute('style')?.includes('9 / 16'));
  await layout(page,'portrait-1366');
  await page.getByRole('combobox',{name:'Project aspect ratio'}).selectOption('16:9');
  await page.setViewportSize({width:1920,height:1080});await layout(page,'populated-1920');
  // Workspace 2.1 editing operations persist and affect real rendering.
  await page.getByRole('button',{name:'Storyboard scene 3',exact:true}).click();
  await page.getByRole('button',{name:'Fit timeline',exact:true}).click();
  const splitRuler=await page.getByRole('slider',{name:'Timeline playhead'}).boundingBox();
  const zoom=Number(await page.getByRole('slider',{name:'Timeline zoom'}).inputValue());
  await page.mouse.click(splitRuler.x+12*zoom,splitRuler.y+12);
  await page.getByRole('button',{name:'Split at playhead',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.picture-clip').length===5);
  const splitProject=await api('/projects/'+project.id,undefined,'GET');assert.equal(splitProject.scenes.length,5);assert.equal(splitProject.scenes[2].requested_duration_ms+splitProject.scenes[3].requested_duration_ms,6000);console.log('PASS split preserves total visual duration');
  await page.getByRole('button',{name:'Storyboard scene 2',exact:true}).click();
  const durationInput=page.getByRole('spinbutton',{name:'Transition seconds'});await durationInput.fill('1.2');await durationInput.press('Enter');
  await page.waitForFunction(()=>document.querySelector('input[aria-label="Transition seconds"]')?.value==='1.2');
  await page.getByRole('button',{name:'Remove transition',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('select[aria-label="Incoming transition"]')?.value==='cut');
  await page.getByRole('button',{name:'Undo timeline edit',exact:true}).click();await page.waitForFunction(()=>document.querySelector('select[aria-label="Incoming transition"]')?.value==='wipe_left');
  assert.equal(await durationInput.inputValue(),'1.2');
  await page.getByRole('button',{name:'Redo timeline edit',exact:true}).click();await page.waitForFunction(()=>document.querySelector('select[aria-label="Incoming transition"]')?.value==='cut');
  await page.getByRole('button',{name:'Undo timeline edit',exact:true}).click();console.log('PASS duration, removal, undo and redo');
  await page.getByRole('button',{name:'Storyboard scene 3',exact:true}).click();await page.getByRole('tab',{name:'Motion',exact:true}).click();
  await page.getByRole('spinbutton',{name:'Crop x percent'}).fill('10');await page.getByRole('spinbutton',{name:'Crop width percent'}).fill('80');await page.getByRole('button',{name:'Apply crop',exact:true}).click();
  await page.locator('.scene-editor:not([hidden]) svg.canvas-media').waitFor();
  const cropped=await api('/scenes/'+splitProject.scenes[2].id,undefined,'GET');assert.equal(cropped.shots[0].crop_json.width,.8);console.log('PASS source crop persists and previews');
  const wav=Buffer.alloc(44+48000*2);wav.write('RIFF');wav.writeUInt32LE(wav.length-8,4);wav.write('WAVEfmt ',8);wav.writeUInt32LE(16,16);wav.writeUInt16LE(1,20);wav.writeUInt16LE(1,22);wav.writeUInt32LE(48000,24);wav.writeUInt32LE(96000,28);wav.writeUInt16LE(2,32);wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(wav.length-44,40);
  for(let i=0;i<4800;i++)wav.writeInt16LE(Math.round(12000*Math.sin(i*.3)*Math.exp(-i/500)),44+i*2);
  const chooser=page.waitForEvent('filechooser');await page.getByRole('button',{name:'Import timeline audio',exact:true}).click();await (await chooser).setFiles({name:'test-audio.wav',mimeType:'audio/wav',buffer:wav});
  await page.locator('.narration-clip.has-take').waitFor();console.log('PASS direct timeline audio import');
  await page.screenshot({path:path.join(output,'editing-tools-1920.png')});
  // Square export with Arabic typewriter captions + uploaded keystroke source.
  const audioScene=await api('/scenes/'+splitProject.scenes[2].id,undefined,'GET');
  const soundId=audioScene.voice_takes.find(t=>t.accepted).audio_asset.id;
  await api('/scenes/'+splitProject.scenes[0].id,{font:{captions_enabled:true,typewriter:true,typewriter_sound:true,typewriter_sound_asset_id:soundId}},'PATCH');
  const badSplit=await fetch(base+'/api/scenes/'+splitProject.scenes[0].id+'/split',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({at_ms:1000})});assert.equal(badSplit.status,400,'reject complex split');
  await page.getByRole('combobox',{name:'Project aspect ratio'}).selectOption('1:1');
  // Real export, including transitions, then seek the resulting MP4 in the viewer.

  await page.getByRole('button',{name:'Export video',exact:true}).click();
  await page.getByRole('button',{name:'Preview last export',exact:true}).waitFor({state:'visible'});
  await page.waitForFunction(()=>!document.querySelector('.movie-toggle')?.disabled||!!document.querySelector('.studio-shell > [role=alert]'),{},{timeout:180000});
  assert.equal(await page.locator('.studio-shell > [role=alert]').count(),0,await page.locator('.studio-shell > [role=alert]').allTextContents());
  await page.getByRole('button',{name:'Preview last export',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.program-monitor video')?.readyState>=2,{},{timeout:30000});
  await page.locator('.program-monitor video').evaluate(v=>v.pause());
  const duration=await page.locator('.program-monitor video').evaluate(v=>v.duration);assert.ok(duration>10&&duration<20,'rendered duration');
  const exportRuler=await page.getByRole('slider',{name:'Timeline playhead'}).boundingBox();await page.mouse.click(exportRuler.x+200,exportRuler.y+12);
  const time=await page.locator('.program-monitor video').evaluate(v=>v.currentTime);assert.ok(time>0,'export seeks');
  const playhead=Number(await page.getByRole('slider',{name:'Timeline playhead'}).getAttribute('aria-valuenow'));assert.ok(Math.abs(playhead-time*1000)<100,'export playhead sync');
  await page.getByRole('button',{name:'Next frame',exact:true}).click();
  assert.ok((await page.locator('.program-monitor video').evaluate(v=>v.currentTime))>time,'frame advance');
  await page.screenshot({path:path.join(output,'export-preview-1920.png')});console.log('PASS real MP4 export, viewer seek and frame advance');
  await page.getByRole('button',{name:'Close movie preview'}).click();
  await page.getByRole('button',{name:'Close export result',exact:true}).click();assert.equal(await page.getByRole('region',{name:'Export result'}).count(),0);console.log('PASS dismiss export result');
  await page.getByRole('button',{name:'Add part',exact:true}).click();await page.waitForFunction(()=>document.querySelectorAll('.picture-clip').length===6);assert.ok((await page.locator('.sequence-status').innerText()).includes('OUTDATED'));console.log('PASS added scene visible and previous export marked outdated');
  await page.getByRole('button',{name:'Provider settings',exact:true}).click();
  await page.screenshot({path:path.join(output,'settings-1920.png')});
  assert.deepEqual(errors,[]);console.log('PASS no browser exceptions');
  console.log('Screenshots: '+output);
 }catch(e){console.error(e);console.error(logs.slice(-3500));process.exitCode=1;}
 finally{if(browser)await browser.close();if(server)server.kill();}
})();
