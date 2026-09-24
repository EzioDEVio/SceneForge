import {askConfirm,askText} from "./dialogs";
import React, {useEffect, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {ArrowLeft, ArrowRight, Film, Plus, GripVertical, Play, Pause, Square, SkipBack, SkipForward, Volume2, Type, Maximize2, X, ChevronLeft, ChevronRight, Trash2, Scissors, Undo2, Redo2, Upload, StepBack, StepForward, Clapperboard, ArrowLeftRight, ChevronUp, ChevronDown, Captions} from 'lucide-react';
import {api, Project, Scene} from './api';
import {ASSET_DRAG_TYPE, DraggedAsset, collectDroppedFiles, isMediaDrag} from './timelineDrop';

export const TRANSITIONS = [
  ['cut','Cut'], ['dissolve','Dissolve'], ['fade_through_black','Fade through black'],
  ['fade_white','Fade through white'], ['slide','Slide left'], ['slide_right','Slide right'],
  ['wipe_left','Wipe left'], ['wipe_right','Wipe right'], ['circle_open','Circle reveal'],
];
export function sceneDuration(scene:Scene) {
  if(scene.timing_mode==='fixed'&&scene.requested_duration_ms)return scene.requested_duration_ms;
  const take=scene.voice_takes.find(t=>t.accepted);
  if(take?.measured_duration_ms)return take.measured_duration_ms+(scene.lead_ms??250)+(scene.trail_ms??400);
  return scene.measured_duration_ms||scene.requested_duration_ms||4000;
}
export function sequenceClips(scenes:Scene[]) {
  let cursor=0;
  return scenes.map((scene,i)=>{
    const duration=sceneDuration(scene), previous=scenes[i-1];
    const overlap=previous?.shots.length&&scene.shots.length&&scene.transition_in_json.type!=='cut'
      ? Math.min(scene.transition_in_json.duration_ms||0,sceneDuration(previous)/2,duration/2):0;
    const start=cursor-overlap;cursor=start+duration;
    return {scene,start,duration,overlap,end:cursor};
  });
}
export const timecode=(ms:number,fps=30)=>{
  const f=Math.max(0,Math.floor(ms/1000*fps));
  return [Math.floor(f/fps/3600),Math.floor(f/fps/60)%60,Math.floor(f/fps)%60,f%fps].map(n=>String(n).padStart(2,'0')).join(':');
};
export function ProjectTimeline({project,selectedId,disabled,onDuration,onRender,onSelect,onAdd,onReorder,onUpdate,exportAsset,exportScenes,onDelete,onAudio,onRemoveAudio,onUndo,onRedo,canUndo,canRedo,onSplit,onDropFiles,onDropAssets,notice}:{
  notice?:string;onDropFiles?:(sceneId:string|null,files:File[])=>void;onDropAssets?:(sceneId:string|null,assets:DraggedAsset[])=>void;
  onDuration?:(id:string,ms:number)=>void;onRender?:()=>void;onDelete?:()=>void;onAudio?:()=>void;onRemoveAudio?:()=>void;onUndo?:()=>void;onRedo?:()=>void;canUndo?:boolean;canRedo?:boolean;onSplit?:(at:number,baked?:boolean)=>void;
  exportScenes?:Scene[];exportAsset?:string|null;project:Project;selectedId:string;disabled:boolean;onSelect:(id:string)=>void;onAdd:()=>void;
  onReorder:(ids:string[])=>Promise<unknown>;onUpdate:(id:string,patch:any)=>Promise<unknown>;
}) {
  const [minimized,setMinimized]=useState(false);
  const [scale,setScale]=useState(55),[height,setHeight]=useState(Math.min(330,window.innerHeight*.37));
  const [drag,setDrag]=useState(''),[position,setPosition]=useState(0);
  const [monitor,setMonitor]=useState(false),[playing,setPlaying]=useState(false),[mediaError,setMediaError]=useState('');
  const player=useRef<HTMLVideoElement>(null),scroll=useRef<HTMLDivElement>(null);
  const rulerSelection=useRef<string|null>(null);
  const scenes=project.scenes,selected=scenes.find(s=>s.id===selectedId),index=scenes.findIndex(s=>s.id===selectedId);
  const [trim,setTrim]=useState<{id:string;x:number;original:number;ms:number}|null>(null);
  const authored=sequenceClips(scenes.map(s=>trim?.id===s.id?{...s,timing_mode:'fixed',requested_duration_ms:trim.ms}:s)),exported=sequenceClips((monitor&&exportScenes?.length?exportScenes:scenes).filter(s=>s.shots.length));
  // Export playback uses the export's time axis; draft layout retains every empty part.
  const clips=monitor?exported:authored;
  const length=clips[clips.length-1]?.end||0,exportLength=exported[exported.length-1]?.end||0;
  const selectedClip=clips.find(c=>c.scene.id===selectedId);
  const firstPlayable=exported[0]?.scene.id===selectedId;
  const staleExport=!!exportAsset&&!!exportScenes&&JSON.stringify(scenes.map(s=>[s.id,s.revision]))!==JSON.stringify(exportScenes.map(s=>[s.id,s.revision]));
  const [toolMessage,setToolMessage]=useState('');
  const needsBake=!!selected&&(selected.shots.length!==1||selected.voice_takes.some(t=>t.accepted)||!!selected.subtitle_text||!!selected.font_json.layers?.length||(selected.shots[0]?.motion_json.type||'static')!=='static'||(selected.shots[0]?.asset?.type==='video'&&(selected.shots[0].asset.duration_ms||0)<(selected.shots[0].source_in_ms||0)+sceneDuration(selected)));
  const canSplit=!!selected?.shots.length&&!monitor;
  async function split(){
    if(!selected||!selectedClip)return;
    if(needsBake&&(!selected.rendered_asset_id||selected.is_stale)){setToolMessage('Render this scene first. Its current motion, captions and sound must be included in the cut.');return;}
    const local=position-selectedClip.start;
    const suggested=local>0&&local<selectedClip.duration?local:selectedClip.duration/2;
    const value=await askText(`Split “${selected.title}” at seconds from its start (length ${(selectedClip.duration/1000).toFixed(2)}s):`,(suggested/1000).toFixed(3));
    if(value===null)return;
    const seconds=Number(value),frameMs=1000/project.fps,at=Math.round(Math.round(seconds*project.fps)*frameMs);
    if(!value.trim()||!Number.isFinite(seconds)||at<Math.round(frameMs)||at>selectedClip.duration-Math.round(frameMs)){setToolMessage('Choose a cut at least one frame from either end.');return;}
    if(needsBake&&!await askConfirm('Split the rendered scene? Motion, text and sound will be baked into the two clips and cannot be edited separately afterward. Original media files remain on disk. This split cannot be undone.'))return;
    setToolMessage('');onSplit?.(at,needsBake);
  }

  useEffect(()=>{setMonitor(false);setPlaying(false);setToolMessage('');},[scenes.length]);
  useEffect(()=>{const clip=authored.find(c=>c.scene.id===selectedId);if(clip&&scroll.current){const left=clip.start/1000*scale,right=clip.end/1000*scale,view=scroll.current;if(left<view.scrollLeft||right>view.scrollLeft+view.clientWidth)view.scrollLeft=Math.max(0,left-60);}},[selectedId]);
  const host=document.getElementById('sequence-viewer');
  useEffect(()=>{if(rulerSelection.current===selectedId){rulerSelection.current=null;return;}if(!monitor&&selectedClip)setPosition(selectedClip.start);},[selectedId,monitor]);
  useEffect(()=>{if(disabled&&playing){player.current?.pause();setPlaying(false);}},[disabled]);
  useEffect(()=>{setPosition(p=>Math.min(p,length));},[length]);
  useEffect(()=>{setMonitor(false);setPlaying(false);},[project.id]);
  useEffect(()=>{if(exportAsset){setMonitor(true);setPosition(0);setMediaError('');}},[exportAsset]);
  useEffect(()=>{const resize=()=>setHeight(h=>Math.min(h,Math.max(250,window.innerHeight*.4)));window.addEventListener('resize',resize);return()=>window.removeEventListener('resize',resize);},[]);
  function seek(ms:number,select=false) {
    const limit=monitor&&Number.isFinite(player.current?.duration)?player.current!.duration*1000:length;
    const value=Math.max(0,Math.min(limit,ms));setPosition(value);
    if(monitor&&player.current){player.current.pause();player.current.currentTime=value/1000;}
    if(!monitor){const clip=[...clips].reverse().find(c=>value>=c.start);if(clip)requestAnimationFrame(()=>window.dispatchEvent(new CustomEvent('sceneforge-seek',{detail:{sceneId:clip.scene.id,timeMs:value-clip.start}})));}
    if(select&&!monitor){const c=[...clips].reverse().find(c=>value>=c.start);if(c&&c.scene.id!==selectedId){rulerSelection.current=c.scene.id;onSelect(c.scene.id);}}
  }
  const [dropTarget,setDropTarget]=useState('');
  // Drop/import results show briefly, then clear so the ruler stays usable.
  const [shownNotice,setShownNotice]=useState('');
  useEffect(()=>{setShownNotice(notice||'');if(!notice)return;const t=setTimeout(()=>setShownNotice(''),7000);return()=>clearTimeout(t);},[notice]);
  useEffect(()=>{const clear=()=>setDropTarget('');window.addEventListener('dragend',clear);window.addEventListener('drop',clear);return()=>{window.removeEventListener('dragend',clear);window.removeEventListener('drop',clear);};},[]);
  function dragOverMedia(e:React.DragEvent,key:string):boolean{
    if(!isMediaDrag(e)||disabled)return false;
    e.preventDefault();e.stopPropagation();e.dataTransfer.dropEffect='copy';
    if(dropTarget!==key)setDropTarget(key);
    return true;
  }
  function dropMedia(e:React.DragEvent,sceneId:string|null):boolean{
    const kind=isMediaDrag(e);
    if(!kind)return false;
    e.preventDefault();e.stopPropagation();setDropTarget('');
    if(disabled)return true;
    if(kind==='assets'){try{onDropAssets?.(sceneId,JSON.parse(e.dataTransfer.getData(ASSET_DRAG_TYPE)));}catch{/* malformed payload */}}
    else{const dt=e.dataTransfer;void collectDroppedFiles(dt).then(files=>files.length&&onDropFiles?.(sceneId,files));}
    return true;
  }
  function togglePlay() {
    if(disabled||!scenes.some(s=>s.shots.length))return;
    if(!exportAsset||staleExport){onRender?.();return;}
    if(!monitor){setMonitor(true);setMediaError('');}
    else if(player.current?.paused){if(player.current.ended)player.current.currentTime=0;void player.current.play().catch(()=>setMediaError('Press Play in the video controls to begin playback.'));}
    else player.current?.pause();
  }
  // Editor shortcuts. Ignored while typing, while a dialog is open, and for
  // Space on a focused button (the browser already activates the button).
  const shortcut=useRef<(e:KeyboardEvent)=>void>(()=>{});
  shortcut.current=(e:KeyboardEvent)=>{
    const t=e.target as HTMLElement|null;
    if(e.defaultPrevented||e.altKey||document.querySelector('[role="dialog"]'))return;
    if(t&&(t.isContentEditable||/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)))return;
    const mod=e.ctrlKey||e.metaKey;const frame=1000/project.fps;
    if(mod&&e.key.toLowerCase()==='z'){if(e.shiftKey){if(canRedo&&!disabled){e.preventDefault();onRedo?.();}}else if(canUndo&&!disabled){e.preventDefault();onUndo?.();}return;}
    if(mod&&e.key.toLowerCase()==='y'){if(canRedo&&!disabled){e.preventDefault();onRedo?.();}return;}
    if(mod)return;
    if(e.key===' '&&t?.tagName!=='BUTTON'){e.preventDefault();togglePlay();}
    else if(e.key==='ArrowLeft'){e.preventDefault();if(e.shiftKey)seek([...clips].reverse().find(c=>c.start<position-1)?.start||0,true);else seek(position-frame,true);}
    else if(e.key==='ArrowRight'){e.preventDefault();if(e.shiftKey)seek(clips.find(c=>c.start>position+1)?.start??length,true);else seek(position+frame,true);}
    else if(e.key==='Home'){e.preventDefault();seek(0,true);}
    else if(e.key==='End'){e.preventDefault();seek(length,true);}
    else if((e.key==='Delete'||e.key==='Backspace')&&selected&&!disabled){e.preventDefault();onDelete?.();}
  };
  useEffect(()=>{const h=(e:KeyboardEvent)=>shortcut.current(e);window.addEventListener('keydown',h);return()=>window.removeEventListener('keydown',h);},[]);
  function drop(target:string) {
    if(disabled||!drag||drag===target)return;
    const ids=scenes.map(s=>s.id),from=ids.indexOf(drag),to=ids.indexOf(target);
    if(from<0||to<0)return;
    ids.splice(from,1);ids.splice(to,0,drag);setDrag('');void onReorder(ids);
  }
  function move(dir:number) {
    if(index<0||index+dir<0||index+dir>=scenes.length)return;
    const ids=scenes.map(s=>s.id);[ids[index],ids[index+dir]]=[ids[index+dir],ids[index]];void onReorder(ids);
  }
  function resize(e:React.PointerEvent<HTMLDivElement>) {
    e.currentTarget.setPointerCapture(e.pointerId);
    e.currentTarget.dataset.origin=String(e.clientY);e.currentTarget.dataset.height=String(height);
  }
  function fit(){setScale(Math.max(.5,Math.min(150,((scroll.current?.clientWidth||800)-40)/Math.max(1,length/1000))));}
  const step=scale>=100?1:scale>=40?2:scale>=16?5:scale>=4?15:60;
  const extent=Math.max(length/1000+3,16);
  return <section className={`sequence-dock ${minimized?'minimized':''}`} aria-label="Video timeline" style={{height:minimized?90:height}}>
    <div className="dock-resizer" role="separator" aria-label="Resize timeline" aria-orientation="horizontal" aria-valuenow={height} aria-valuemin={250} aria-valuemax={Math.max(250,Math.round(window.innerHeight*.6))} tabIndex={0}
      onPointerDown={resize} onPointerMove={e=>{if(e.currentTarget.hasPointerCapture(e.pointerId))setHeight(Math.max(250,Math.min(window.innerHeight*.6,Number(e.currentTarget.dataset.height)+Number(e.currentTarget.dataset.origin)-e.clientY)));}}
      onKeyDown={e=>{if(e.key==='ArrowUp'||e.key==='ArrowDown'){e.preventDefault();setHeight(h=>Math.max(250,Math.min(window.innerHeight*.6,h+(e.key==='ArrowUp'?20:-20))));}}}><span/></div>
    <header className="sequence-toolbar">
      <div className="sequence-title"><Film size={16}/><strong>Timeline 01</strong><span>{project.fps} fps</span></div>
      <div className="timeline-actions"><button aria-label="Undo timeline edit" title={canUndo?"Undo last transition/order edit":"No transition/order edits to undo in this session"} disabled={disabled||!canUndo} onClick={onUndo}><Undo2 size={15}/>Undo</button><button aria-label="Redo timeline edit" title={canRedo?"Redo timeline edit":"Nothing to redo — undo a timeline edit first"} disabled={disabled||!canRedo} onClick={onRedo}><Redo2 size={15}/>Redo</button><button aria-label="Split at playhead" title="Split selected scene: choose cut time; render complex scenes first" disabled={disabled||!canSplit} onClick={split}><Scissors size={15}/></button><button aria-label="Delete selected scene" title="Delete selected scene" disabled={disabled||!selected} onClick={onDelete}><Trash2 size={15}/></button><button aria-label="Import timeline audio" title="Import audio into selected scene's A1 lane" disabled={disabled||!selected} onClick={onAudio}><Upload size={15}/><Volume2 size={14}/></button><button aria-label="Remove selected scene audio" title="Remove accepted audio from selected scene" disabled={disabled||!selected?.voice_takes.some(t=>t.accepted)} onClick={onRemoveAudio}><Volume2 size={14}/><X size={12}/></button></div>
      <div className="sequence-transport" role="group" aria-label="Playback">
        <button title="Go to start (Home)" aria-label="Go to timeline start" onClick={()=>seek(0,true)}><SkipBack size={16}/></button>
        <button title="Previous scene" aria-label="Previous scene" disabled={disabled||!clips.length||position<=0} onClick={()=>seek([...clips].reverse().find(c=>c.start<position-1)?.start||0,true)}><StepBack size={16}/></button>
        <button title="Previous frame (←)" aria-label="Previous frame" disabled={disabled||position<=0} onClick={()=>seek(position-1000/project.fps,true)}><ChevronLeft size={16}/></button>
        <button className="transport-play" title={playing?'Pause (Space)':'Play full video (Space); renders first if needed'} aria-label={playing?'Pause movie':'Play movie'} disabled={!scenes.some(s=>s.shots.length)||disabled} onClick={togglePlay}>{playing?<Pause size={16}/>:<Play size={16}/>}</button>
        <button aria-label="Stop full video" title="Stop and return to start" disabled={!monitor} onClick={()=>seek(0)}><Square size={15}/></button>
        <button title="Next frame (→)" aria-label="Next frame" disabled={disabled||position>=length} onClick={()=>seek(position+1000/project.fps,true)}><ChevronRight size={16}/></button>
        <button title="Next scene" aria-label="Next scene" disabled={disabled||!clips.some(c=>c.start>position+1)} onClick={()=>seek(clips.find(c=>c.start>position+1)?.start||length,true)}><StepForward size={16}/></button>
        <button title="Go to end (End)" aria-label="Go to timeline end" onClick={()=>seek(length,true)}><SkipForward size={16}/></button>
        <span className="transport-timecode" aria-label="Timeline timecode">{timecode(position,project.fps)}</span>
      </div>
      <div className="sequence-tools"><button className="render-sequence" title="Render every scene and assemble the full video" disabled={disabled||!scenes.some(s=>s.shots.length)} onClick={onRender}><Clapperboard size={14}/> Render full video</button><button aria-label="Minimize or restore timeline" title={minimized?'Restore timeline':'Minimize timeline'} onClick={()=>setMinimized(!minimized)}>{minimized?<ChevronUp size={15}/>:<ChevronDown size={15}/>}</button><button aria-label="Maximize timeline" title="Maximize timeline" onClick={()=>{setMinimized(false);setHeight(window.innerHeight*.6);}}><Maximize2 size={13}/></button><button aria-label="Fit timeline" title="Fit timeline to width" onClick={fit}><ArrowLeftRight size={15}/></button><label>Zoom<input aria-label="Timeline zoom" type="range" min={.5} max={150} step={.5} value={scale} onChange={e=>setScale(Number(e.target.value))}/></label><button disabled={disabled} onClick={onAdd}><Plus size={15}/> Add part</button></div>
    </header>
    <div className="sequence-editbar">
      <span className="tool-feedback" aria-live="polite">{toolMessage||shownNotice}</span><span className="selection-label">{selected?.title||'Select a part'}</span>
      <button aria-label="Move timeline part earlier" title="Move part earlier" disabled={disabled||index<=0} onClick={()=>move(-1)}><ArrowLeft size={14}/>Earlier</button>
      <button aria-label="Move timeline part later" title="Move part later" disabled={disabled||index<0||index>=scenes.length-1} onClick={()=>move(1)}><ArrowRight size={14}/>Later</button>
      <label>Transition<select aria-label="Incoming transition" disabled={disabled||!selected?.shots.length||firstPlayable} value={selected?.transition_in_json.type||'cut'} onChange={e=>selected&&void onUpdate(selected.id,{transition_in:{type:e.target.value,duration_ms:e.target.value==='cut'?0:(selected.transition_in_json.duration_ms||500)}})}>{TRANSITIONS.map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      <label>Duration<input aria-label="Transition seconds" type="number" min={0} max={30} step={.1} key={`${selectedId}-${selected?.transition_in_json.duration_ms}`} defaultValue={(selected?.transition_in_json.duration_ms||0)/1000} disabled={disabled||!selected?.shots.length||firstPlayable||selected.transition_in_json.type==='cut'} onBlur={e=>{if(selected&&e.target.validity.valid&&e.target.value!=='')void onUpdate(selected.id,{transition_in:{...selected.transition_in_json,duration_ms:Math.round(Number(e.target.value)*1000)}});}} onKeyDown={e=>{if(e.key==='Enter')e.currentTarget.blur();}}/>s</label><button aria-label="Remove transition" disabled={disabled||!selected||selected.transition_in_json.type==='cut'} onClick={()=>selected&&void onUpdate(selected.id,{transition_in:{type:'cut',duration_ms:0}})}><X size={12}/>Remove</button><span className="overlap-info" title="Limited to half the duration of either neighboring scene">Overlap {((selectedClip?.overlap||0)/1000).toFixed(2)}s</span>
      <button className="movie-toggle" disabled={!exportAsset} onClick={()=>{setMonitor(!monitor);setPlaying(false);setMediaError('');}}>{monitor?'Return to editing':'Preview last export'}</button>
    </div>
    <div className="sequence-tracks">
      <aside className="track-headers" aria-label="Track headers"><div className="track-ruler-label">TRACKS</div><div className="track-video-label"><b>V1</b><Film size={15}/><span>Picture<small>{scenes.length} parts</small></span></div><div className="track-audio-label"><b>A1</b><Volume2 size={15}/><span>Narration<small>Accepted takes</small></span></div><div className="track-text-label"><b>T1</b><Type size={15}/><span>Text<small>Captions & titles</small></span></div></aside>
      <div className="sequence-scroll" ref={scroll}>
        <div className="sequence-content" style={{width:Math.max(650,extent*scale)}}>
          <div className="sequence-ruler" role="slider" aria-label="Timeline playhead" aria-valuemin={0} aria-valuemax={Math.round(length)} aria-valuenow={Math.round(position)} tabIndex={0} onKeyDown={e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();seek(position+(e.key==='ArrowLeft'?-1:1)*1000/project.fps,true);}}}
            onPointerDown={e=>{e.currentTarget.setPointerCapture(e.pointerId);seek((e.clientX-e.currentTarget.getBoundingClientRect().left)/scale*1000,true);}}
            onPointerMove={e=>{if(e.currentTarget.hasPointerCapture(e.pointerId))seek((e.clientX-e.currentTarget.getBoundingClientRect().left)/scale*1000,true);}}>
            {Array.from({length:Math.min(1000,Math.ceil(extent/step))},(_,i)=><span key={i} style={{left:i*step*scale}}>{timecode(i*step*1000,project.fps).slice(0,8)}</span>)}
          </div>
          <div className="sequence-playhead" style={{left:position/1000*scale}}><span/></div>
          <div className={`picture-track ${dropTarget==="end"?"drop-target":""}`} aria-label="Scene track" onDragOver={e=>{dragOverMedia(e,"end");}} onDragLeave={e=>{if(e.currentTarget===e.target)setDropTarget("");}} onDrop={e=>{dropMedia(e,null);}}>
            {clips.map(({scene:s,start,duration,overlap})=><React.Fragment key={s.id}>
              <button draggable={!disabled&&!monitor} disabled={disabled} onDragStart={()=>setDrag(s.id)} onDragEnd={()=>setDrag('')} onDragOver={e=>{if(!dragOverMedia(e,'v:'+s.id))e.preventDefault();}} onDragLeave={()=>setDropTarget('')} onDrop={e=>{if(!dropMedia(e,s.id))drop(s.id);}} className={`picture-clip ${s.id===selectedId?'selected':''} ${s.shots.length?'':'placeholder'} ${dropTarget==='v:'+s.id?'drop-target':''}`} style={{left:start/1000*scale,width:Math.max(4,duration/1000*scale-2)}} aria-label={`Storyboard scene ${scenes.indexOf(s)+1}`} aria-current={s.id===selectedId?'true':undefined} onClick={()=>{onSelect(s.id);seek(start);}} title={`${s.title} · ${(duration/1000).toFixed(1)}s${!s.shots.length?' · Add media':''}`}>
                <div className="clip-label"><GripVertical size={12}/><strong>{s.title}</strong><small>{(duration/1000).toFixed(1)}s</small></div>
                {s.shots[0]?.asset&&s.shots[0].asset.type!=='audio'?<div className="filmstrip" data-kind={s.shots[0].asset.type} style={{backgroundImage:`url("${api.assetThumbUrl(s.shots[0].asset_id,160)}")`}}/>:s.shots.length?<div className="clip-placeholder"><Film size={22}/>Video source</div>:<div className="clip-placeholder"><Plus size={18}/>Add media</div>}
              </button>
              {!monitor&&s.shots.length>0&&s.shots.every(shot=>shot.asset?.type==='image')&&<div role="slider" tabIndex={disabled?-1:0} aria-label={`Resize ${s.title} duration`} aria-valuemin={0.5} aria-valuemax={3600} aria-valuenow={duration/1000} className="clip-duration-handle" style={{left:(start+duration)/1000*scale-9}} title="Drag to change duration; arrow keys adjust 0.1s"
                onPointerDown={e=>{if(disabled)return;e.preventDefault();e.stopPropagation();e.currentTarget.setPointerCapture(e.pointerId);setTrim({id:s.id,x:e.clientX,original:duration,ms:duration});}}
                onPointerMove={e=>{if(trim?.id!==s.id||!e.currentTarget.hasPointerCapture(e.pointerId))return;const ms=Math.max(500,Math.min(3600000,Math.round((trim.original+(e.clientX-trim.x)/scale*1000)/100)*100));setTrim({...trim,ms});}}
                onPointerUp={e=>{if(!trim||trim.id!==s.id)return;e.currentTarget.releasePointerCapture(e.pointerId);const ms=trim.ms;setTrim(null);if(ms!==trim.original)onDuration?.(s.id,ms);}}
                onPointerCancel={()=>setTrim(null)} onKeyDown={e=>{if(!disabled&&(e.key==='ArrowLeft'||e.key==='ArrowRight')){e.preventDefault();onDuration?.(s.id,Math.max(500,Math.min(3600000,duration+(e.key==='ArrowRight'?100:-100))));}}}/>} 
              {overlap>0&&<button disabled={disabled} className={`clip-transition ${selectedId===s.id?'selected':''}`} style={{left:start/1000*scale,width:Math.max(20,overlap/1000*scale)}} aria-label={`Edit ${s.title} transition`} title={`${TRANSITIONS.find(t=>t[0]===s.transition_in_json.type)?.[1]} · ${(overlap/1000).toFixed(2)}s (effective overlap)`} onClick={()=>{onSelect(s.id);seek(start);}}><span>⋈</span></button>}
            </React.Fragment>)}
          </div>
          <div className="narration-track" aria-label="Narration track">{clips.map(({scene:s,start,duration})=>{const take=s.voice_takes.find(t=>t.accepted);return <button key={s.id} onDragOver={e=>{dragOverMedia(e,'a:'+s.id);}} onDragLeave={()=>setDropTarget('')} onDrop={e=>{dropMedia(e,s.id);}} className={`narration-clip ${take?'has-take':''} ${dropTarget==='a:'+s.id?'drop-target':''}`} style={{left:start/1000*scale,width:Math.max(4,duration/1000*scale-2)}} onClick={()=>onSelect(s.id)} title={take?`${take.voice||'Narration'} · ${((take.measured_duration_ms||0)/1000).toFixed(1)}s · drop audio here to replace`:'Drop an audio file here to add sound to this scene'}><Volume2 size={13}/>{take?take.voice||'Narration':dropTarget==='a:'+s.id?'Drop to add audio':'No narration'}</button>})}</div>
          <div className="titles-track" aria-label="Text track">{clips.map(({scene:s,start,duration})=>{const caption=s.font_json.captions_enabled&&s.subtitle_text?s.subtitle_text:'';const layers=s.font_json.layers?.length||0;const summary=[caption&&`Caption: ${caption}`,layers&&`${layers} title${layers>1?'s':''}`].filter(Boolean).join(' · ')||'No captions or titles';return <button key={s.id} className={`title-clip ${caption||layers?'has-title':''}`} style={{left:start/1000*scale,width:Math.max(4,duration/1000*scale-2)}} onClick={()=>onSelect(s.id)} title={summary} aria-label={`${s.title} text: ${summary}`}>{layers>0&&<span className="lane-titles"><Type size={11}/>{layers}</span>}{caption?<span className="lane-caption"><Captions size={12}/>{caption}</span>:layers?null:<span className="lane-empty"><Type size={12}/>No text</span>}</button>})}</div>
        </div>
      </div>
    </div>
    <footer className="sequence-status"><span>{staleExport?'EXPORT OUTDATED · Export again to include your latest changes':monitor?'LAST EXPORT · Export again after edits':'ASSEMBLY · Drag parts to reorder · Drop audio on a scene to add its sound · Drop images or videos on a scene, or after the last one'}</span><span>{scenes.some(s=>!s.shots.length)?'Empty placeholders are skipped on export · ':''}Estimated export {timecode(exportLength,project.fps)}</span></footer>
    {monitor&&exportAsset&&host&&createPortal(<div className="program-monitor"><header><strong>Last exported movie</strong><span>{staleExport?'Outdated — export again for current scenes':'Export again after edits'}</span><button title="Fullscreen movie" onClick={()=>void player.current?.requestFullscreen()}><Maximize2 size={15}/></button><button aria-label="Close movie preview" onClick={()=>{setMonitor(false);setPlaying(false);}}><X size={16}/></button></header><video ref={player} controls autoPlay src={api.assetStreamUrl(exportAsset)} onPlay={()=>setPlaying(true)} onPause={()=>setPlaying(false)} onEnded={()=>setPlaying(false)} onError={()=>setMediaError('The exported movie could not be loaded. Export again and retry.')} onTimeUpdate={e=>setPosition(e.currentTarget.currentTime*1000)}/>{mediaError&&<p role="alert">{mediaError}</p>}</div>,host)}
  </section>;
}
