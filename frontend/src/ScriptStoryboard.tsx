import {useEffect,useState} from 'react';
import {api,type Asset,type Project} from './api';
import {CaptionPreview} from './CaptionsPro';
import catalog from './captionStyles.json';
import {CAMERA_MOTIONS} from './cameraMotions';
import {type SceneSetupOptions} from './scriptSceneSetup';

export function ScriptStoryboard({scenes,options,prepare,assets,project}:{scenes:any[];options:SceneSetupOptions;prepare:boolean;assets:Asset[];project:Project}){
 const [index,setIndex]=useState(0);
 useEffect(()=>setIndex(i=>Math.min(i,Math.max(0,scenes.length-1))),[scenes.length]);
 if(!scenes.length)return null;
 const scene=scenes[index],picture=prepare&&options.pictures==='pool'?assets.find(a=>a.id===options.mediaIds[index%options.mediaIds.length]):undefined;
 const style=prepare?catalog.styles.find(s=>s.name===options.style)?.values:undefined;
 const font={...project.default_font_json,...style,captions_enabled:true,caption_segments:[],typewriter:null};
 return <section className="script-storyboard" aria-label="Script visual storyboard">
  <h3>Review before adding scenes</h3><p className="hint">Picture and caption layout sample. Movement, generated pictures and voice are checked after setup and rendering.</p>
  <div className="storyboard-scene-tabs" role="group" aria-label="Review a script scene">{scenes.map((s,i)=><button className="btn" key={i} aria-pressed={index===i} aria-label={`Review script scene ${i+1}`} onClick={()=>setIndex(i)}>{i+1}. {s.title}</button>)}</div>
  <div className="storyboard-frame" style={{aspectRatio:project.aspect.replace(':','/'),width:`min(100%,${340*project.width/project.height}px)`}} role="img" aria-label={`Scene ${index+1} layout sample: ${scene.title}`}>
   {picture?<img src={api.assetThumbUrl(picture.id,720)} alt={picture.original_filename}/>:<div className="storyboard-no-picture">{prepare&&options.pictures==='local'?'Picture will be generated on Add scenes':'Add a picture in the scene editor'}<strong>{scene.title}</strong></div>}
   <CaptionPreview font={font as any} text={scene.subtitle_text||scene.spoken_text||''} projectW={project.width} projectH={project.height}/>
  </div>
  <p className="hint">{prepare?CAMERA_MOTIONS.find(([id])=>id===options.motion)?.[1]||options.motion:'Project defaults'} · {prepare?`${options.seconds}s before narration sets timing`:'Text-only scene'}{prepare&&options.voiceEngine!=='none'?' · Narration generated on Add scenes':''}</p>
  <button className="btn" onClick={()=>{const field=document.querySelector<HTMLTextAreaElement>(`[aria-label="Preview scene ${index+1} narration"]`);field?.scrollIntoView({block:'center',behavior:'smooth'});field?.focus();}}>Edit this narration</button>
 </section>;
}
