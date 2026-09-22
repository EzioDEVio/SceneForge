const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),os=require('os'),{spawn}=require('child_process'),assert=require('assert/strict');
const root=path.resolve(__dirname,'../..'),data=fs.mkdtempSync(path.join(os.tmpdir(),'sf23-'));
const base='http://127.0.0.1:8023';let server,browser,logs='';
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function api(url,body,method='POST'){const r=await fetch(base+'/api'+url,{method,headers:body instanceof FormData?{}:{'content-type':'application/json'},body:body===undefined?undefined:body instanceof FormData?body:JSON.stringify(body)});assert(r.ok,await r.clone().text());return r.json();}
(async()=>{try{
server=spawn('python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8023'],{cwd:path.join(root,'backend'),env:{...process.env,SCENEFORGE_DATA_DIR:data}});server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);
let up=false;for(let i=0;i<100;i++){try{if((await fetch(base+'/api/health')).ok){up=true;break;}}catch{}await wait(100);}assert(up,logs);
let p=await api('/projects',{title:'Titles and duration review',aspect:'16:9'});p=await api('/projects/'+p.id,undefined,'GET');
for(let i=0;i<2;i++){const f=new FormData();f.append('file',new Blob([fs.readFileSync(path.join(root,`examples/fixture_assets/image${i+1}.png`))]),`frame${i}.png`);const a=await api('/assets/upload?project_id='+p.id,f);await api('/scenes/'+p.scenes[i].id+'/shots',{asset_id:a.id,motion:{type:'static'}});await api('/scenes/'+p.scenes[i].id,{timing_mode:'fixed',requested_duration_ms:2000,...(i?{transition_in:{type:'dissolve',duration_ms:500}}:{})},'PATCH');}
browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{}),args:['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const page=await browser.newPage({viewport:{width:1440,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
await page.goto(base);await page.getByRole('button',{name:/Titles and duration review Open project/}).click();
const handle=page.getByRole('slider',{name:'Resize Part-1 duration',exact:true});
await handle.focus();await page.keyboard.press('ArrowRight');
await page.waitForFunction(()=>document.querySelector('[aria-label="Resize Part-1 duration"]').getAttribute('aria-valuenow')==='2.1');
await page.getByRole('button',{name:'Undo timeline edit',exact:true}).click();
await page.waitForFunction(()=>document.querySelector('[aria-label="Resize Part-1 duration"]').getAttribute('aria-valuenow')==='2');
await page.getByRole('button',{name:'Redo timeline edit',exact:true}).click();
await page.waitForFunction(()=>document.querySelector('[aria-label="Resize Part-1 duration"]').getAttribute('aria-valuenow')==='2.1');
const box=await handle.boundingBox();await page.mouse.move(box.x+4,box.y+20);await page.mouse.down();await page.mouse.move(box.x+59,box.y+20,{steps:8});await page.mouse.up();
await page.waitForFunction(()=>document.querySelector('[aria-label="Resize Part-1 duration"]').getAttribute('aria-valuenow')==='3.1');
await page.getByRole('button',{name:'Add title card',exact:true}).click();
await page.getByRole('textbox',{name:'Title card text',exact:true}).fill('بداية الحكاية');
await page.getByRole('combobox',{name:'Title card animation',exact:true}).selectOption('slide');
await page.getByRole('button',{name:'Create title card',exact:true}).click();
await page.waitForFunction(()=>document.querySelectorAll('.picture-clip').length===4);
const current=await api('/projects/'+p.id,undefined,'GET');const card=current.scenes[3];
assert.equal(current.scenes[0].requested_duration_ms,3100);assert.equal(card.font_json.layers[0].animation,'slide');assert.equal(card.shots.length,1);
assert.equal(await page.getByRole('button',{name:'Play movie',exact:true}).isEnabled(),true);
await page.getByRole('button',{name:'Play movie',exact:true}).click();
await page.locator('.program-monitor video').waitFor({timeout:180000});await page.waitForFunction(()=>document.querySelector('.program-monitor video').readyState>=2);
const duration=await page.locator('.program-monitor video').evaluate(v=>v.duration);assert(Math.abs(duration-9.6)<.15,`duration ${duration}`);
await page.getByRole('button',{name:'Stop full video',exact:true}).click();assert.equal(await page.locator('.program-monitor video').evaluate(v=>v.currentTime),0);
await page.getByRole('button',{name:'Next scene',exact:true}).click();assert(Math.abs(await page.locator('.program-monitor video').evaluate(v=>v.currentTime)-2.6)<.15);
await page.getByRole('button',{name:'Previous scene',exact:true}).click();assert.equal(await page.locator('.program-monitor video').evaluate(v=>v.currentTime),0);
await page.getByRole('button',{name:'Play movie',exact:true}).click();await page.getByRole('button',{name:'Pause full video',exact:true}).click();assert.equal(await page.locator('.program-monitor video').evaluate(v=>v.paused),true);
for(const width of [1366,1920]){await page.setViewportSize({width,height:1080});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));}
fs.mkdirSync(path.join(root,'docs/qa'),{recursive:true});await page.screenshot({path:path.join(root,'docs/qa/titles-duration-24.png')});assert.deepEqual(errors,[]);
console.log('PASS duration keyboard, undo/redo, pointer drag, Arabic slide title creation, full movie 9.6s, and playback controls');
}catch(e){console.error(e,logs.slice(-2500));process.exitCode=1;}finally{await browser?.close();server?.kill();}})();
