// Owner report 2026-10-07: Free timeline opened before a scene had its video, so the
// export contained only the text overlay. Real Chromium, disposable database.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),os=require('os'),{spawn}=require('child_process'),assert=require('assert/strict');
const root=path.resolve(__dirname,'../..'),data=fs.mkdtempSync(path.join(os.tmpdir(),'sf-free-export-')),base='http://127.0.0.1:8097';let server,browser,logs='';
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function api(url,body,method='POST'){const r=await fetch(base+'/api'+url,{method,headers:{'content-type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});assert(r.ok,await r.clone().text());return r.status===204?null:r.json();}
async function upload(pid,name){const form=new FormData();form.append('file',new Blob([fs.readFileSync(path.join(root,'examples/fixture_assets',name))]),name);const r=await fetch(base+'/api/assets/upload?project_id='+pid,{method:'POST',body:form});assert(r.ok);return r.json();}
(async()=>{try{
 server=spawn('python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8097'],{cwd:path.join(root,'backend'),env:{...process.env,SCENEFORGE_DATA_DIR:data}});server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);
 let up=false;for(let i=0;i<150;i++){try{if((await fetch(base+'/api/health')).ok){up=true;break;}}catch{}await wait(100);}assert(up,logs);
 let p=await api('/projects',{title:'Owner export',aspect:'16:9',fps:25});p=await api('/projects/'+p.id,undefined,'GET');const [s1,s2]=p.scenes;
 for(const s of p.scenes)await api('/scenes/'+s.id,{timing_mode:'fixed',requested_duration_ms:3000,font:{captions_enabled:false}},'PATCH');
 // Free timeline switched on while no scene had media: it starts empty.
 await api('/projects/'+p.id,{finishing:{free_timeline:{enabled:true,clips:[]}}},'PATCH');
 const v=await upload(p.id,'clip1.mp4');await api('/scenes/'+s2.id+'/shots',{asset_id:v.id});
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});const page=await browser.newPage({viewport:{width:1440,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);await page.getByText('Owner export').first().click();
 const skip=page.getByRole('button',{name:'Skip tour',exact:true});await page.waitForTimeout(1500);if(await skip.count())await skip.click();
 const early=page.locator('dialog.editor-confirm');if(await early.count())console.log('EARLY DIALOG:',await early.innerText());
 await page.getByRole('button',{name:'Export video',exact:true}).click();
 await page.locator('.export-dialog').getByRole('button',{name:'Export',exact:true}).click();
 const dialog=page.locator('dialog.editor-confirm');await dialog.waitFor();
 if(process.env.SF_QA_DIR)await page.screenshot({path:path.join(process.env.SF_QA_DIR,'free-export-choice.png')});const text=await dialog.innerText();assert(/does not include: Part-2/.test(text)||/does not include:/.test(text),text);
 for(const label of ['Cancel','Export without them','Use Scene assembly instead','Add to the end and export'])assert.equal(await dialog.getByRole('button',{name:label,exact:true}).count(),1,label);
 await dialog.getByRole('button',{name:'Cancel',exact:true}).click();await wait(500);
 p=await api('/projects/'+p.id,undefined,'GET');assert.deepEqual(p.finishing_json.free_timeline.clips,[]);
 console.log('PASS export warns that a scene with media is not on the Free timeline; Cancel changes nothing');
 await page.getByRole('button',{name:'Export video',exact:true}).click();
 await page.locator('.export-dialog').getByRole('button',{name:'Export',exact:true}).click();
 await dialog.waitFor();const exported=page.waitForResponse(r=>/\/api\/projects\/[^/]+\/export/.test(r.url())&&r.request().method()==='POST',{timeout:60000});await dialog.getByRole('button',{name:'Add to the end and export',exact:true}).click();const jobId=(await (await exported).json()).job_id;
 for(let i=0;i<50;i++){p=await api('/projects/'+p.id,undefined,'GET');if(p.finishing_json.free_timeline.clips.length)break;await wait(200);}
 const clips=p.finishing_json.free_timeline.clips;assert.equal(clips.length,1);assert.equal(clips[0].scene_id,s2.id);assert.equal(clips[0].start_ms,0);
 // Wait for the export job to finish and check it is real video, not a black frame.
 let job;for(let i=0;i<900;i++){job=await api('/jobs/'+jobId,undefined,'GET');if(['succeeded','failed','cancelled'].includes(job.status))break;await wait(200);}
 assert.equal(job.status,'succeeded',JSON.stringify(job));
 const out=path.join(data,'check.mp4');fs.writeFileSync(out,Buffer.from(await (await fetch(base+'/api/assets/'+job.artifact_asset_id+'/stream')).arrayBuffer()));
 const probe=require('child_process').execFileSync('ffprobe',['-v','error','-show_entries','stream=codec_type','-of','csv=p=0',out]).toString();assert(/video/.test(probe)&&/audio/.test(probe),probe);
 const px=require('child_process').execFileSync('ffmpeg',['-v','error','-ss','1.5','-i',out,'-frames:v','1','-vf','scale=32:18','-f','rawvideo','-pix_fmt','gray','-']);assert(px.reduce((a,b)=>a+b,0)/px.length>12,'exported frame is black');
 console.log('PASS Add to the end places the missing scene on the Free timeline and exports');
 assert.deepEqual(errors,[]);console.log('PASS no browser errors');
}catch(e){try{const pg=browser&&browser.contexts()[0]?.pages()[0];if(pg){await pg.screenshot({path:'/tmp/claude-0/fail.png'});console.log('DIALOGS',await pg.locator('dialog').evaluateAll(d=>d.map(x=>x.className+':'+x.innerText.slice(0,200))));}}catch{}console.error(e);console.error(logs.slice(-3000));process.exitCode=1;}finally{await browser?.close();server?.kill();}})();
