// Real Chromium + disposable backend: no providers, no existing user projects.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),os=require('os'),{spawn}=require('child_process'),assert=require('assert/strict');
const root=path.resolve(__dirname,'../..'),data=fs.mkdtempSync(path.join(os.tmpdir(),'sf093-'));
const base='http://127.0.0.1:8093',front=process.env.SF_BROWSER_DEV?'http://127.0.0.1:8193':base;let server,devServer,browser,logs='';
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function api(url,body,method='POST'){const r=await fetch(base+'/api'+url,{method,headers:{'content-type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});assert(r.ok,await r.clone().text());return r.json();}
(async()=>{try{
server=spawn('python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8093'],{cwd:path.join(root,'backend'),env:{...process.env,SCENEFORGE_DATA_DIR:data}});server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);
let up=false;for(let i=0;i<150;i++){try{if((await fetch(base+'/api/health')).ok){up=true;break;}}catch{}await wait(100);}assert(up,logs);
if(process.env.SF_BROWSER_DEV){devServer=spawn(process.execPath,[path.join(root,'frontend/node_modules/vite/bin/vite.js'),'--config','vite.browser-tests.config.ts','--host','127.0.0.1','--port','8193'],{cwd:path.join(root,'frontend'),env:{...process.env,SF_DEV_BACKEND:base}});devServer.stderr.on('data',d=>logs+=d);let ready=false;for(let i=0;i<150;i++){try{if((await fetch(front)).ok){ready=true;break;}}catch{}await wait(100);}assert(ready,logs);}
let p=await api('/projects',{title:'Release 093 regression',aspect:'16:9'});p=await api('/projects/'+p.id,undefined,'GET');
browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{}),args:['--no-sandbox','--disable-dev-shm-usage',...(process.env.CHROMIUM_SINGLE_PROCESS?['--single-process','--no-zygote','--in-process-gpu','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']:[])]});
const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto(front);console.log('Browser opened editor home');await page.getByRole('button',{name:/Release 093 regression Open project/}).click();
await page.getByRole('button',{name:'Skip tour',exact:true}).click();
// Click the label inside an unselected scene. Assert an actual chooser, multiple files,
// and persisted shots on that scene only (rather than whichever inspector was selected).
const chooserPromise=page.waitForEvent('filechooser');
await page.getByRole('button',{name:'Storyboard scene 2',exact:true}).getByText('Add media',{exact:true}).click();
const chooser=await chooserPromise;assert(chooser.isMultiple());
await chooser.setFiles([path.join(root,'examples/fixture_assets/image1.png'),path.join(root,'examples/fixture_assets/image2.png'),path.join(root,'examples/fixture_assets/clip1.mp4')]);
await page.waitForFunction(()=>document.querySelectorAll('.picture-clip')[1]?.querySelector('.filmstrip'));
p=await api('/projects/'+p.id,undefined,'GET');assert.equal(p.scenes[1].shots.length,3);assert.equal(p.scenes[0].shots.length,0);assert(p.scenes[1].shots.some(s=>s.asset.type==='video'));
await page.getByRole('button',{name:'Add title card',exact:true}).click();
let dialog=page.getByRole('dialog',{name:'Create title card',exact:true});
await dialog.getByRole('textbox',{name:'Title card text',exact:true}).fill('PARIS 1969');
await dialog.getByRole('heading',{name:'Create title card',exact:true}).click();
await dialog.getByRole('button',{name:/Neon/}).click();
await dialog.getByRole('combobox',{name:'Title card animation',exact:true}).selectOption('slide');
assert.equal(await dialog.getByRole('textbox',{name:'Title card text'}).inputValue(),'PARIS 1969');
assert.equal(await dialog.getByRole('combobox',{name:'Title card font',exact:true}).locator('option').count(),19);
await dialog.getByRole('combobox',{name:'Title card font',exact:true}).selectOption('DejaVu Serif');
await page.evaluate(()=>document.fonts.ready);
const typing=dialog.getByRole('textbox',{name:'Title card text',exact:true});
await typing.fill('');await typing.focus();
const fixedBox=await typing.boundingBox();
const fixedScroll=await dialog.evaluate(el=>el.querySelector(".title-designer-controls").scrollTop);
await typing.pressSequentially('A calm title · مرحبا بالعالم · 2026',{delay:25});
const typedBox=await typing.boundingBox();
assert(Math.abs(typedBox.x-fixedBox.x)<1&&Math.abs(typedBox.y-fixedBox.y)<1,'Title typing must not move the control');
assert.equal(await dialog.evaluate(el=>el.querySelector(".title-designer-controls").scrollTop),fixedScroll,'Title typing must not jump the scroll position');
assert(await typing.evaluate(el=>document.activeElement===el),'Title typing retains focus');
await typing.fill('PARIS 1969');
await page.screenshot({path:path.join(root,'docs/qa/friendly-title-editing.png'),fullPage:true});
await page.evaluate(()=>document.documentElement.dataset.theme='light');
await page.screenshot({path:path.join(root,'docs/qa/friendly-title-editing-light.png'),fullPage:true});
await page.evaluate(()=>document.documentElement.dataset.theme='dark');
console.log('PASS 19 bundled title fonts, Arabic/English typing with fixed control geometry, focus and scroll');

await page.keyboard.press('Escape');await dialog.waitFor({state:'detached'});
for(const action of ['Cancel','Close title card','outside']){
 await page.getByRole('button',{name:'Add title card',exact:true}).click();
 dialog=page.getByRole('dialog',{name:'Create title card',exact:true});await dialog.waitFor();
 if(action==='outside')await page.locator('.title-designer-backdrop').click({position:{x:20,y:100}});
 else await dialog.getByRole('button',{name:action,exact:true}).click();
 await dialog.waitFor({state:'detached'});
}
await page.getByRole('tab',{name:'Overlays',exact:true}).click();
// 0.9.3 RC4: creative titles open in their own dialog with a live preview and settings tabs.
await page.getByRole('button',{name:/^Video inside text/}).click();
const koDialog=page.getByRole('dialog',{name:'Video inside text',exact:true});await koDialog.waitFor();
const title=page.getByRole('textbox',{name:'Video inside text title',exact:true});
await title.waitFor();assert.equal(await title.getAttribute('placeholder'),'e.g. PARIS or 1969');
assert.equal(await page.locator('.ko-preview').innerText(),'YOUR TITLE');
await title.fill('PARIS');assert.equal(await page.locator('.ko-preview').innerText(),'PARIS');

// Typing and native-dialog guards: none of the editor shortcuts may run here.
const manualSnapshots=[];page.on('request',r=>{if(r.url().endsWith('/snapshots')&&r.method()==='POST'&&r.postDataJSON()?.auto===false)manualSnapshots.push(r);});
await title.focus();
for(const k of ['Control+/','Control+s','Control+e','Control+z','Control+y'])await page.keyboard.press(k);
assert.equal(await page.getByRole('dialog',{name:'Keyboard shortcuts'}).count(),0);
assert.equal(await page.getByRole('dialog',{name:'Export video'}).count(),0);assert.equal(manualSnapshots.length,0);
const typingSceneCount=await page.locator('.picture-clip').count(),typingZoom=await page.getByRole('slider',{name:'Timeline zoom',exact:true}).inputValue();
for(const k of ['s','m','Space','+','-','Delete','?'])await page.keyboard.press(k);
assert.equal(await page.locator('.picture-clip').count(),typingSceneCount);assert.equal(await page.getByRole('slider',{name:'Timeline zoom',exact:true}).inputValue(),typingZoom);
assert.equal(await page.locator('dialog.editor-confirm').count(),0);assert.equal(await page.getByRole('dialog',{name:'Keyboard shortcuts'}).count(),0);
await page.keyboard.press('Escape');await koDialog.waitFor({state:'detached'});
// A nested contenteditable child must also count as typing.
await page.evaluate(()=>{const edit=document.createElement('div');edit.contentEditable='true';edit.id='typing-guard-fixture';edit.innerHTML='<span>Editable text</span>';document.body.append(edit);edit.focus();const selection=window.getSelection(),range=document.createRange();range.selectNodeContents(edit.firstChild);range.collapse(false);selection.removeAllRanges();selection.addRange(range);});
await page.keyboard.press('Control+e');await page.keyboard.press('Control+/');
assert.equal(await page.getByRole('dialog',{name:'Export video'}).count(),0);assert.equal(await page.getByRole('dialog',{name:'Keyboard shortcuts'}).count(),0);
await page.evaluate(()=>document.getElementById('typing-guard-fixture').remove());
await page.evaluate(()=>document.activeElement.blur());
await page.keyboard.press('Control+/');
let sheet=page.getByRole('dialog',{name:'Keyboard shortcuts'});await sheet.waitFor();
await sheet.getByRole('searchbox',{name:'Search keyboard shortcuts'}).fill('split');
assert.equal(await sheet.locator('.shortcut-row').count(),1);assert.equal(await sheet.locator('kbd').innerText(),'S');
await page.keyboard.press('Escape');await sheet.waitFor({state:'detached'});
await page.keyboard.press('?');await sheet.waitFor();await page.keyboard.press('Escape');await sheet.waitFor({state:'detached'});
await page.getByRole('button',{name:'Storyboard scene 2',exact:true}).click();
await page.keyboard.press('Control+a');assert.equal(await page.locator('.picture-clip.multi').count(),3);
const zoom=page.getByRole('slider',{name:'Timeline zoom',exact:true});const z=Number(await zoom.inputValue());
await page.keyboard.press('+');assert(Number(await zoom.inputValue())>z);await page.keyboard.press('-');assert(Math.abs(Number(await zoom.inputValue())-z)<.01);
await page.keyboard.press('m');const prompt=page.locator('dialog.editor-confirm');await prompt.waitFor();
await prompt.getByRole('textbox',{name:'Value',exact:true}).fill('Chapter beat');
await prompt.getByRole('button',{name:'Continue',exact:true}).focus();await page.keyboard.press('Control+e');assert.equal(await page.getByRole('dialog',{name:'Export video'}).count(),0);
await prompt.getByRole('button',{name:'Continue',exact:true}).click();
await page.getByRole('button',{name:'Seek to marker Chapter beat',exact:true}).waitFor();
// The marker appears optimistically; wait for its save before invoking Undo.
await page.getByRole('button',{name:'Undo timeline edit',exact:true}).waitFor();
await page.waitForFunction(()=>!document.querySelector('button[aria-label="Undo timeline edit"]')?.disabled);
await page.keyboard.press('Control+z');await page.getByRole('button',{name:'Seek to marker Chapter beat',exact:true}).waitFor({state:'detached'});
await page.waitForFunction(()=>!document.querySelector('button[aria-label="Redo timeline edit"]')?.disabled);
await page.keyboard.press('Control+y');await page.getByRole('button',{name:'Seek to marker Chapter beat',exact:true}).waitFor();
await page.keyboard.press('Control+s');await page.waitForFunction(()=>document.querySelector('.tool-feedback')?.textContent.includes('Restore point saved.'));
assert.equal(manualSnapshots.length,1);const snapshots=await api('/projects/'+p.id+'/snapshots',undefined,'GET');assert(snapshots.snapshots.length>=1);
await page.keyboard.press('Control+e');const exp=page.getByRole('dialog',{name:'Export video',exact:true});await exp.waitFor();
await exp.getByRole('button',{name:'Close',exact:true}).click();await exp.waitFor({state:'detached'});
// A simple still scene can be split without baking. Upload through the real chooser.
const picker=page.waitForEvent('filechooser');await page.getByRole('button',{name:'Storyboard scene 3',exact:true}).click();
await (await picker).setFiles(path.join(root,'examples/fixture_assets/image1.png'));
await page.waitForFunction(()=>document.querySelectorAll('.picture-clip')[2]?.querySelector('.filmstrip'));
await page.keyboard.press('ArrowRight');await page.keyboard.press('ArrowRight');await page.keyboard.press('s');
await page.waitForFunction(()=>document.querySelectorAll('.picture-clip').length===4);
await page.keyboard.press('Control+z');await page.waitForFunction(()=>document.querySelectorAll('.picture-clip').length===3);
await page.keyboard.press('Control+y');await page.waitForFunction(()=>document.querySelectorAll('.picture-clip').length===4);
p=await api('/projects/'+p.id,undefined,'GET');assert.equal(p.scenes.length,4);assert.equal(p.scenes[2].shots.length,1);assert.equal(p.scenes[3].shots.length,1);
console.log('PASS B: typing guards; Ctrl+/ and ? searchable help; Ctrl+A; +/-; M and undo/redo; Ctrl+S persisted restore point; Ctrl+E; S persisted split and undo/redo');

await page.getByRole('button',{name:'Storyboard scene 2',exact:true}).click();
await page.getByRole('tab',{name:'Overlays',exact:true}).click();
await page.getByRole('button',{name:/^Video inside text/}).click();await koDialog.waitFor();
const koTitle=page.getByRole('textbox',{name:'Video inside text title',exact:true});await koTitle.fill('PREVIEW');
await page.getByLabel('Video inside text font',{exact:true}).selectOption('DejaVu Sans');
const sourceForPreview=await api('/scenes/'+p.scenes[1].id,undefined,'GET');
await page.getByRole('button',{name:'Preview video inside text',exact:true}).click();
const koPreview=page.getByRole('region',{name:'Video inside text preview',exact:true});await koPreview.waitFor();
await koPreview.getByLabel('Rendered video inside text preview',{exact:true}).waitFor({timeout:120000});
await page.waitForFunction(()=>document.querySelector('video[aria-label="Rendered video inside text preview"]')?.readyState>=2);
assert.deepEqual(await api('/scenes/'+p.scenes[1].id,undefined,'GET'),sourceForPreview);
await koPreview.getByLabel('Rendered video inside text preview',{exact:true}).evaluate(video=>{video.currentTime=1;});
await page.waitForFunction(()=>{const v=document.querySelector('video[aria-label="Rendered video inside text preview"]');return v&&v.currentTime>=1&&!v.seeking;});
await page.screenshot({path:path.join(root,'docs/qa/owner-knockout-preview.png'),fullPage:true});
await koTitle.fill('CHANGED');await koPreview.getByRole('status').filter({hasText:'Settings changed'}).waitFor();
await koPreview.getByRole('button',{name:'Close video inside text preview',exact:true}).click();await koPreview.waitFor({state:'detached'});
assert.equal(await koTitle.inputValue(),'CHANGED');
await koDialog.getByRole('button',{name:'Done',exact:true}).click();await koDialog.waitFor({state:'detached'});
console.log('PASS real video-inside-text companion render, playable media, stale-settings hint, Close and no saved mutation');
assert.deepEqual(errors,[]);console.log('PASS A: scene-specific multi-file chooser and persistence; title typing/presets and Cancel/close/Esc/outside; friendly knockout example');
}catch(e){console.error(e,logs.slice(-3000));process.exitCode=1;}finally{await browser?.close();server?.kill();devServer?.kill();}})();
