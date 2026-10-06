// No provider calls: record the actual request contract with a controlled API fixture.
import {build} from 'esbuild';import {createRequire} from 'node:module';import assert from 'node:assert/strict';
await build({entryPoints:['src/scriptSceneSetup.ts'],outfile:'node_modules/.cache/script-setup.cjs',bundle:true,platform:'node',format:'cjs',logLevel:'silent'});
const require=createRequire(import.meta.url),{DEFAULT_SCENE_SETUP,setupImportedScenes,validateSceneSetup,estimatedCaptionSegments,sceneLanguage,visualPrompt}=require('../node_modules/.cache/script-setup.cjs');
const assets=[{id:'picture',type:'image',original_filename:'Photo'}],providers=[{id:'local',name:'chatterbox',capability:'speech'}];
const options={...DEFAULT_SCENE_SETUP,pictures:'pool',mediaIds:['picture'],voiceEngine:'local',voice:'default',captions:'script',motion:'zoom_in',render:true};
const originals=[{id:'one',title:'One',original_text:'Visual: a mountain\nNarration: Hello there',spoken_text:'Hello there and welcome to our story',subtitle_text:'Hello there and welcome to our story',shots:[],voice_takes:[],font_json:{}},{id:'two',title:'Two',original_text:'المشهد ٢',spoken_text:'أهلا بكم في هذه القصة الجديدة',subtitle_text:'أهلا بكم في هذه القصة الجديدة',shots:[],voice_takes:[],font_json:{}}];
let scenes=structuredClone(originals),requests=[],failVoice=false,cancelled=false,jobMode='success';
globalThis.fetch=async(path,init={})=>{const body=init.body?JSON.parse(init.body):undefined;requests.push({path,body});let result;const id=path.match(/\/scenes\/([^/]+)/)?.[1],s=scenes.find(s=>s.id===id);
 if(path.endsWith('/voice-takes/service')){if(failVoice)return {ok:false,status:503,json:async()=>({detail:'Local engine offline'})};result={id:'take-'+id,accepted:true,measured_duration_ms:2000};s.voice_takes=[result];}
 else if(path.endsWith('/generate-image'))result={id:'generated',type:'image'};
 else if(path.endsWith('/auto-captions')){s.font_json.caption_segments=[{id:'aligned',text:s.spoken_text,start_ms:250,end_ms:2250}];result=s;}
 else if(path.endsWith('/select'))result={};
 else if(path.endsWith('/shots')){s.shots=[{id:'shot-'+id,asset_id:body.asset_id,motion_json:body.motion,asset:assets[0]}];result=s.shots[0];}
 else if(path.endsWith('/render'))result={job_id:'render-'+id};
 else if(path.endsWith('/cancel')){cancelled=true;result={};}
 else if(path.includes('/jobs/'))result={status:cancelled?'cancelled':jobMode==='waiting'?'running':'succeeded',progress:100};
 else if(s){if(init.method==='PATCH'){Object.assign(s,body);if(body.font)s.font_json={...s.font_json,...body.font};}result=s;}
 else throw Error('Unexpected endpoint '+path);
 return {ok:true,json:async()=>structuredClone(result)};
};
assert.equal(sceneLanguage('أهلا','auto'),'ar');assert.equal(sceneLanguage('Hello','auto'),'en');assert.equal(visualPrompt(originals[0]),'a mountain');
const estimated=estimatedCaptionSegments('One two three four five six seven eight',3000,250);assert.equal(estimated.length,2);assert.equal(estimated[0].start_ms,250);assert.equal(estimated[1].end_ms,3000);
assert.throws(()=>validateSceneSetup({...options,voiceEngine:'paid'},originals,[{id:'paid',name:'elevenlabs',capability:'speech'}],assets),/Confirm paid ElevenLabs narration/);
validateSceneSetup({...options,voiceEngine:'paid',paidNarrationConfirmed:true},originals,[{id:'paid',name:'elevenlabs',capability:'speech'}],assets);
assert.throws(()=>validateSceneSetup({...options,voiceEngine:'kokoro'},originals,[{id:'kokoro',name:'kokoro',capability:'speech'}],assets),/does not support Arabic/);
validateSceneSetup(options,originals,providers,assets);
let result=await setupImportedScenes(originals,options,assets,()=>{},()=>false);
assert.equal(result.notes.length,0);assert.equal(result.scenes.length,2);assert(result.scenes.every(s=>s.shots.length===1&&s.font_json.caption_segments.length));
assert.equal(requests.find(r=>r.path.includes('two/voice-takes/service')).body.language,'ar');assert.equal(requests.find(r=>r.path.includes('one/voice-takes/service')).body.language,'en');
assert.equal(requests.filter(r=>r.path.endsWith('/render')).length,2);
assert(requests.every(r=>!r.path.includes('generate-image')&&!r.path.includes('auto-captions')));
scenes=structuredClone(originals);requests=[];failVoice=true;result=await setupImportedScenes(originals,{...options,render:false},assets,()=>{},()=>false);
assert(result.notes.some(n=>n.includes('Local engine offline')));assert(result.scenes.every(s=>s.shots.length===1&&s.font_json.caption_segments.length));assert.equal(requests.filter(r=>r.path.endsWith('/voice-takes/service')).length,2);assert(!requests.some(r=>r.path.includes('local-tts')));
scenes=structuredClone(originals);requests=[];let stopped=false;result=await setupImportedScenes(originals,options,assets,message=>{if(message.includes('scene timing'))stopped=true;},()=>stopped);
assert(result.notes.some(n=>n.includes('Stopped')));assert(!requests.some(r=>r.path.endsWith('/shots')||r.path.includes('voice-takes/service')));assert.equal(result.scenes.length,2);
scenes=structuredClone(originals);requests=[];failVoice=false;stopped=false;
const localOptions={...options,pictures:'local',imageProviderId:'images',captions:'local',render:false};
validateSceneSetup(localOptions,originals,[...providers,{id:'images',name:'local_sd',capability:'image'}],assets);
result=await setupImportedScenes(originals,localOptions,assets,()=>{},()=>false);
assert.equal(result.notes.length,0);assert.equal(requests.filter(r=>r.path.endsWith('/generate-image')).length,2);assert(requests.filter(r=>r.path.endsWith('/generate-image')).every(r=>r.body.provider_id==='images'));
assert(requests.filter(r=>r.path.endsWith('/auto-captions')).every(r=>r.body.provider==='local'));assert(result.scenes.every(s=>s.font_json.caption_segments[0].id==='aligned'));
scenes=structuredClone(originals);requests=[];jobMode='waiting';cancelled=false;stopped=false;
result=await setupImportedScenes(originals,options,assets,message=>{if(message.endsWith('· render'))stopped=true;},()=>stopped);
assert(cancelled);assert(result.notes.some(n=>n.includes('Render cancelled')));assert.equal(result.scenes.length,2);
console.log('PASS scene setup selection, Arabic/English voices, estimated captions, render contract, failure retention, no cloud fallback and stopping');
