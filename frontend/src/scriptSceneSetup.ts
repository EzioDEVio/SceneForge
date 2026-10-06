import {api, type Asset, type Scene, type ProviderProfile} from './api';
import {sceneDuration} from './duration';
import captionCatalog from './captionStyles.json';
export type SceneSetupOptions={pictures:'none'|'pool'|'local';mediaIds:string[];imageProviderId:string;voiceEngine:string;voice:string;language:'auto'|'en'|'ar';captions:'keep'|'script'|'local';style:string;motion:string;render:boolean;seconds:number;paidNarrationConfirmed?:boolean};
export const DEFAULT_SCENE_SETUP:SceneSetupOptions={pictures:'none',mediaIds:[],imageProviderId:'',voiceEngine:'none',voice:'',language:'auto',captions:'keep',style:'',motion:'static',render:false,seconds:4};
export function sceneLanguage(text:string,language:SceneSetupOptions['language']){return language==='auto'?(/[\u0600-\u06ff]/.test(text)?'ar':'en'):language;}
export function visualPrompt(scene:{original_text:string;spoken_text:string}){return scene.original_text.match(/(?:Visual|AI Image Prompt|الصورة|اللقطة البصرية)\s*[:：]\s*([^\n]+)/i)?.[1]?.trim()||scene.spoken_text;}
export function estimatedCaptionSegments(text:string,duration:number,start=0){const words=text.replace(/\[\d+(?:,\s*\d+)*\]/g,'').trim().split(/\s+/).filter(Boolean);const chunks=[];for(let i=0;i<words.length;i+=6)chunks.push(words.slice(i,i+6).join(' '));const span=Math.max(100,duration-start);return chunks.map((text,i)=>({id:crypto.randomUUID(),text,start_ms:Math.round(start+span*i/chunks.length),end_ms:Math.round(start+span*(i+1)/chunks.length)}));}
export function validateSceneSetup(options:SceneSetupOptions,scenes:{spoken_text:string}[],providers:ProviderProfile[],assets:Asset[]){
 if(options.pictures==='pool'&&(!options.mediaIds.length||options.mediaIds.some(id=>!assets.some(a=>a.id===id&&['image','video'].includes(a.type)))))throw Error('Choose pictures from this project’s Media Pool.');
 if(options.pictures==='local'&&!providers.some(p=>p.id===options.imageProviderId&&p.capability==='image'&&p.name==='local_sd'))throw Error('Choose a connected local image engine.');
 if(options.voiceEngine!=='none'&&options.voiceEngine!=='diagnostic'){
 const profile=providers.find(p=>p.id===options.voiceEngine&&p.capability==='speech'&&['kokoro','chatterbox','elevenlabs'].includes(p.name));
 if(!profile||profile.configured===false||!options.voice)throw Error('Choose a narration engine and voice.');
 if(profile.name==='elevenlabs'&&!options.paidNarrationConfirmed)throw Error('Confirm paid ElevenLabs narration for this batch before adding scenes.');
 if(profile.name==='kokoro'&&scenes.some(s=>sceneLanguage(s.spoken_text,options.language)==='ar'))throw Error('Kokoro does not support Arabic. Choose Chatterbox, or leave voice generation off for this batch.');
 }
}
/** Runs only explicitly selected steps on freshly imported scenes. Redo restores snapshots. */
export async function setupImportedScenes(scenes:Scene[],options:SceneSetupOptions,assets:Asset[],onProgress:(message:string)=>void,stopped:()=>boolean){
 const notes:string[]=[];
 let jobId:string|null=null;
 const attempt=async(label:string,work:()=>Promise<unknown>)=>{if(stopped())return false;onProgress(label);try{await work();return true;}catch(e:any){notes.push(`${label}: ${e.message||'Step failed'}`);return false;}};
 for(let i=0;i<scenes.length&&!stopped();i++){
  const scene=scenes[i],prefix=`Scene ${i+1}/${scenes.length}`;
  let current=scene;
  await attempt(`${prefix} · scene timing and style`,async()=>{const style=captionCatalog.styles.find(s=>s.name===options.style)?.values;current=await api.updateScene(scene.id,{timing_mode:'fixed',requested_duration_ms:Math.round(options.seconds*1000),...(style?{font:{...style,captions_enabled:true}}:{})});});
  let picture:Asset|undefined;
  if(options.pictures==='pool')picture=assets.find(a=>a.id===options.mediaIds[i%options.mediaIds.length]);
  if(options.pictures==='local')await attempt(`${prefix} · local image`,async()=>{picture=await api.generateImage(scene.id,(scene as any).picture_prompt||visualPrompt(scene),'1024x1024',options.imageProviderId);});
  if(picture)await attempt(`${prefix} · picture and motion`,()=>api.addShot(scene.id,picture!.id,{type:picture!.type==='image'?options.motion:'static'}));
  if(options.voiceEngine!=='none'){
   const ok=await attempt(`${prefix} · narration`,async()=>{const language=sceneLanguage(scene.spoken_text,options.language);const take=options.voiceEngine==='diagnostic'?await api.localTtsTake(scene.id,language):await api.serviceTts(scene.id,options.voiceEngine,options.voice,language,1);await api.selectTake(take.id);current=await api.updateScene(scene.id,{timing_mode:'audio_driven'});});
   if(!ok)notes.push(`${prefix}: narration was not replaced with another engine.`);
  }
  if(!stopped())current=await api.getScene(scene.id);
  if(options.captions==='script')await attempt(`${prefix} · estimated script captions`,async()=>{const take=current.voice_takes.find(t=>t.accepted),lead=take?(current.lead_ms??250):0,tail=take?(current.trail_ms??400):0;const segments=estimatedCaptionSegments(current.subtitle_text||current.spoken_text,Math.max(lead+100,sceneDuration(current)-tail),lead);current=await api.updateScene(scene.id,{font:{captions_enabled:true,caption_segments:segments,transcript:null}});});
  if(options.captions==='local')await attempt(`${prefix} · local timed captions`,async()=>{current=await api.autoCaptions(scene.id,{provider:'local',language:sceneLanguage(scene.spoken_text,options.language)});});
  if(options.render)await attempt(`${prefix} · render`,async()=>{current=await api.getScene(scene.id);if(!current.shots.length)throw Error('Add a picture before rendering this scene.');jobId=(await api.renderPart(scene.id)).job_id;try{while(true){const job=await api.getJob(jobId);if(stopped()){await api.cancelJob(jobId);let cancelled=await api.getJob(jobId);while(['queued','running','cancelling'].includes(cancelled.status)){await new Promise(resolve=>setTimeout(resolve,350));cancelled=await api.getJob(jobId);}throw Error('Render cancelled. The editable scene is kept.');}if(job.status==='succeeded')break;if(['failed','cancelled'].includes(job.status))throw Error(job.error||'Render did not complete.');onProgress(`${prefix} · ${job.stage} ${Math.round(job.progress)}%`);await new Promise(resolve=>setTimeout(resolve,350));}}finally{jobId=null;}});
 }
 if(stopped())notes.push('Stopped after the current step. All imported scenes remain editable.');
 const snapshots=[];for(const scene of scenes)snapshots.push(await api.getScene(scene.id));
 return {scenes:snapshots,notes};
}
