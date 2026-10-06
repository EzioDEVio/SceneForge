// Real editor gestures against a disposable local backend. No provider calls.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),os=require('os'),{spawn}=require('child_process'),assert=require('assert/strict');
const root=path.resolve(__dirname,'../..'),data=fs.mkdtempSync(path.join(os.tmpdir(),'sf-layers-')),base='http://127.0.0.1:8094';
let server,browser,devServer,logs='';const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function api(url,body,method='POST'){const r=await fetch(base+'/api'+url,{method,headers:{'content-type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});assert(r.ok,await r.clone().text());return r.json();}
(async()=>{try{
 const frontend=process.env.SF_BROWSER_DEV?'http://127.0.0.1:8194':process.env.SF_BROWSER_FRONTEND_URL||base;
 if(process.env.SF_BROWSER_DEV){devServer=spawn(process.execPath,[path.join(root,'frontend/node_modules/vite/bin/vite.js'),'--config','vite.browser-tests.config.ts','--host','127.0.0.1','--port','8194'],{cwd:path.join(root,'frontend'),env:{...process.env,SF_DEV_BACKEND:base}});devServer.stderr.on('data',d=>logs+=d);for(let i=0;i<100;i++){try{if((await fetch(frontend)).ok)break;}catch{}await wait(100);}}

 server=spawn('python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8094'],{cwd:path.join(root,'backend'),env:{...process.env,SCENEFORGE_DATA_DIR:data}});server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);
 for(let i=0;i<150;i++){try{if((await fetch(base+'/api/health')).ok)break;}catch{}await wait(100);}
 let p=await api('/projects',{title:'Independent layers browser',aspect:'16:9'});p=await api('/projects/'+p.id,undefined,'GET');const pid=p.id,sid=p.scenes[0].id;
 const fd=new FormData();fd.append('file',new Blob([fs.readFileSync(path.join(root,'examples/fixture_assets/clip1.mp4'))],{type:'video/mp4'}),'clip1.mp4');const asset=await (await fetch(base+'/api/assets/upload?project_id='+pid,{method:'POST',body:fd})).json();
 await api('/scenes/'+sid+'/shots',{asset_id:asset.id});await api('/scenes/'+sid,{timing_mode:'fixed',requested_duration_ms:20000,font:{captions_enabled:true,caption_segments:[{id:'cap1',text:'First caption box',start_ms:1000,end_ms:3000},{id:'cap2',text:'Second caption box',start_ms:3000,end_ms:5000}]}},'PATCH');
 browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{}),args:['--no-sandbox','--disable-dev-shm-usage']});
 const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(frontend);await page.getByRole('button',{name:/Independent layers browser Open project/}).click();await page.getByRole('button',{name:'Skip tour',exact:true}).click();
 async function read(){return await api('/projects/'+pid,undefined,'GET');}
 async function saved(fn){for(let i=0;i<100;i++){p=await read();if(fn(p)){await page.waitForFunction(()=>Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='Add image at playhead')?.disabled===false);return p;}await wait(100);}throw new Error('Saved edit not found: '+JSON.stringify(p.finishing_json));}
 async function seek(ms){await page.evaluate(ms=>window.dispatchEvent(new CustomEvent('sceneforge-timeline-seek',{detail:{timeMs:ms}})),ms);await page.waitForFunction(ms=>Number(document.querySelector('[aria-label="Timeline playhead"]')?.getAttribute('aria-valuenow'))===ms,ms);}
 // Use the real timeline ruler's keyboard controls: Home, then 150 frames = 5s at 30fps.
 const ruler=page.getByRole('slider',{name:'Timeline playhead',exact:true});await ruler.focus();await page.keyboard.press('Home');for(let i=0;i<150;i++)await page.keyboard.press('ArrowRight');assert(Math.abs(Number(await ruler.getAttribute('aria-valuenow'))-5000)<40);
 const chooser=page.waitForEvent('filechooser');await page.getByRole('button',{name:'Add image at playhead',exact:true}).click();await (await chooser).setFiles(path.join(root,'examples/fixture_assets/image1.png'));p=await saved(p=>p.finishing_json?.layer_clips?.length===1);const image=p.finishing_json.layer_clips[0];assert(Math.abs(image.start_ms-5000)<40);assert.equal(p.scenes[0].shots.length,1);console.log('PASS image chooser adds an independent clip at five seconds');
 const imageDraft=page.getByRole('region',{name:'Overlay draft preview'});
 await imageDraft.getByAltText('Draft image').waitFor({state:'visible'});
 await page.waitForFunction(id=>{const img=document.querySelector(`[data-draft-layer="${id}"]`);return img?.complete&&img.naturalWidth>0;},image.id);
 await page.getByRole('slider',{name:'Overlay opacity slider',exact:true}).fill('55');
 assert.equal(await imageDraft.locator('img').evaluate(e=>getComputedStyle(e).opacity),'0.55');
 assert.equal((await read()).finishing_json.layer_clips.find(c=>c.id===image.id).opacity,100);
 await page.getByRole('slider',{name:'Overlay opacity slider',exact:true}).fill('100');
 console.log('PASS image draft preview shows local slider changes without saving');

 // Drop a text tool onto O2 at eight seconds.
 await page.getByRole('tab',{name:'Text',exact:true}).click();const tool=page.getByRole('button',{name:'Timeline Text+',exact:true});assert.equal(await page.locator('.text-add-actions .text-tool-card').count(),3);await page.getByRole('heading',{name:'Scene titles & labels',exact:true}).waitFor();const lane=page.locator('[data-layer-track="1"]');await lane.scrollIntoViewIfNeeded();const r=await lane.boundingBox();
 const transfer=await page.evaluateHandle(()=>new DataTransfer());await tool.dispatchEvent('dragstart',{dataTransfer:transfer});await lane.dispatchEvent('drop',{dataTransfer:transfer,clientX:r.x+8*55,clientY:r.y+15});p=await saved(p=>p.finishing_json?.layer_clips?.length===2);let text=p.finishing_json.layer_clips.find(c=>c.kind==='text_plus');assert.equal(text.track,1);assert(Math.abs(text.start_ms-8000)<40);
 await page.getByRole('textbox',{name:'Overlay text',exact:true}).fill('PARIS 1969');await page.getByRole('spinbutton',{name:'Overlay length (seconds)',exact:true}).fill('4');await page.getByRole('spinbutton',{name:'Overlay start (seconds)',exact:true}).fill('5');await page.getByRole('spinbutton',{name:'Overlay rotation',exact:true}).fill('15');// Draft controls must preview locally before saving and keep the committed clip intact.
 const draftBox=page.getByRole('region',{name:'Overlay draft preview'});await draftBox.waitFor({state:'visible'});
 await page.waitForFunction(id=>{const img=document.querySelector(`[data-draft-layer="${id}"]`);return img?.complete&&img.naturalWidth>0&&decodeURIComponent(img.src).includes('PARIS 1969');},text.id);
 assert.notEqual((await read()).finishing_json.layer_clips.find(c=>c.id===text.id).text,'PARIS 1969');
 await page.getByRole('slider',{name:'Overlay opacity slider',exact:true}).fill('65');
 assert.equal(await page.getByRole('spinbutton',{name:'Overlay opacity',exact:true}).inputValue(),'65');
 assert.equal(await draftBox.locator('img').evaluate(e=>getComputedStyle(e).opacity),'0.65');
 await page.getByRole('slider',{name:'Overlay width slider',exact:true}).fill('45');
 assert.equal(await page.getByRole('spinbutton',{name:'Overlay width',exact:true}).inputValue(),'45');
 await page.getByRole('slider',{name:'Overlay opacity slider',exact:true}).fill('100');
 fs.mkdirSync(path.join(root,'docs/qa'),{recursive:true});
 await draftBox.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(root,'docs/qa/overlay-draft-preview-093.png'),fullPage:true});
 console.log('PASS sliders update precise values and draft preview before Apply without changing saved clip');
 // A broken Windows font DLL must explain recovery in the draft pane.
 const fontRoute='**/layer-preview?style=*';
 await page.route(fontRoute,route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Text rendering unavailable. Run scripts/setup.bat and restart SceneForge.'})}));
 await page.getByRole('textbox',{name:'Overlay text',exact:true}).fill('FONT ERROR TEST');
 await page.waitForFunction(()=>{
  const img=document.querySelector('.layer-draft-preview img');
  return img&&JSON.parse(new URL(img.src).searchParams.get('style')).text==='FONT ERROR TEST'&&document.querySelector('.layer-draft-preview [role="status"]')?.textContent.includes('scripts/setup.bat');
 });
 assert.equal((await read()).finishing_json.layer_clips.find(c=>c.id===text.id).text,text.text);
 await page.screenshot({path:path.join(root,'docs/qa/text-runtime-recovery.png'),fullPage:true});
 await page.unroute(fontRoute);
 await page.getByRole('textbox',{name:'Overlay text',exact:true}).fill('PARIS 1969');
 try {await page.waitForFunction(()=>{const img=document.querySelector('.layer-draft-preview img');return img?.complete&&img.naturalWidth>0&&document.querySelector('.layer-draft-preview [role="status"]')?.textContent==='';});} catch(error) {console.error('DRAFT RECOVERY STATE',JSON.stringify(await page.locator('.layer-draft-preview').evaluateAll(elements=>elements.map(el=>({status:el.querySelector('[role="status"]')?.textContent,images:Array.from(el.querySelectorAll('img')).map(img=>({src:img.src,complete:img.complete,width:img.naturalWidth}))})))));throw error;}
 console.log('PASS font-runtime error shown in draft, saved text intact, recovered preview loads');
 // An older error fetch must not overwrite a successful retry of the same URL.
 let releaseError, errorStarted, errorFinished, injectDelayedError=true;
 const heldError=new Promise(resolve=>{releaseError=resolve;});
 const startedError=new Promise(resolve=>{errorStarted=resolve;});
 const finishedError=new Promise(resolve=>{errorFinished=resolve;});
 await page.route(fontRoute,async route=>{
  if(!injectDelayedError){await route.continue();return;}
  if(route.request().resourceType()!=='image'){
   errorStarted();await heldError;
   await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Delayed font error: scripts/setup.bat'})});
   errorFinished();
  }else await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Delayed font error: scripts/setup.bat'})});
 });
 const overlayText=page.getByRole('textbox',{name:'Overlay text',exact:true});
 await overlayText.fill('DELAYED FONT RETRY');
 await Promise.race([startedError,new Promise((_,reject)=>setTimeout(()=>reject(new Error('Error-detail fetch did not start')),10000))]);
 injectDelayedError=false;
 async function loadedText(value){
  await overlayText.fill(value);
  await page.waitForFunction(expected=>{
   const img=document.querySelector('.layer-draft-preview img');
   if(!img?.complete||!img.naturalWidth)return false;
   const style=JSON.parse(new URL(img.src).searchParams.get('style'));
   return style.text===expected&&document.querySelector('.layer-draft-preview [role="status"]')?.textContent==='';
  },value);
 }
 await loadedText('PARIS 1969');
 await loadedText('DELAYED FONT RETRY');
 releaseError();await finishedError;
 await page.unroute(fontRoute);
 await page.waitForTimeout(300);
 assert.equal(await page.locator('.layer-draft-preview [role="status"]').textContent(),'','A delayed old error cannot replace a loaded retry');
 await loadedText('PARIS 1969');
 console.log('PASS delayed error discarded after successful same-URL preview retry');


 await page.getByRole('button',{name:'Apply changes',exact:true}).click();p=await saved(p=>p.finishing_json.layer_clips.find(c=>c.id===text.id)?.text==='PARIS 1969');text=p.finishing_json.layer_clips.find(c=>c.id===text.id);assert.equal(text.duration_ms,4000);assert.equal(text.rotation,15);
 await page.getByRole('button',{name:'Saved',exact:true}).waitFor({state:'visible'});assert(await page.getByRole('button',{name:'Saved',exact:true}).isDisabled());
 await page.getByRole('textbox',{name:'Overlay text',exact:true}).fill('ANOTHER EDIT');assert(await page.getByRole('button',{name:'Apply changes',exact:true}).isEnabled());
 await page.getByRole('textbox',{name:'Overlay text',exact:true}).fill('PARIS 1969');assert(await page.getByRole('button',{name:'Saved',exact:true}).isDisabled());
 console.log('PASS Apply returns to Saved and re-enables for the next edit');
 await seek(5500);
 // Preview uses the backend raster and image is draggable in the actual scene frame.
 const preview=page.locator(`.preview-canvas [data-preview-layer="${image.id}"]`);await preview.waitFor({state:'visible'});await page.waitForFunction(id=>{const img=document.querySelector(`.preview-canvas [data-preview-layer="${id}"]`);return img?.complete&&img.naturalWidth>0;},image.id);
 const b=await preview.boundingBox();await page.mouse.move(b.x+b.width/2,b.y+b.height/2);await page.mouse.down();await page.mouse.move(b.x+b.width/2+35,b.y+b.height/2-20,{steps:6});await page.mouse.up();p=await saved(p=>p.finishing_json.layer_clips.find(c=>c.id===image.id)?.x>50);assert(p.finishing_json.layer_clips.find(c=>c.id===image.id).y<50);console.log('PASS draggable Text+ card, real placement controls and preview drag persist');
 // Drag on the timeline: move right two seconds and down to another track.
 let clip=page.locator(`[data-layer-id="${image.id}"]`);await clip.scrollIntoViewIfNeeded();let cr=await clip.boundingBox();await page.mouse.move(cr.x+30,cr.y+19);await page.mouse.down();await page.mouse.move(cr.x+140,cr.y+67,{steps:8});await page.mouse.up();p=await saved(p=>p.finishing_json.layer_clips.find(c=>c.id===image.id)?.track===1);assert(Math.abs(p.finishing_json.layer_clips.find(c=>c.id===image.id).start_ms-7000)<70);
 await page.waitForFunction(id=>document.querySelector(`[data-layer-id="${id}"]`)?.closest('[data-layer-track]')?.dataset.layerTrack==='1',image.id);
 clip=page.locator(`[data-layer-id="${image.id}"]`);await clip.scrollIntoViewIfNeeded();const trim=clip.getByRole('separator',{name:/Trim end/});const tb=await trim.boundingBox();await page.mouse.move(tb.x+4,tb.y+15);await page.mouse.down();await page.mouse.move(tb.x+59,tb.y+15,{steps:5});await page.mouse.up();p=await saved(p=>p.finishing_json.layer_clips.find(c=>c.id===image.id)?.duration_ms>3900);
 const length=p.finishing_json.layer_clips.find(c=>c.id===image.id).duration_ms;await page.evaluate(()=>document.activeElement.blur());await page.keyboard.press('Control+z');p=await saved(p=>p.finishing_json.layer_clips.find(c=>c.id===image.id)?.duration_ms===3000);await page.keyboard.press('Control+y');await saved(p=>p.finishing_json.layer_clips.find(c=>c.id===image.id)?.duration_ms===length);console.log('PASS timeline movement, track movement, edge trim and Undo/Redo');
 // OS file drops use actual File objects, not the scene-insertion route.
 const file=fs.readFileSync(path.join(root,'examples/fixture_assets/image2.png'));const files=await page.evaluateHandle(bytes=>{const dt=new DataTransfer();dt.items.add(new File([new Uint8Array(bytes)],'local-image.png',{type:'image/png'}));return dt;},Array.from(file));const upper=page.locator('[data-layer-track="0"]');const ur=await upper.boundingBox();await upper.dispatchEvent('drop',{dataTransfer:files,clientX:ur.x+220,clientY:ur.y+15});p=await saved(p=>p.finishing_json.layer_clips.length===3);const local=p.finishing_json.layer_clips.find(c=>c.name==='local-image.png');assert(Math.abs(local.start_ms-4000)<40);
 // Real Media Pool asset drag data is also accepted. Keep source identity.
 await page.getByRole('button',{name:'Media Pool',exact:true}).click();const pool=page.locator(`[data-asset-id="${local.asset_id}"]`); // fallback selects the filename if the pool does not expose ids
 const poolItem=await pool.count()?pool:page.locator('[draggable="true"]').filter({hasText:'local-image.png'}).first();await poolItem.waitFor();const pooled=await page.evaluateHandle(()=>new DataTransfer());await poolItem.dispatchEvent('dragstart',{dataTransfer:pooled});await upper.dispatchEvent('drop',{dataTransfer:pooled,clientX:ur.x+550,clientY:ur.y+15});p=await saved(p=>p.finishing_json.layer_clips.length===4);assert.equal(p.finishing_json.layer_clips[3].asset_id,local.asset_id);console.log('PASS local-file and Media Pool drops add overlays without replacing video');
 // Captions are visible, separately timed beige boxes on the timeline and in the editor.
 const captions=page.locator('.caption-edit-clip');assert.equal(await captions.count(),2);const color=await captions.first().evaluate(e=>getComputedStyle(e).backgroundColor);assert.equal(color,'rgb(207, 182, 142)');await captions.first().click();const card=page.locator('[data-caption-segment-id="cap1"]');await card.waitFor({state:'visible'});assert.equal(await card.evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(204, 181, 141)');assert.equal(await card.locator('textarea').inputValue(),'First caption box');
 function contrast(a,b){const lum=rgb=>{const c=rgb.match(/\d+/g).slice(0,3).map(v=>{v=Number(v)/255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;});return c[0]*.2126+c[1]*.7152+c[2]*.0722;};const x=lum(a),y=lum(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
 for(const theme of ['dark','light']){
  await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
  const colors=await card.evaluate(e=>{const h=e.querySelector('strong'),b=e.querySelector('button');return {bg:getComputedStyle(e).backgroundColor,fg:getComputedStyle(h).color,buttonBg:getComputedStyle(b).backgroundColor,buttonFg:getComputedStyle(b).color};});
  assert(contrast(colors.bg,colors.fg)>4.5,theme+' caption heading contrast');
  assert(contrast(colors.buttonBg,colors.buttonFg)>4.5,theme+' caption action contrast');
 }
 await page.evaluate(()=>document.documentElement.dataset.theme='dark');
 console.log('PASS darker beige caption numbers and action buttons remain readable in dark/light themes');

 await page.reload();await page.getByRole('button',{name:/Independent layers browser Open project/}).click();await page.waitForFunction(()=>document.querySelectorAll('.timeline-layer-clip').length===4);assert.equal(await page.locator('.timeline-layer-clip').count(),4);assert.equal(await page.locator('.picture-clip').count(),3);
 // Context actions and common shortcuts operate on the selected overlay, keeping video intact.
 const restoredText=page.locator(`[data-layer-id="${text.id}"]`);await restoredText.scrollIntoViewIfNeeded();await restoredText.click({button:'right'});
 await page.getByRole('menuitem',{name:/Duplicate/}).click();await saved(p=>p.finishing_json.layer_clips.length===5);assert.equal(await page.locator('.picture-clip').count(),3);
 await page.evaluate(()=>document.activeElement.blur());await page.keyboard.press('Control+z');await saved(p=>p.finishing_json.layer_clips.length===4);
 await restoredText.click();await page.waitForFunction(id=>document.querySelector(`[data-layer-id="${id}"]`)?.classList.contains('selected'),text.id);
 await page.evaluate(()=>document.activeElement.blur());await page.keyboard.press('Control+c');await seek(12000);await page.keyboard.press('Control+v');p=await saved(p=>p.finishing_json.layer_clips.length===5);assert.equal(p.finishing_json.layer_clips[4].text,'PARIS 1969');assert.equal(p.finishing_json.layer_clips[4].start_ms,12000);
 await page.keyboard.press('Delete');await saved(p=>p.finishing_json.layer_clips.length===4);assert.equal(await page.locator('.picture-clip').count(),3);
 await restoredText.click();await seek(6500);await page.keyboard.press('s');p=await saved(p=>p.finishing_json.layer_clips.length===5);assert.equal(p.finishing_json.layer_clips.find(c=>c.id===text.id).duration_ms,1500);assert.equal(p.scenes[0].shots.length,1);
 await page.keyboard.press('Control+z');await saved(p=>p.finishing_json.layer_clips.length===4);
 // Pending text is saved by Ctrl+S before the restore point is made.
 await restoredText.click();await page.getByRole('textbox',{name:'Overlay text',exact:true}).fill('SAVE THIS TITLE');await page.getByRole('heading',{name:'Text+ clip',exact:true}).click();await page.keyboard.press('Control+s');await saved(p=>p.finishing_json.layer_clips.find(c=>c.id===text.id)?.text==='SAVE THIS TITLE');await page.waitForFunction(()=>document.querySelector('.tool-feedback')?.textContent.includes('Restore point saved.'));
 assert.deepEqual(errors,[]);console.log('PASS overlay context menu, copy/paste/delete/split shortcuts, scene preservation and Ctrl+S draft save');
 await seek(8500);await page.evaluate(()=>document.activeElement.blur());await page.keyboard.press('l');const live=page.getByRole('region',{name:'Live timeline playback'});await live.waitFor({state:'visible'});await page.keyboard.press('k');const liveImage=live.locator(`[data-preview-layer="${image.id}"]`);await liveImage.waitFor({state:'visible'});const liveText=live.locator(`[data-preview-layer="${text.id}"]`);await liveText.waitFor({state:'visible'});assert((await liveText.boundingBox()).width>10);assert((await liveImage.boundingBox()).height>5);await live.getByRole('button',{name:'Close timeline playback',exact:true}).click();console.log('PASS live sequence playback shows timed image and text overlays');

 await page.getByRole('tab',{name:'Text',exact:true}).click();await seek(8500);
 await page.getByRole('separator',{name:'Resize timeline',exact:true}).focus();for(let i=0;i<9;i++)await page.keyboard.press('ArrowUp');
 await page.locator('.inspector-body:visible').evaluate(e=>e.scrollTop=0);
 await page.waitForFunction(()=>Array.from(document.querySelectorAll('.project-layer-preview img')).filter(img=>img.getBoundingClientRect().width>0).every(img=>img.complete&&img.naturalWidth>0));
 fs.mkdirSync(path.join(root,'docs/qa'),{recursive:true});
 await page.screenshot({path:path.join(root,'docs/qa/timeline-overlays-093.png'),fullPage:true});console.log('PASS beige caption boxes, clip persistence after reload, no browser errors');
 const closeInspector=page.getByTitle('Return to scene controls', {exact:true});if(await closeInspector.count())await closeInspector.click();
 await page.getByRole('tab',{name:'Text',exact:true}).click();await page.getByRole('heading',{name:'Whole-video tracks',exact:true}).scrollIntoViewIfNeeded();
 await page.screenshot({path:path.join(root,'docs/qa/styled-text-cards-093.png'),fullPage:true});

 }catch(e){if(browser){const pages=browser.contexts().flatMap(c=>c.pages());if(pages[0])await pages[0].screenshot({path:path.join(data,'failure.png'),fullPage:true}).catch(()=>{});}console.error('Data directory:',data);console.error(logs.slice(-1400));throw e;}finally{if(browser)await browser.close();if(server)server.kill();if(devServer)devServer.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
