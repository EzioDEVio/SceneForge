import {askConfirm,askText} from "./dialogs";
import React, {useEffect, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {ArrowLeft, ArrowRight, Film, Plus, GripVertical, Play, Pause, Square, SkipBack, SkipForward, Volume2, VolumeX, Type, Maximize2, X, ChevronLeft, ChevronRight, Trash2, Scissors, Undo2, Redo2, Upload, StepBack, StepForward, Clapperboard, ArrowLeftRight, ChevronUp, ChevronDown, Captions, Rows3,ZoomIn,ZoomOut,Maximize,Magnet,Flag,Lock,Unlock} from 'lucide-react';
import {api, Project, ProjectAudioClip, Scene} from './api';
import {sceneDuration,snapTimelineTime} from './duration';
import {NarrationWave} from './NarrationWave';
import {FeatureHelp} from './FeatureHelp';
import {ASSET_DRAG_TYPE, DraggedAsset, collectDroppedFiles, isMediaDrag} from './timelineDrop';
import {AUDIO_TRACKS, AudioTrackId, MARKER_COLORS, TOOL_KEYS, TOOL_LABELS, TimelineAudioClip, TimelineMarker, TimelineSettings, TimelineTool, TrackId, clipTrack, isAudioTrackAudible, markerTime, nextAudioTrack, normalizeTimeline} from './timeline/timeline.types';
import {EditResult, blade as bladeClip, bladeAll, clipEnd, moveClips, neighbours, packRows, rippleDelete, rippleTrim, roll, slide, slip, trackSelectForward, trim as trimClip} from './timeline/editOps';
import {envelopePath} from './GainEnvelope';
import {TIMELINE_SEEK_EVENT, openCleanup} from './cleanupApi';
import {frameMs, intersectsWindow, rafCoalesce, visibleWindow, zoomAround} from './timeline/timeMath';
import {readPreferences} from './preferences';
import {SequencePlayer} from './SequencePlayer';
import {WORKSPACE_EVENT, timelineHeightFor, workspacePreset, type WorkspacePreset} from './workspaces';

export const TRANSITIONS = [
  // A curated set of visibly different families. Directional variants remain
  // renderable for older projects, but are not repeated as separate tiles.
  ['cut','Cut'], ['dissolve','Cross dissolve'], ['fade_through_black','Fade through black'],
  ['fade_white','Flash white'], ['film_burn','Film burn'], ['slide','Slide left'],
  ['slide_up','Slide up'], ['wipe_left','Wipe left'], ['circle_open','Circle reveal'],
  ['circle_close','Circle close'], ['zoom_in','Zoom in'], ['smooth_left','Smooth slide'],
  ['radial','Clock wipe'], ['pixelize','Pixelate'], ['blur','Blur wipe'],
  ['diagonal','Diagonal wipe'], ['squeeze','Horizontal squeeze'], ['fade_grays','Fade through grey'],
  ['wind','Wind'], ['slice','Horizontal slice'], ['slice_vertical','Vertical slice'],
  ['open','Horizontal open'], ['close','Horizontal close'], ['vert_open','Vertical open'],
  ['rect_crop','Rectangle crop'], ['distance','Distance morph'], ['cover_left','Cover left'],
  ['reveal_right','Reveal right'],
];
export function transitionLabel(key:string){return TRANSITIONS.find(([type])=>type===key)?.[1]||key.replace(/_/g,' ').replace(/\b\w/g,(char:string)=>char.toUpperCase());}
export {sceneDuration} from './duration';
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
type TrackLocks=Record<TrackId,boolean>;
const AUDIO_LANE_ROW=32;
const COMPACT_LANE_ROW=16;
const COLLAPSED_LANE_H=18;
// Per-project view state (collapsed lanes, compact tracks). It is how this computer shows the
// timeline, not part of the edit, so it stays in this browser profile instead of the project.
type TrackView={collapsed:Partial<Record<TrackId,boolean>>;compact:boolean};
const trackViewKey=(projectId:string)=>`sceneforge.timelineView.${projectId}`;
function readTrackView(projectId:string):TrackView{try{const v=JSON.parse(localStorage.getItem(trackViewKey(projectId))||'null');return {collapsed:v&&typeof v.collapsed==='object'&&v.collapsed?v.collapsed:{},compact:v?.compact===true};}catch{return {collapsed:{},compact:false};}}
function writeTrackView(projectId:string,view:TrackView){try{localStorage.setItem(trackViewKey(projectId),JSON.stringify(view));}catch{/* storage unavailable: the view still works for this session */}}
// Pre-timeline-v1 builds kept markers and locks in this browser profile. They are read
// once as a fallback and move into the project the next time the timeline is saved.
function legacyTimeline(projectId:string){const read=(k:string)=>{try{return JSON.parse(localStorage.getItem(k)||'null');}catch{return null;}};return {markers:read(`sceneforge.timelineMarkers.${projectId}`),locks:read(`sceneforge.timelineTrackLocks.${projectId}`)};}
const audioTrackLabel=(t:AudioTrackId)=>t==='A3'?'Timeline audio':`Audio ${t.slice(1)}`;
export function ProjectTimeline({onRefresh,project,selectedId,disabled,onDuration,onTrimShot,onRender,onSelect,onAdd,onReorder,onUpdate,exportAsset,exportScenes,onDelete,onDeleteScene,onToggleClipAudio,onAudio,onRemoveAudio,onUndo,onRedo,canUndo,canRedo,onSplit,onDropFiles,onDropAssets,notice,onRemoveSceneAudio,clipboard,onClipboard,onDuplicate,onPaste,multi,onMulti,selectedAudioClipId,onAudioClipSelect,onUpdateAudioClips,onUpdateTimeline,onDetachAudio}:{onRefresh?:()=>Promise<unknown>|void;onDetachAudio?:(sceneId:string,source:'narration'|'shot',placeMs:number,shotId?:string,durationMs?:number)=>void;onUpdateTimeline?:(next:TimelineSettings,options?:{undoable?:boolean;label?:string})=>void;multi?:string[];onMulti?:(id:string,mode:'toggle'|'range'|'clear')=>void;clipboard?:{kind:'scene'|'audio';id:string;label:string}|null;onClipboard?:(c:{kind:'scene'|'audio';id:string;label:string})=>void;onDuplicate?:(id:string)=>void;onPaste?:(targetId:string)=>void;
  onRemoveSceneAudio?:(sceneId:string)=>void;notice?:string;onDropFiles?:(sceneId:string|null,files:File[],insert?:{before?:string;after?:string;audioTrack?:boolean;timeMs?:number;track?:string})=>void;onDropAssets?:(sceneId:string|null,assets:DraggedAsset[],insert?:{before?:string;after?:string;audioTrack?:boolean;timeMs?:number;track?:string})=>void;
  onDuration?:(id:string,ms:number)=>void;onTrimShot?:(sceneId:string,shotId:string,sourceIn:number,sourceOut:number)=>void;onRender?:()=>void;onDelete?:()=>void;onDeleteScene?:(id:string)=>void;onToggleClipAudio?:(shotId:string,audio:Record<string,any>)=>void;onAudio?:()=>void;onRemoveAudio?:()=>void;onUndo?:()=>void;onRedo?:()=>void;canUndo?:boolean;canRedo?:boolean;onSplit?:(at:number,baked?:boolean)=>void;
  exportScenes?:Scene[];exportAsset?:string|null;project:Project;selectedId:string;disabled:boolean;onSelect:(id:string)=>void;onAdd:()=>void;selectedAudioClipId?:string;onAudioClipSelect?:(id:string)=>void;onUpdateAudioClips?:(clips:ProjectAudioClip[])=>void;
  onReorder:(ids:string[])=>Promise<unknown>;onUpdate:(id:string,patch:any)=>Promise<unknown>;
}) {
  const [minimized,setMinimized]=useState(false);
  const [scale,setScale]=useState(55),[height,setHeight]=useState(()=>timelineHeightFor(workspacePreset(readPreferences().workspace)));
  useEffect(()=>{const onWorkspace=(e:Event)=>{const preset=(e as CustomEvent<WorkspacePreset>).detail;if(!preset)return;setMinimized(false);setHeight(Math.min(window.innerHeight*.6,timelineHeightFor(preset)));};window.addEventListener(WORKSPACE_EVENT,onWorkspace);return()=>window.removeEventListener(WORKSPACE_EVENT,onWorkspace);},[]);
  const [trackView,setTrackView]=useState<{projectId:string;view:TrackView}>(()=>({projectId:project.id,view:readTrackView(project.id)}));
  const tv=trackView.projectId===project.id?trackView.view:readTrackView(project.id);
  useEffect(()=>{if(trackView.projectId!==project.id)setTrackView({projectId:project.id,view:readTrackView(project.id)});},[project.id,trackView.projectId]);
  function updateTrackView(next:TrackView){setTrackView({projectId:project.id,view:next});writeTrackView(project.id,next);}
  const isCollapsed=(t:TrackId)=>!!tv.collapsed[t];
  function toggleCollapsed(t:TrackId){const collapsed={...tv.collapsed};if(collapsed[t])delete collapsed[t];else collapsed[t]=true;updateTrackView({...tv,collapsed});}
  const compact=tv.compact;
  const laneRow=compact?COMPACT_LANE_ROW:AUDIO_LANE_ROW;
  const collapsedStyle=(t:TrackId)=>isCollapsed(t)?{height:COLLAPSED_LANE_H,minHeight:COLLAPSED_LANE_H}:undefined;
  const collapseButton=(t:TrackId,label:string)=><button className="track-collapse-button" aria-label={`${isCollapsed(t)?'Expand':'Collapse'} ${t} ${label} track`} aria-expanded={!isCollapsed(t)} title={isCollapsed(t)?`Expand ${t} to full height`:`Collapse ${t} to a thin strip (clips stay selectable)`} onClick={()=>toggleCollapsed(t)}>{isCollapsed(t)?<ChevronRight size={12}/>:<ChevronDown size={12}/>}</button>;
  const [drag,setDrag]=useState(''),[position,setPosition]=useState(0);
  const [snapEnabled,setSnapEnabled]=useState(true);
  const projectAudio:TimelineAudioClip[]=project.finishing_json?.audio_clips||[];
  const storedTimeline=project.finishing_json?.timeline;
  // Local copy so lock/marker changes show immediately, even before the project reloads.
  const [timelineDraft,setTimelineDraft]=useState<{projectId:string;value:TimelineSettings}|null>(null);
  const timeline=React.useMemo(()=>timelineDraft?.projectId===project.id?timelineDraft.value:normalizeTimeline(storedTimeline,projectAudio,storedTimeline?undefined:legacyTimeline(project.id)),[timelineDraft,project.id,storedTimeline,projectAudio]);
  useEffect(()=>{setTimelineDraft(null);},[project.id,storedTimeline]);
  function saveTimeline(next:TimelineSettings,options?:{undoable?:boolean;label?:string}){setTimelineDraft({projectId:project.id,value:next});onUpdateTimeline?.(next,options);}
  const trackLocks=Object.fromEntries([...(['T1','V1','A1','A2'] as const),...AUDIO_TRACKS].map(t=>[t,!!timeline.tracks[t]?.locked])) as TrackLocks;
  function setTrackState(track:TrackId,key:'locked'|'mute'|'solo'){const state={...(timeline.tracks[track]||{})};if(state[key])delete state[key];else state[key]=true;saveTimeline({...timeline,tracks:{...timeline.tracks,[track]:state}},key==='locked'?undefined:{undoable:true,label:`${key} ${track}`});}
  function toggleTrackLock(track:TrackId){setTrackState(track,'locked');}
  const markers=timeline.markers;
  function saveMarkers(next:TimelineMarker[],label:string){saveTimeline({...timeline,markers:[...next].sort((a,b)=>a.time_ms-b.time_ms)},{undoable:true,label});}
  function addAudioTrack(){const t=nextAudioTrack(timeline);if(t)saveTimeline({...timeline,audio_tracks:[...timeline.audio_tracks,t]});}
  function hideAudioTrack(t:AudioTrackId){if(t!=='A3'&&!projectAudio.some(c=>clipTrack(c)===t)){const tracks={...timeline.tracks};delete tracks[t];saveTimeline({...timeline,tracks,audio_tracks:timeline.audio_tracks.filter(x=>x!==t)});}}
  const [tool,setTool]=useState<TimelineTool>('select');
  const [audioSelection,setAudioSelection]=useState<string[]>([]);
  const [view,setView]=useState({left:0,width:1600});
  const viewUpdate=useRef(rafCoalesce<{left:number;width:number}>(v=>setView(v)));
  useEffect(()=>{const sync=()=>{if(scroll.current)setView({left:scroll.current.scrollLeft,width:scroll.current.clientWidth||1600});};sync();window.addEventListener('resize',sync);return()=>window.removeEventListener('resize',sync);},[scale]);
  const [monitor,setMonitor]=useState(false),[playing,setPlaying]=useState(false),[mediaError,setMediaError]=useState('');
  // Live timeline playback (SequencePlayer.tsx): rendered scenes played in sequence, no full export needed.
  const [live,setLive]=useState(false),[liveSeek,setLiveSeek]=useState({ms:0,n:0}),[liveRate,setLiveRate]=useState(1);
  useEffect(()=>{if(monitor)setLive(false);},[monitor]);
  const player=useRef<HTMLVideoElement>(null),scroll=useRef<HTMLDivElement>(null);
  const rulerSelection=useRef<string|null>(null);
  const scenes=project.scenes,selected=scenes.find(s=>s.id===selectedId),index=scenes.findIndex(s=>s.id===selectedId);
  const [trim,setTrim]=useState<{id:string;x:number;original:number;ms:number;shotId?:string;sourceIn?:number;sourceOut?:number;edge?:'in'|'out'}|null>(null);
  const authored=sequenceClips(scenes.map(s=>trim?.id===s.id?{...s,timing_mode:'fixed',requested_duration_ms:trim.ms}:s)),exported=sequenceClips((monitor&&exportScenes?.length?exportScenes:scenes).filter(s=>s.shots.length));
  // Export playback uses the export's time axis; draft layout retains every empty part.
  const clips=monitor?exported:authored;
  const length=clips[clips.length-1]?.end||0,exportLength=exported[exported.length-1]?.end||0;
  const selectedClip=clips.find(c=>c.scene.id===selectedId);
  const activeAudioClip=projectAudio.find(clip=>clip.id===selectedAudioClipId);
  const [focusLane,setFocusLane]=useState<'scene'|'audio'>('scene');
  const [audioDrag,setAudioDrag]=useState<{id:string;clips:TimelineAudioClip[]|null}|null>(null);
  const audioDragRef=useRef<typeof audioDrag>(null);
  const firstPlayable=exported[0]?.scene.id===selectedId;
  const staleExport=!!exportAsset&&!!exportScenes&&JSON.stringify(scenes.map(s=>[s.id,s.revision]))!==JSON.stringify(exportScenes.map(s=>[s.id,s.revision]));
  const [toolMessage,setToolMessage]=useState('');
  const toolMessageTimer=useRef<ReturnType<typeof setTimeout>|null>(null);
  function showToolMessage(message:string){
    setToolMessage(message);
    if(toolMessageTimer.current)clearTimeout(toolMessageTimer.current);
    toolMessageTimer.current=setTimeout(()=>{setToolMessage('');toolMessageTimer.current=null;},3500);
  }
  useEffect(()=>()=>{if(toolMessageTimer.current)clearTimeout(toolMessageTimer.current);},[]);
  const sourceSpeed=Number(selected?.shots[0]?.speed_json?.speed||1);
  const needsBake=!!selected&&(selected.shots.length!==1||selected.voice_takes.some(t=>t.accepted)||(selected.shots[0]?.motion_json.type||'static')!=='static'||Math.abs(sourceSpeed-1)>.001||selected.shots[0]?.speed_json?.freeze_at_ms!=null||(selected.shots[0]?.asset?.type==='video'&&(selected.shots[0].asset.duration_ms||0)<(selected.shots[0].source_in_ms||0)+sceneDuration(selected)));
  const audioFocused=!!activeAudioClip&&focusLane==='audio';
  const canSplit=audioFocused?!monitor:!!selected?.shots.length&&!monitor;
  const unlockedAudioTracks=timeline.audio_tracks.filter(t=>!trackLocks[t]);
  function applyAudioEdit(result:EditResult,message?:string){
    if(!result.ok){showToolMessage(result.error);return false;}
    onUpdateAudioClips?.(result.clips);
    if(result.selected?.length){setAudioSelection(result.selected);onAudioClipSelect?.(result.selected[result.selected.length-1]);}
    if(message)showToolMessage(message);
    return true;
  }
  function razorAll(at=position){
    const r=bladeAll(projectAudio,at,unlockedAudioTracks,frameMs(project.fps));
    applyAudioEdit(r,r.ok?`Razor all: cut ${r.selected?.length||0} audio clip${r.selected?.length===1?'':'s'} on unlocked tracks.`:undefined);
  }
  async function split(e?:React.MouseEvent,sceneOnly=false){
    if(e?.shiftKey){razorAll();return;}
    if(activeAudioClip&&audioFocused&&!sceneOnly){
      if(trackLocks[clipTrack(activeAudioClip)]){showToolMessage(`${clipTrack(activeAudioClip)} is locked.`);return;}
      const r=bladeClip(projectAudio,activeAudioClip.id,position,frameMs(project.fps));
      applyAudioEdit(r.ok?r:{ok:false,error:'Move the playhead inside the selected audio clip, at least one frame from either edge.'},'Audio clip split into two editable pieces.');return;
    }
    if(!selected||!selectedClip)return;
    if(needsBake&&(!selected.rendered_asset_id||selected.is_stale)){showToolMessage('Render this scene first. Its current motion, captions and sound must be included in the cut.');return;}
    const frame=Math.max(1,Math.round(1000/project.fps)),local=position-selectedClip.start,at=Math.round(local/frame)*frame;
    if(at<frame||at>selectedClip.duration-frame){showToolMessage('Move the playhead inside the selected clip, at least one frame from either edge.');return;}
    if(needsBake&&!await askConfirm('Split the rendered scene? Motion, separate narration, or speed effects will be baked into two clips and cannot be edited separately afterward. Original media files remain on disk. You can undo this split from the timeline.'))return;
    setToolMessage('');onSplit?.(at,needsBake);
  }

  useEffect(()=>{setMonitor(false);setPlaying(false);setToolMessage('');},[scenes.length]);
  useEffect(()=>{if(notice){setToolMessage('');if(toolMessageTimer.current)clearTimeout(toolMessageTimer.current);toolMessageTimer.current=null;}},[notice]);
  useEffect(()=>{const clip=authored.find(c=>c.scene.id===selectedId);if(clip&&scroll.current){const left=clip.start/1000*scale,right=clip.end/1000*scale,view=scroll.current;if(left<view.scrollLeft||right>view.scrollLeft+view.clientWidth)view.scrollLeft=Math.max(0,left-60);}},[selectedId]);
  const host=document.getElementById('sequence-viewer');
  useEffect(()=>{if(rulerSelection.current===selectedId){rulerSelection.current=null;return;}if(!monitor&&selectedClip)setPosition(selectedClip.start);},[selectedId,monitor]);
  useEffect(()=>{if(disabled&&playing){player.current?.pause();setPlaying(false);}},[disabled]);
  const [ctx,setCtx]=React.useState<{x:number;y:number;sceneId:string;kind:'scene'|'audio'|'clip'|'source';clipId?:string;shotId?:string;startMs?:number;durationMs?:number}|null>(null);
  // Which lane the user last worked in decides what Delete / Ctrl+C / Ctrl+V act on, so
  // deleting a cut audio piece never deletes the scene picture underneath it.
  const [audioClipboard,setAudioClipboard]=useState<{clips:TimelineAudioClip[];cut:boolean}|null>(null);
  const selectedAudioIds=()=>{const ids=audioSelection.length?audioSelection:selectedAudioClipId?[selectedAudioClipId]:[];return ids.filter(id=>projectAudio.some(c=>c.id===id&&!trackLocks[clipTrack(c)]));};
  function deleteAudio(ids:string[],ripple=false){if(!ids.length)return;applyAudioEdit(ripple?rippleDelete(projectAudio,ids):{ok:true,clips:projectAudio.filter(c=>!ids.includes(c.id)),selected:[]},ripple?`Ripple delete: ${ids.length} audio clip${ids.length===1?'':'s'} removed and later clips moved left.`:`${ids.length} audio clip${ids.length===1?'':'s'} removed. The video is unchanged.`);setAudioSelection([]);}
  function copyAudio(ids:string[],cut=false){const picked=projectAudio.filter(c=>ids.includes(c.id));if(!picked.length)return;setAudioClipboard({clips:picked,cut});if(cut)deleteAudio(ids);else showToolMessage(`Copied ${picked.length} audio clip${picked.length===1?'':'s'}. Move the playhead and paste.`);}
  function pasteAudio(at=position,track?:AudioTrackId){
    if(!audioClipboard?.clips.length){showToolMessage('Copy or cut an audio clip first.');return;}
    const first=Math.min(...audioClipboard.clips.map(c=>c.start_ms));
    const pasted=audioClipboard.clips.map(c=>{const target=track||clipTrack(c);return {...c,id:crypto.randomUUID(),start_ms:Math.max(0,Math.round(at+c.start_ms-first)),...(target==='A3'?{track:undefined}:{track:target})};});
    if(pasted.some(c=>trackLocks[clipTrack(c)])){showToolMessage('Unlock the target track to paste there.');return;}
    applyAudioEdit({ok:true,clips:[...projectAudio,...pasted],selected:pasted.map(c=>c.id)},`Pasted ${pasted.length} audio clip${pasted.length===1?'':'s'} at ${timecode(at,project.fps)}.`);
  }
  const groupOf=(id:string)=>{const g=projectAudio.find(c=>c.id===id)?.group;return g?projectAudio.filter(c=>c.group===g).map(c=>c.id):[id];};
  function groupAudio(ids:string[]){if(ids.length<2){showToolMessage('Select two or more audio clips (Ctrl+click) to group them.');return;}const g=`g${Date.now().toString(36)}`;applyAudioEdit({ok:true,clips:projectAudio.map(c=>ids.includes(c.id)?{...c,group:g}:c),selected:ids},`Grouped ${ids.length} clips: they now select and move together.`);}
  function ungroupAudio(ids:string[]){const groups=new Set(projectAudio.filter(c=>ids.includes(c.id)).map(c=>c.group).filter(Boolean));if(!groups.size)return;applyAudioEdit({ok:true,clips:projectAudio.map(c=>c.group&&groups.has(c.group)?{...c,group:undefined}:c)},'Ungrouped.');}
  function addClipMarker(clip:TimelineAudioClip){const at=Math.max(0,Math.min(clipEnd(clip)-clip.start_ms,Math.round(position-clip.start_ms)));saveMarkers([...markers,{id:`m${Date.now().toString(36)}`,time_ms:clip.start_ms+at,duration_ms:0,label:`${clip.name.slice(0,24)} cue`,color:'green',clip_id:clip.id,offset_ms:at}],'clip marker');showToolMessage('Marker attached to the clip: it moves when the clip moves.');}
  function duplicateAudio(ids:string[]){const picked=projectAudio.filter(c=>ids.includes(c.id));if(!picked.length)return;const end=Math.max(...picked.map(clipEnd)),first=Math.min(...picked.map(c=>c.start_ms));const copies=picked.map(c=>({...c,id:crypto.randomUUID(),name:c.name.endsWith(' copy')?c.name:`${c.name} copy`,start_ms:c.start_ms-first+end}));applyAudioEdit({ok:true,clips:[...projectAudio,...copies],selected:copies.map(c=>c.id)},'Duplicated after the original.');}
  useEffect(()=>{if(!ctx)return;const close=()=>setCtx(null);window.addEventListener('click',close);window.addEventListener('keydown',close);return()=>{window.removeEventListener('click',close);window.removeEventListener('keydown',close);};},[ctx]);
  useEffect(()=>{setPosition(p=>Math.min(p,length));},[length]);
  useEffect(()=>{setMonitor(false);setPlaying(false);setLive(false);},[project.id]);
  const lastAspect=useRef(project.aspect);
  useEffect(()=>{if(lastAspect.current!==project.aspect){lastAspect.current=project.aspect;setMonitor(false);setPlaying(false);setMediaError('');setPosition(0);}},[project.aspect]);
  useEffect(()=>{if(exportAsset){setMonitor(true);setPosition(0);setMediaError('');}},[exportAsset]);
  useEffect(()=>{const resize=()=>setHeight(h=>Math.min(h,Math.max(250,window.innerHeight*.4)));window.addEventListener('resize',resize);return()=>window.removeEventListener('resize',resize);},[]);
  function snapTime(ms:number){
    if(!snapEnabled||monitor)return ms;
    const points=[...clips.flatMap(c=>[c.start,c.end]),...markers.flatMap(m=>{const t=markerTime(m,projectAudio);return m.duration_ms?[t,t+m.duration_ms]:[t];}),...projectAudio.flatMap(c=>[c.start_ms,clipEnd(c)]),position];
    const threshold=Math.max(45,700/scale);
    return snapTimelineTime(ms,points,threshold);
  }
  function seek(ms:number,select=false,snap=false) {
    if(snap)ms=snapTime(ms);
    const limit=monitor&&Number.isFinite(player.current?.duration)?player.current!.duration*1000:length;
    const value=Math.max(0,Math.min(limit,ms));setPosition(value);
    if(monitor&&player.current){player.current.pause();player.current.currentTime=value/1000;}
    if(live&&!monitor)setLiveSeek(s=>({ms:value,n:s.n+1}));
    if(!monitor){const clip=[...clips].reverse().find(c=>value>=c.start);if(clip)requestAnimationFrame(()=>window.dispatchEvent(new CustomEvent('sceneforge-seek',{detail:{sceneId:clip.scene.id,timeMs:value-clip.start}})));}
    if(select&&!monitor){const c=[...clips].reverse().find(c=>value>=c.start);if(c&&c.scene.id!==selectedId){rulerSelection.current=c.scene.id;onSelect(c.scene.id);}}
  }
  const seekRef=useRef(seek);seekRef.current=seek;
  useEffect(()=>{const h=(e:Event)=>seekRef.current(Number((e as CustomEvent).detail?.timeMs)||0);window.addEventListener(TIMELINE_SEEK_EVENT,h);return()=>window.removeEventListener(TIMELINE_SEEK_EVENT,h);},[]);
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
  function dropMedia(e:React.DragEvent,sceneId:string|null,insert?:{before?:string;after?:string;audioTrack?:boolean;timeMs?:number;track?:string}):boolean{
    const kind=isMediaDrag(e);
    if(!kind)return false;
    e.preventDefault();e.stopPropagation();setDropTarget('');
    if(disabled)return true;
    if(kind==='assets'){try{onDropAssets?.(sceneId,JSON.parse(e.dataTransfer.getData(ASSET_DRAG_TYPE)),insert);}catch{/* malformed payload */}}
    else{const dt=e.dataTransfer;void collectDroppedFiles(dt).then(files=>files.length&&onDropFiles?.(sceneId,files,insert));}
    return true;
  }
  function togglePlay() {
    if(disabled||!scenes.some(s=>s.shots.length))return;
    // Play runs the timeline live from the scene renders; "Preview last export" keeps the movie player.
    if(!monitor){if(!live)startLive();else{setLiveRate(1);setPlaying(p=>!p);}return;}
    if(player.current?.paused){if(player.current.ended)player.current.currentTime=0;void player.current.play().catch(()=>setMediaError('Press Play in the video controls to begin playback.'));}
    else player.current?.pause();
  }
  function startLive(){const from=position>=length-1?0:position;setLive(true);setLiveRate(1);setPosition(from);setLiveSeek(s=>({ms:from,n:s.n+1}));setPlaying(true);}
  // J / K / L: back 5 s, pause, play (L again: 2×, 4×) in live timeline playback.
  function liveKey(k:'j'|'k'|'l'){
    if(k==='k'){setPlaying(false);setLiveRate(1);return;}
    if(k==='l'){if(!live)startLive();else if(!playing){setLiveRate(1);setPlaying(true);}else setLiveRate(r=>Math.min(4,r*2));return;}
    seek(Math.max(0,position-5000),true);
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
    if(focusLane==='audio'&&!disabled&&!t?.classList.contains('narration-clip')){
      const ids=selectedAudioIds(),k=e.key.toLowerCase();
      if(mod&&!e.shiftKey&&k==='c'&&ids.length){e.preventDefault();copyAudio(ids);return;}
      if(mod&&!e.shiftKey&&k==='x'&&ids.length){e.preventDefault();copyAudio(ids,true);return;}
      if(mod&&!e.shiftKey&&k==='v'&&audioClipboard){e.preventDefault();pasteAudio();return;}
      if(mod&&!e.shiftKey&&k==='d'&&ids.length){e.preventDefault();duplicateAudio(ids);return;}
      if(mod&&k==='g'&&ids.length){e.preventDefault();if(e.shiftKey)ungroupAudio(ids);else groupAudio(ids);return;}
      if(!mod&&(e.key==='Delete'||e.key==='Backspace')&&ids.length){e.preventDefault();deleteAudio(ids,e.shiftKey);return;}
    }
    if(mod&&!e.shiftKey&&['d','c','v'].includes(e.key.toLowerCase())&&!disabled){
      const k=e.key.toLowerCase(), narr=t?.classList.contains('narration-clip')?t.dataset.sceneId:null, sc=scenes.find(x=>x.id===(narr||selectedId));
      if(k==='d'&&sc&&!trackLocks.V1){e.preventDefault();onDuplicate?.(sc.id);return;}
      if(k==='c'&&sc){e.preventDefault();const take=sc.voice_takes.find(v=>v.accepted);
        if(narr&&take)onClipboard?.({kind:'audio',id:take.id,label:`${sc.title} audio`});else onClipboard?.({kind:'scene',id:sc.id,label:sc.title});return;}
      if(k==='v'&&sc&&clipboard&&!(clipboard.kind==='scene'?trackLocks.V1:trackLocks.A1)){e.preventDefault();onPaste?.(sc.id);return;}
    }
    if(mod)return;
    if(!e.shiftKey&&!monitor&&!disabled&&['j','k','l'].includes(e.key.toLowerCase())&&scenes.some(s=>s.shots.length)){e.preventDefault();liveKey(e.key.toLowerCase() as 'j'|'k'|'l');return;}
    const toolKey=TOOL_KEYS[e.key.toLowerCase()];
    if(toolKey&&!e.shiftKey&&e.key.length===1){e.preventDefault();setTool(toolKey);showToolMessage(`${TOOL_LABELS[toolKey][0]} tool (${TOOL_LABELS[toolKey][1]})`);return;}
    if(e.key==='C'&&e.shiftKey&&!disabled){e.preventDefault();razorAll();return;}
    if(e.key===' '&&t?.tagName!=='BUTTON'){e.preventDefault();togglePlay();}
    else if(e.key==='ArrowLeft'){e.preventDefault();if(e.shiftKey)seek([...clips].reverse().find(c=>c.start<position-1)?.start||0,true);else seek(position-frame,true);}
    else if(e.key==='ArrowRight'){e.preventDefault();if(e.shiftKey)seek(clips.find(c=>c.start>position+1)?.start??length,true);else seek(position+frame,true);}
    else if(e.key==='Home'){e.preventDefault();seek(0,true);}
    else if(e.key==='End'){e.preventDefault();seek(length,true);}
    else if((e.key==='Delete'||e.key==='Backspace')&&t?.classList.contains('narration-clip')&&!disabled&&!trackLocks.A1){e.preventDefault();const id=t.dataset.sceneId;if(id&&scenes.find(x=>x.id===id)?.voice_takes.some(v=>v.accepted))onRemoveSceneAudio?.(id);}
    else if((e.key==='Delete'||e.key==='Backspace')&&selected&&!disabled&&!trackLocks.V1){e.preventDefault();onDelete?.();}
  };
  useEffect(()=>{const h=(e:KeyboardEvent)=>shortcut.current(e);window.addEventListener('keydown',h);return()=>window.removeEventListener('keydown',h);},[]);
  function drop(target:string,after=false) {
    if(disabled||trackLocks.V1||!drag||drag===target)return;
    const ids=scenes.map(s=>s.id),from=ids.indexOf(drag);
    if(from<0)return;
    ids.splice(from,1);let to=ids.indexOf(target);
    if(to<0)return;if(after)to++;
    ids.splice(to,0,drag);setDrag('');void onReorder(ids);
  }
  function move(dir:number) {
    if(disabled||trackLocks.V1||index<0||index+dir<0||index+dir>=scenes.length)return;
    const ids=scenes.map(s=>s.id);[ids[index],ids[index+dir]]=[ids[index+dir],ids[index]];void onReorder(ids);
  }
  // Range markers span the selected audio clip(s), or the selected scene when no audio clip is selected.
  function selectionRange(){
    const picked=projectAudio.filter(c=>audioSelection.includes(c.id)||c.id===selectedAudioClipId);
    if(picked.length)return {from:Math.min(...picked.map(c=>c.start_ms)),to:Math.max(...picked.map(clipEnd))};
    return selectedClip?{from:selectedClip.start,to:selectedClip.end}:null;
  }
  async function addMarker(range=false){
    const span=range?selectionRange():null;
    if(range&&!span){showToolMessage('Select a scene or audio clip to mark its range.');return;}
    const label=await askText(range?'Name this range marker':'Name this timeline marker',`${range?'Range':'Marker'} ${markers.length+1}`);
    if(label===null)return;
    const frame=1000/project.fps,time=Math.round(Math.max(0,span?span.from:position)/frame)*frame;
    const marker:TimelineMarker={id:`m${Date.now().toString(36)}${Math.random().toString(36).slice(2,6)}`,time_ms:Math.round(time),duration_ms:span?Math.round(span.to-span.from):0,label:label.trim()||`Marker ${markers.length+1}`,color:range?'blue':'amber'};
    saveMarkers([...markers,marker],'add marker');
  }
  async function addBeatMarkers(every:number){
    const clipId=activeAudioClip&&focusLane==='audio'?activeAudioClip.id:undefined;
    showToolMessage(clipId?`Finding the beat in ${activeAudioClip!.name}…`:'Finding the beat in the music bed…');
    try{
      const r=await api.beatMarkers(project.id,{clip_id:clipId,every});
      const kept=markers.filter(m=>!m.id.startsWith('beat-'));
      const beats:TimelineMarker[]=r.markers.slice(0,Math.max(0,200-kept.length)).map((b,i)=>({id:`beat-${i}-${b.time_ms}`,time_ms:b.time_ms,duration_ms:0,label:b.downbeat?'♪1':'♪',color:b.downbeat?'red':'purple'}));
      saveMarkers([...kept,...beats],'beat markers');
      showToolMessage(`${beats.length} beat markers at ${r.bpm} BPM${r.truncated||beats.length<r.markers.length?' (limited to 200 markers)':''}. Snapping lands cuts and clips on them; red = first beat of each bar.`);
    }catch(e:any){showToolMessage(e.message||String(e));}
  }
  function clearBeatMarkers(){const kept=markers.filter(m=>!m.id.startsWith('beat-'));if(kept.length!==markers.length)saveMarkers(kept,'clear beat markers');}
  function removeMarker(id:string){saveMarkers(markers.filter(x=>x.id!==id),'remove marker');}
  function recolorMarker(m:TimelineMarker){const color=MARKER_COLORS[(MARKER_COLORS.indexOf(m.color)+1)%MARKER_COLORS.length];saveMarkers(markers.map(x=>x.id===m.id?{...x,color}:x),'marker colour');}
  function resize(e:React.PointerEvent<HTMLDivElement>) {
    e.currentTarget.setPointerCapture?.(e.pointerId);
    e.currentTarget.dataset.origin=String(e.clientY);e.currentTarget.dataset.height=String(height);
  }
  function fit(){setScale(Math.max(.5,Math.min(150,((scroll.current?.clientWidth||800)-40)/Math.max(1,length/1000))));}
  function beginShotTrim(sceneId:string,shot:Scene['shots'][number],edge:'in'|'out',e:React.PointerEvent<HTMLDivElement>,duration:number){
    if(disabled||monitor)return;e.preventDefault();e.stopPropagation();e.currentTarget.setPointerCapture?.(e.pointerId);
    const sourceOut=shot.source_out_ms??shot.asset?.duration_ms??0,sourceIn=shot.source_in_ms||0;
    setTrim({id:sceneId,x:e.clientX,original:duration,ms:duration,shotId:shot.id,sourceIn,sourceOut,edge});
  }
  function moveShotTrim(sceneId:string,shot:Scene['shots'][number],e:React.PointerEvent<HTMLDivElement>){
    if(trim?.id!==sceneId||trim.shotId!==shot.id||!e.currentTarget.hasPointerCapture?.(e.pointerId))return;
    const delta=(e.clientX-trim.x)/scale*1000,speed=Math.max(.1,Number((shot as any).speed_json?.speed)||1);
    const sourceIn=trim.edge==='in'?Math.max(0,Math.min(trim.sourceOut!-100,Math.round(trim.sourceIn!+delta))):trim.sourceIn!;
    const sourceOut=trim.edge==='out'?Math.max(sourceIn+100,Math.min(shot.asset?.duration_ms||trim.sourceOut!,Math.round(trim.sourceOut!+delta))):trim.sourceOut!;
    setTrim({...trim,sourceIn,sourceOut,ms:Math.max(100,(sourceOut-sourceIn)/speed)});
  }
  function finishShotTrim(sceneId:string,shotId:string,e:React.PointerEvent<HTMLDivElement>){
    if(!trim||trim.id!==sceneId||trim.shotId!==shotId)return;
    e.currentTarget.releasePointerCapture?.(e.pointerId);const {sourceIn,sourceOut}=trim;setTrim(null);
    if(sourceIn!=null&&sourceOut!=null)onTrimShot?.(sceneId,shotId,sourceIn,sourceOut);
  }
  function selectProjectAudio(id:string){setFocusLane('audio');onAudioClipSelect?.(id);setMonitor(false);setPlaying(false);if(selectedId)window.dispatchEvent(new CustomEvent('sceneforge-open-tab',{detail:{sceneId:selectedId,tab:'Audio',audioClipId:id}}));}
  // One pointer gesture on a timeline audio clip. What it does depends on the active tool;
  // previews are computed with the same pure edit operations that are saved on release.
  function beginProjectAudioDrag(clip:TimelineAudioClip,mode:'move'|'left'|'right',e:React.PointerEvent<HTMLElement>){
    const track=clipTrack(clip);
    if(disabled||monitor||trackLocks[track])return;e.preventDefault();e.stopPropagation();
    const frame=frameMs(project.fps),rect=e.currentTarget.getBoundingClientRect();
    const pointerTime=clip.start_ms+Math.max(0,Math.min(1,(e.clientX-rect.left)/Math.max(1,rect.width)))*(clip.source_out_ms-clip.source_in_ms);
    if(tool==='blade'&&mode==='move'){
      selectProjectAudio(clip.id);
      const at=snapTime(pointerTime);
      if(e.shiftKey)razorAll(at);else applyAudioEdit(bladeClip(projectAudio,clip.id,at,frame),'Blade: clip cut at the pointer.');
      return;
    }
    let group=[clip.id];
    if(tool==='track_select'&&mode==='move')group=trackSelectForward(projectAudio,track,clip.start_ms);
    else if(e.ctrlKey||e.metaKey){const next=audioSelection.includes(clip.id)?audioSelection.filter(id=>id!==clip.id):[...audioSelection,clip.id];setAudioSelection(next);selectProjectAudio(clip.id);return;}
    else if(audioSelection.includes(clip.id)&&audioSelection.length>1&&mode==='move'&&(tool==='select'||tool==='ripple'))group=audioSelection;
    if(mode==='move'&&(tool==='select'||tool==='ripple')&&clip.group)group=Array.from(new Set([...group,...groupOf(clip.id)]));
    setAudioSelection(group);selectProjectAudio(clip.id);
    if(mode==='move')seek(pointerTime);
    const {before,after}=neighbours(projectAudio,clip,frame);
    const trackIndex=AUDIO_TRACKS.indexOf(track),originY=e.clientY,laneHeight=laneRow+8;
    const compute=(dx:number,dy:number):EditResult=>{
      const delta=Math.round((dx/scale*1000)/frame)*frame;
      if(mode!=='move'){
        const edge=mode==='left'?'in':'out';
        if(tool==='ripple')return rippleTrim(projectAudio,clip.id,edge,delta);
        if(tool==='roll'&&edge==='out'&&after)return roll(projectAudio,clip.id,after.id,delta);
        if(tool==='roll'&&edge==='in'&&before)return roll(projectAudio,before.id,clip.id,delta);
        return trimClip(projectAudio,clip.id,edge,delta);
      }
      if(tool==='slip')return slip(projectAudio,clip.id,-delta);
      if(tool==='slide')return slide(projectAudio,clip.id,delta,frame);
      // Select / track select / ripple body: move in time; vertical drags change track.
      const target=AUDIO_TRACKS[Math.max(0,Math.min(AUDIO_TRACKS.length-1,trackIndex+Math.round(dy/laneHeight)))];
      const toTrack=group.length===1&&target!==track&&!trackLocks[target]?target:undefined;
      const snapped=group.length===1?snapTime(clip.start_ms+delta)-clip.start_ms:delta;
      return moveClips(projectAudio,group,snapped,toTrack);
    };
    const start={pointerId:e.pointerId,x:e.clientX,y:e.clientY};
    audioDragRef.current={id:clip.id,clips:null};setAudioDrag({id:clip.id,clips:null});
    const preview=rafCoalesce<TimelineAudioClip[]>(clips=>{if(audioDragRef.current){audioDragRef.current={id:clip.id,clips};setAudioDrag({id:clip.id,clips});}});
    let latest:EditResult|null=null;
    const move=(event:PointerEvent)=>{
      if(event.pointerId!==start.pointerId||!audioDragRef.current)return;
      latest=compute(event.clientX-start.x,event.clientY-originY);
      if(latest.ok)preview.push(latest.clips);
    };
    const finish=(event:PointerEvent)=>{
      if(event.pointerId!==start.pointerId)return;
      window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',finish);window.removeEventListener('pointercancel',finish);
      preview.cancel();audioDragRef.current=null;setAudioDrag(null);
      if(event.type==='pointercancel')return;
      const result=event.clientX===start.x&&event.clientY===start.y?null:compute(event.clientX-start.x,event.clientY-originY);
      if(!result)return;
      if(!result.ok){showToolMessage(result.error);return;}
      if(JSON.stringify(result.clips)!==JSON.stringify(projectAudio))applyAudioEdit({...result,selected:group.length>1?group:result.selected});
    };
    window.addEventListener('pointermove',move);window.addEventListener('pointerup',finish);window.addEventListener('pointercancel',finish);
  }
  const shownAudio:TimelineAudioClip[]=audioDrag?.clips||projectAudio;
  const audioRows=React.useMemo(()=>{const rows:Record<string,number>={};for(const t of AUDIO_TRACKS)Object.assign(rows,packRows(shownAudio.filter(c=>clipTrack(c)===t)));return rows;},[shownAudio]);
  const laneHeights=Object.fromEntries(AUDIO_TRACKS.map(t=>{const n=shownAudio.filter(c=>clipTrack(c)===t).reduce((m,c)=>Math.max(m,(audioRows[c.id]||0)+1),1);return [t,isCollapsed(t)?COLLAPSED_LANE_H:Math.max(compact?20:38,n*laneRow+6)];})) as Record<AudioTrackId,number>;
  const visibleMs=visibleWindow(view.left,view.width,scale);
  const step=scale>=100?1:scale>=40?2:scale>=16?5:scale>=4?15:60;
  const audioEnd=shownAudio.reduce((end,clip)=>Math.max(end,clipEnd(clip)),0);
  const extent=Math.max(length/1000+3,audioEnd/1000+3,16);
  return <section className={`sequence-dock ${minimized?'minimized':''}`} aria-label="Video timeline" style={{height:minimized?90:height}}>
    <div className="dock-resizer" role="separator" aria-label="Resize timeline" aria-orientation="horizontal" aria-valuenow={height} aria-valuemin={250} aria-valuemax={Math.max(250,Math.round(window.innerHeight*.6))} tabIndex={0}
      onPointerDown={resize} onPointerMove={e=>{if(e.currentTarget.hasPointerCapture?.(e.pointerId))setHeight(Math.max(250,Math.min(window.innerHeight*.6,Number(e.currentTarget.dataset.height)+Number(e.currentTarget.dataset.origin)-e.clientY)));}}
      onKeyDown={e=>{if(e.key==='ArrowUp'||e.key==='ArrowDown'){e.preventDefault();setHeight(h=>Math.max(250,Math.min(window.innerHeight*.6,h+(e.key==='ArrowUp'?20:-20))));}}}><span/></div>
    <header className="sequence-toolbar">
      <div className="sequence-title"><Film size={16}/><strong>Timeline 01</strong><span>{project.fps} fps</span></div>
      <div className="timeline-actions"><button aria-label="Undo timeline edit" title={canUndo?"Undo the last timeline edit":"No timeline edits to undo in this session"} disabled={disabled||!canUndo} onClick={onUndo}><Undo2 size={15}/>Undo</button><button aria-label="Redo timeline edit" title={canRedo?"Redo timeline edit":"Nothing to redo — undo a timeline edit first"} disabled={disabled||!canRedo} onClick={onRedo}><Redo2 size={15}/>Redo</button><button aria-label="Split at playhead" title="Split the selected video or audio clip at the playhead (Shift+click: Razor All cuts every unlocked timeline audio track). Motion, separate narration, or speed effects require rendering first." disabled={disabled||!canSplit||(audioFocused?trackLocks[clipTrack(activeAudioClip!)]:trackLocks.V1)} onClick={e=>void split(e)}><Scissors size={15}/></button><span className="tl-zoom" role="group" aria-label="Preview zoom tools"><button title="Zoom into the preview (Ctrl + mouse wheel on the picture)" aria-label="Zoom preview in" onClick={()=>window.dispatchEvent(new CustomEvent('sceneforge-preview-zoom',{detail:1}))}><ZoomIn size={15}/></button><button title="Zoom out of the preview" aria-label="Zoom preview out" onClick={()=>window.dispatchEvent(new CustomEvent('sceneforge-preview-zoom',{detail:-1}))}><ZoomOut size={15}/></button><button title="Fit the preview" aria-label="Fit preview to window" onClick={()=>window.dispatchEvent(new CustomEvent('sceneforge-preview-zoom',{detail:'fit'}))}><Maximize size={15}/></button></span><button aria-label="Ripple delete selected scene" title="Ripple delete selected scene and close the gap" disabled={disabled||!selected||trackLocks.V1} onClick={onDelete}><Trash2 size={15}/></button><button aria-label="Import timeline audio" title="Import audio into selected scene's A1 lane" disabled={disabled||!selected} onClick={onAudio}><Upload size={15}/><Volume2 size={14}/></button><button aria-label="Remove selected scene audio" title="Remove accepted audio from selected scene" disabled={disabled||!selected?.voice_takes.some(t=>t.accepted)||trackLocks.A1} onClick={onRemoveAudio}><Volume2 size={14}/><X size={12}/></button></div>
      <div className="timeline-marker-actions"><button aria-pressed={snapEnabled} title={snapEnabled?'Snapping on · ruler scrubs snap near scene edges and markers':'Snapping off'} aria-label="Toggle timeline snapping" className={snapEnabled?'active':''} onClick={()=>setSnapEnabled(v=>!v)}><Magnet size={14}/> Snap</button><button disabled={monitor} title="Add a named bookmark at the playhead; click it later to jump back here" aria-label="Add timeline marker" onClick={()=>void addMarker()}><Flag size={14}/> Marker</button><button disabled={monitor||disabled} title="Add a named range marker spanning the selected audio clip(s) or scene" aria-label="Add range marker for selection" onClick={()=>void addMarker(true)}><Flag size={14}/> Range</button><select aria-label="Add beat markers" className="beat-marker-select" disabled={monitor||disabled} value="" title="Detect the beat of the music bed (or the selected timeline audio clip) and add markers that cuts snap to" onChange={e=>{const v=e.target.value;if(v==='clear')clearBeatMarkers();else if(v)void addBeatMarkers(Number(v));}}><option value="">♪ Beats…</option><option value="1">Mark every beat</option><option value="2">Every 2nd beat</option><option value="4">Every bar (4 beats)</option>{markers.some(m=>m.id.startsWith('beat-'))&&<option value="clear">Remove beat markers</option>}</select><FeatureHelp compact title="Timeline markers" description="Markers are named bookmarks on the ruler. They help you remember a moment, like a title change, music cue, or section boundary." steps="Move the playhead to the moment, click Marker, and enter a short name. Range marks the selected audio clip(s) or scene as a span. Click a marker flag to jump back to it, its colour dot to change the colour, and its X to remove it. Markers are saved with the project and can be undone."/></div>
      <div className="sequence-transport" role="group" aria-label="Playback">
        <button title="Go to start (Home)" aria-label="Go to timeline start" onClick={()=>seek(0,true)}><SkipBack size={16}/></button>
        <button title="Previous scene" aria-label="Previous scene" disabled={disabled||!clips.length||position<=0} onClick={()=>seek([...clips].reverse().find(c=>c.start<position-1)?.start||0,true)}><StepBack size={16}/></button>
        <button title="Previous frame (←)" aria-label="Previous frame" disabled={disabled||position<=0} onClick={()=>seek(position-1000/project.fps,true)}><ChevronLeft size={16}/></button>
        <button className="transport-play" title={playing?'Pause (Space)':(monitor?'Play the last export (Space)':'Play the timeline from the scene renders (Space · J/K/L)')} aria-label={playing?'Pause movie':'Play movie'} disabled={!scenes.some(s=>s.shots.length)||disabled} onClick={togglePlay}>{playing?<Pause size={16}/>:<Play size={16}/>}</button>
        <button aria-label="Stop full video" title="Stop and return to start" disabled={!monitor&&!live} onClick={()=>{if(live&&!monitor)setPlaying(false);seek(0);}}><Square size={15}/></button>
        <button title="Next frame (→)" aria-label="Next frame" disabled={disabled||position>=length} onClick={()=>seek(position+1000/project.fps,true)}><ChevronRight size={16}/></button>
        <button title="Next scene" aria-label="Next scene" disabled={disabled||!clips.some(c=>c.start>position+1)} onClick={()=>seek(clips.find(c=>c.start>position+1)?.start||length,true)}><StepForward size={16}/></button>
        <button title="Go to end (End)" aria-label="Go to timeline end" onClick={()=>seek(length,true)}><SkipForward size={16}/></button>
        <span className="transport-timecode" aria-label="Timeline timecode">{timecode(position,project.fps)}</span>
      </div>
      <div className="sequence-tools"><button className="render-sequence" title="Render every scene and assemble the full video" disabled={disabled||!scenes.some(s=>s.shots.length)} onClick={onRender}><Clapperboard size={14}/> Render full video</button><button aria-label="Minimize or restore timeline" title={minimized?'Restore timeline':'Minimize timeline'} onClick={()=>setMinimized(!minimized)}>{minimized?<ChevronUp size={15}/>:<ChevronDown size={15}/>}</button><button aria-label="Maximize timeline" title="Maximize timeline" onClick={()=>{setMinimized(false);setHeight(window.innerHeight*.6);}}><Maximize2 size={13}/></button><button aria-label="Compact tracks" aria-pressed={compact} className={compact?'active':''} title={compact?'Compact tracks on: lanes at half height. Click for full height.':'Compact tracks: halve every lane height to see more tracks'} onClick={()=>updateTrackView({...tv,compact:!compact})}><Rows3 size={14}/></button><button aria-label="Fit timeline" title="Fit timeline to width" onClick={fit}><ArrowLeftRight size={15}/></button><label>Zoom<input aria-label="Timeline zoom" type="range" min={.5} max={150} step={.5} value={scale} onChange={e=>setScale(Number(e.target.value))}/></label><button disabled={disabled} onClick={onAdd}><Plus size={15}/> Add part</button></div>
    </header>
    <div className="sequence-editbar">
      <span className="timeline-tools" role="toolbar" aria-label="Timeline edit tools">{(Object.keys(TOOL_LABELS) as TimelineTool[]).map(k=><button key={k} className={tool===k?'active':''} aria-pressed={tool===k} aria-label={`${TOOL_LABELS[k][0]} tool`} title={`${TOOL_LABELS[k][0]} (${TOOL_LABELS[k][1]}) · applies to timeline audio clips on A3–A8${k==='blade'?' · Shift+click or Shift+C: Razor All':''}`} onClick={()=>setTool(k)}>{TOOL_LABELS[k][1]}</button>)}<FeatureHelp compact title="Timeline edit tools" description="Edit tools work on timeline audio clips (A3–A8). Scenes on V1 keep their scene tools: drag to reorder, edge trims, scissors and ripple delete." steps="V Select: drag to move, up/down to change track, Ctrl+click to add to the selection. A Track select: grabs this clip and everything after it on the track. B Ripple: trimming an edge moves later clips on the track. N Roll: drag the edge between two touching clips. Y Slip: change which part of the audio plays. U Slide: move a clip between its neighbours. C Blade: click to cut; Shift+click or Shift+C cuts every unlocked audio track. Delete removes a focused clip; Shift+Delete ripple-deletes it."/></span>
      <span className="tool-feedback" aria-live="polite">{toolMessage||shownNotice}</span><span className="selection-label">{selected?.title||'Select a part'}</span>
      <button aria-label="Move timeline part earlier" title="Move part earlier" disabled={disabled||trackLocks.V1||index<=0} onClick={()=>move(-1)}><ArrowLeft size={14}/>Earlier</button>
      <button aria-label="Move timeline part later" title="Move part later" disabled={disabled||trackLocks.V1||index<0||index>=scenes.length-1} onClick={()=>move(1)}><ArrowRight size={14}/>Later</button>
      <label>Transition<select aria-label="Incoming transition" disabled={disabled||!selected?.shots.length||firstPlayable} value={selected?.transition_in_json.type||'cut'} onChange={e=>selected&&void onUpdate(selected.id,{transition_in:{type:e.target.value,duration_ms:e.target.value==='cut'?0:(selected.transition_in_json.duration_ms||500)}})}>{selected?.transition_in_json.type&&!TRANSITIONS.some(([key])=>key===selected.transition_in_json.type)&&<option value={selected.transition_in_json.type}>Existing · {transitionLabel(selected.transition_in_json.type)}</option>}{TRANSITIONS.map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      <label>Duration<input aria-label="Transition seconds" type="number" min={0} max={30} step={.1} key={`${selectedId}-${selected?.transition_in_json.duration_ms}`} defaultValue={(selected?.transition_in_json.duration_ms||0)/1000} disabled={disabled||!selected?.shots.length||firstPlayable||selected.transition_in_json.type==='cut'} onBlur={e=>{if(selected&&e.target.validity.valid&&e.target.value!=='')void onUpdate(selected.id,{transition_in:{...selected.transition_in_json,duration_ms:Math.round(Number(e.target.value)*1000)}});}} onKeyDown={e=>{if(e.key==='Enter')e.currentTarget.blur();}}/>s</label><button aria-label="Remove transition" disabled={disabled||!selected||selected.transition_in_json.type==='cut'} onClick={()=>selected&&void onUpdate(selected.id,{transition_in:{type:'cut',duration_ms:0}})}><X size={12}/>Remove</button><span className="overlap-info" title="Limited to half the duration of either neighboring scene">Overlap {((selectedClip?.overlap||0)/1000).toFixed(2)}s</span>
      <button className="movie-toggle" disabled={!exportAsset} onClick={()=>{setMonitor(!monitor);setPlaying(false);setMediaError('');}}>{monitor?'Return to editing':'Preview last export'}</button>
    </div>
    <div className={`sequence-tracks ${compact?'compact-tracks':''}`}>
      <aside className="track-headers" aria-label="Track headers"><div className="track-ruler-label">TRACKS</div>{([['T1','Text','Captions & titles','track-text-label',Type],['V1','Picture',`${scenes.length} parts`,'track-video-label',Film],['A1','Narration','Accepted takes','track-audio-label',Volume2],['A2','Clip sound','Video audio','track-source-audio-label',Volume2]] as const).map(([key,label,detail,className,Icon])=><div key={key} className={`${className} ${trackLocks[key]?'track-locked':''} ${isCollapsed(key)?'track-collapsed':''}`} style={collapsedStyle(key)}>{collapseButton(key,label.toLowerCase())}<b>{key}</b><Icon size={15}/><span>{label}<small>{trackLocks[key]?'Locked':detail}</small></span><button className="track-lock-button" aria-label={`${trackLocks[key]?'Unlock':'Lock'} ${key} ${label.toLowerCase()} track`} aria-pressed={trackLocks[key]} title={`${trackLocks[key]?'Unlock':'Lock'} ${key} track`} disabled={disabled} onClick={()=>toggleTrackLock(key)}>{trackLocks[key]?<Lock size={12}/>:<Unlock size={12}/>}</button></div>)}{timeline.audio_tracks.map(t=>{const count=projectAudio.filter(c=>clipTrack(c)===t).length,state=timeline.tracks[t]||{},audible=isAudioTrackAudible(timeline,t);return <div key={t} className={`track-project-audio-label ${trackLocks[t]?'track-locked':''} ${audible?'':'track-silent'} ${isCollapsed(t)?'track-collapsed':''}`} style={{height:laneHeights[t],minHeight:laneHeights[t]}}>{collapseButton(t,'audio')}<b>{t}</b><Volume2 size={15}/><span>{audioTrackLabel(t)}<small>{trackLocks[t]?'Locked':!audible?(state.mute?'Muted':'Not soloed'):`${count} clip${count===1?'':'s'}`}</small></span><span className="track-state-buttons"><button className={`track-mute-button ${state.mute?'active':''}`} aria-label={`${state.mute?'Unmute':'Mute'} ${t} track`} aria-pressed={!!state.mute} title={`${state.mute?'Unmute':'Mute'} every clip on ${t} in playback and export`} disabled={disabled} onClick={()=>setTrackState(t,'mute')}>M</button><button className={`track-solo-button ${state.solo?'active':''}`} aria-label={`${state.solo?'Unsolo':'Solo'} ${t} track`} aria-pressed={!!state.solo} title={`Solo ${t}: only soloed timeline audio tracks (A3–A8) are heard. Narration, clip sound and music are not affected.`} disabled={disabled} onClick={()=>setTrackState(t,'solo')}>S</button>{t!=='A3'&&!count&&<button className="track-hide-button" aria-label={`Remove empty ${t} track`} title={`Remove the empty ${t} track`} disabled={disabled} onClick={()=>hideAudioTrack(t)}><X size={11}/></button>}</span><button className="track-lock-button" aria-label={t==='A3'?`${trackLocks.A3?'Unlock':'Lock'} A3 timeline audio track`:`${trackLocks[t]?'Unlock':'Lock'} ${t} audio track`} aria-pressed={trackLocks[t]} title={`${trackLocks[t]?'Unlock':'Lock'} ${t} track`} disabled={disabled} onClick={()=>toggleTrackLock(t)}>{trackLocks[t]?<Lock size={12}/>:<Unlock size={12}/>}</button></div>;})}<button className="track-add-button" disabled={disabled||!nextAudioTrack(timeline)} title={nextAudioTrack(timeline)?`Add audio track ${nextAudioTrack(timeline)}`:'All audio tracks (A3–A8) are shown'} aria-label="Add audio track" onClick={addAudioTrack}><Plus size={13}/>{nextAudioTrack(timeline)?`Add ${nextAudioTrack(timeline)}`:'A3–A8 shown'}</button></aside>
      <div className="sequence-scroll" ref={scroll} onScroll={e=>viewUpdate.current.push({left:e.currentTarget.scrollLeft,width:e.currentTarget.clientWidth||1600})} onWheel={e=>{if(!(e.ctrlKey||e.metaKey)||!scroll.current)return;e.preventDefault();const r=scroll.current.getBoundingClientRect(),z=zoomAround(scale,scale*(e.deltaY<0?1.2:1/1.2),e.clientX-r.left,scroll.current.scrollLeft);setScale(z.scale);requestAnimationFrame(()=>{if(scroll.current)scroll.current.scrollLeft=z.scrollLeft;});}}>
        <div className="sequence-content" style={{width:Math.max(650,extent*scale)}}>
          <div className="sequence-ruler" role="slider" aria-label="Timeline playhead" aria-valuemin={0} aria-valuemax={Math.round(length)} aria-valuenow={Math.round(position)} tabIndex={0} onKeyDown={e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();seek(position+(e.key==='ArrowLeft'?-1:1)*1000/project.fps,true);}}}
            onPointerDown={e=>{e.currentTarget.setPointerCapture?.(e.pointerId);seek((e.clientX-e.currentTarget.getBoundingClientRect().left)/scale*1000,true,true);}}
            onPointerMove={e=>{if(e.currentTarget.hasPointerCapture?.(e.pointerId))seek((e.clientX-e.currentTarget.getBoundingClientRect().left)/scale*1000,true,true);}}>
            {Array.from({length:Math.min(1000,Math.ceil(extent/step))},(_,i)=><span key={i} style={{left:i*step*scale}}>{timecode(i*step*1000,project.fps).slice(0,8)}</span>)}
            {markers.map(m=><span key={m.id} className={`timeline-marker marker-${m.color} ${m.duration_ms?'range':''}`} style={{left:markerTime(m,shownAudio)/1000*scale}}>{m.duration_ms>0&&<span className="timeline-marker-range" aria-hidden="true" style={{width:Math.max(2,m.duration_ms/1000*scale)}}/>}<button className="timeline-marker-color" title={`Change colour of ${m.label} (now ${m.color})`} aria-label={`Change colour of marker ${m.label}`} onPointerDown={e=>e.stopPropagation()} onClick={e=>{e.stopPropagation();recolorMarker(m);}}/><button title={`${m.clip_id?'📎 ':''}${m.label} · ${timecode(markerTime(m,projectAudio),project.fps)}${m.duration_ms?` → ${timecode(m.time_ms+m.duration_ms,project.fps)}`:''} · click to jump to this saved point`} aria-label={`Seek to marker ${m.label}`} onPointerDown={e=>e.stopPropagation()} onClick={e=>{e.stopPropagation();seek(markerTime(m,projectAudio));}}><Flag size={11}/>{m.label}</button><button className="timeline-marker-remove" title={`Remove marker ${m.label}`} aria-label={`Remove marker ${m.label}`} onPointerDown={e=>e.stopPropagation()} onClick={e=>{e.stopPropagation();removeMarker(m.id);}}><X size={10}/></button></span>)}
          </div>
          {ctx&&(()=>{const sc=scenes.find(x=>x.id===ctx.sceneId);const take=sc?.voice_takes.find(v=>v.accepted);const sceneClip=clips.find(c=>c.scene.id===ctx.sceneId);const menuClip=ctx.clipId?projectAudio.find(c=>c.id===ctx.clipId):undefined;const ids=ctx.kind==='clip'?selectedAudioIds():[];const shot=ctx.shotId?sc?.shots.find(x=>x.id===ctx.shotId):undefined;const close=(fn:()=>void)=>()=>{setCtx(null);fn();};return <div className="clip-menu" role="menu" aria-label="Timeline clip actions" style={{left:ctx.x,top:ctx.y}} onClick={e=>e.stopPropagation()}>
            {ctx.kind==='scene'&&<>
              <button role="menuitem" disabled={disabled||trackLocks.V1||!sc?.shots.length||monitor} onClick={close(()=>{setFocusLane('scene');void split(undefined,true);})}>Split scene at playhead <kbd>C</kbd></button>
              <button role="menuitem" disabled={disabled||trackLocks.V1} onClick={close(()=>onDuplicate?.(ctx.sceneId))}>Duplicate scene <kbd>Ctrl+D</kbd></button>
              <button role="menuitem" onClick={close(()=>{if(sc)onClipboard?.({kind:'scene',id:sc.id,label:sc.title});})}>Copy scene <kbd>Ctrl+C</kbd></button>
              <button role="menuitem" disabled={!clipboard||disabled||trackLocks.V1} onClick={close(()=>onPaste?.(ctx.sceneId))}>{clipboard?.kind==='audio'?`Paste ${clipboard.label} here`:clipboard?`Paste “${clipboard.label}” after this`:'Paste'} <kbd>Ctrl+V</kbd></button>
              <button role="menuitem" disabled={disabled||!audioClipboard||!sceneClip} onClick={close(()=>sceneClip&&pasteAudio(sceneClip.start))}>Paste copied audio at scene start</button>
              <button role="menuitem" disabled={disabled||trackLocks.V1||!sc?.shots.some(x=>x.asset?.type==='video')} onClick={close(()=>openCleanup('silence',{kind:'scene',sceneId:ctx.sceneId,source:'clips'}))}>Remove silences (jump cut)…</button>
              <button role="menuitem" disabled={disabled||trackLocks.V1||!sc?.shots.some(x=>x.asset?.type==='video')} onClick={close(()=>openCleanup('fillers',{kind:'scene',sceneId:ctx.sceneId,source:'clips'}))}>Remove filler words…</button>
              <button role="menuitem" className="danger" disabled={disabled||trackLocks.V1} onClick={close(()=>onDeleteScene?.(ctx.sceneId))}>Ripple delete scene (close gap) <kbd>Delete</kbd></button>
            </>}
            {ctx.kind==='audio'&&<>
              <button role="menuitem" disabled={!take} onClick={close(()=>{if(sc&&take)onClipboard?.({kind:'audio',id:take.id,label:`${sc.title} audio`});})}>Copy audio <kbd>Ctrl+C</kbd></button>
              <button role="menuitem" disabled={clipboard?.kind!=='audio'||disabled||trackLocks.A1} onClick={close(()=>onPaste?.(ctx.sceneId))}>{clipboard?.kind==='audio'?`Paste ${clipboard.label} here`:'Paste audio'} <kbd>Ctrl+V</kbd></button>
              <button role="menuitem" disabled={!take||disabled||trackLocks.A1||trackLocks.A3||!sceneClip} onClick={close(()=>sceneClip&&onDetachAudio?.(ctx.sceneId,'narration',sceneClip.start))}>Move narration to timeline audio (A3) to cut or trim it</button>
              <button role="menuitem" disabled={!take||disabled||trackLocks.A1||trackLocks.A3||!sceneClip} onClick={close(()=>openCleanup('silence',{kind:'scene',sceneId:ctx.sceneId,source:'narration'}))}>Move narration to timeline and remove silences…</button>
              <button role="menuitem" disabled={!take||disabled||trackLocks.A1||trackLocks.A3||!sceneClip} onClick={close(()=>openCleanup('fillers',{kind:'scene',sceneId:ctx.sceneId,source:'narration'}))}>Remove filler words from narration…</button>
              <button role="menuitem" className="danger" disabled={!take||disabled||trackLocks.A1} onClick={close(()=>onRemoveSceneAudio?.(ctx.sceneId))}>Remove narration (keep video) <kbd>Delete</kbd></button>
            </>}
            {ctx.kind==='source'&&<>
              <button role="menuitem" disabled={disabled||trackLocks.A2||trackLocks.A3||!shot} onClick={close(()=>shot&&onDetachAudio?.(ctx.sceneId,'shot',ctx.startMs||0,shot.id,ctx.durationMs))}>Detach clip sound to timeline audio (A3) to cut it</button>
              <button role="menuitem" disabled={disabled||trackLocks.A2||trackLocks.V1||!shot} onClick={close(()=>openCleanup('silence',{kind:'scene',sceneId:ctx.sceneId,source:'clips'}))}>Remove silences (jump cut)…</button>
              <button role="menuitem" disabled={disabled||trackLocks.A2||trackLocks.V1||!shot} onClick={close(()=>openCleanup('fillers',{kind:'scene',sceneId:ctx.sceneId,source:'clips'}))}>Remove filler words…</button>
              <button role="menuitem" disabled={disabled||trackLocks.A2||!shot} onClick={close(()=>shot&&onToggleClipAudio?.(shot.id,{...(shot.audio_json||{}),mute:!shot.audio_json?.mute}))}>{shot?.audio_json?.mute?'Unmute clip sound':'Mute clip sound (keep video)'}</button>
            </>}
            {ctx.kind==='clip'&&menuClip&&<>
              <button role="menuitem" disabled={disabled} onClick={close(()=>applyAudioEdit(bladeClip(projectAudio,menuClip.id,position,frameMs(project.fps)),'Audio clip split at the playhead.'))}>Split at playhead <kbd>C</kbd></button>
              <button role="menuitem" disabled={disabled} onClick={close(()=>copyAudio(ids,true))}>Cut <kbd>Ctrl+X</kbd></button>
              <button role="menuitem" onClick={close(()=>copyAudio(ids))}>Copy <kbd>Ctrl+C</kbd></button>
              <button role="menuitem" disabled={disabled||!audioClipboard} onClick={close(()=>pasteAudio(position,clipTrack(menuClip)))}>Paste at playhead on {clipTrack(menuClip)} <kbd>Ctrl+V</kbd></button>
              <button role="menuitem" disabled={disabled} onClick={close(()=>duplicateAudio(ids))}>Duplicate <kbd>Ctrl+D</kbd></button>
              {menuClip.group?<button role="menuitem" disabled={disabled} onClick={close(()=>ungroupAudio(ids))}>Ungroup <kbd>Ctrl+Shift+G</kbd></button>:<button role="menuitem" disabled={disabled||ids.length<2} onClick={close(()=>groupAudio(ids))}>Group selected clips <kbd>Ctrl+G</kbd></button>}
              <button role="menuitem" disabled={disabled} onClick={close(()=>openCleanup('silence',{kind:'clips',ids}))}>Remove silences…</button>
              <button role="menuitem" disabled={disabled} onClick={close(()=>addClipMarker(menuClip))}>Add marker on this clip (moves with it)</button>
              <button role="menuitem" disabled={disabled} onClick={close(()=>applyAudioEdit({ok:true,clips:projectAudio.map(c=>ids.includes(c.id)?{...c,mute:!menuClip.mute}:c)},menuClip.mute?'Unmuted.':'Muted.'))}>{menuClip.mute?'Unmute':'Mute'}</button>
              <span className="clip-menu-row" role="group" aria-label="Move to track">Move to {AUDIO_TRACKS.map(t=><button key={t} role="menuitem" disabled={disabled||t===clipTrack(menuClip)||trackLocks[t]} onClick={close(()=>{if(!timeline.audio_tracks.includes(t))saveTimeline({...timeline,audio_tracks:[...timeline.audio_tracks,t]});applyAudioEdit(moveClips(projectAudio,ids,0,t));})}>{t}</button>)}</span>
              <button role="menuitem" className="danger" disabled={disabled} onClick={close(()=>deleteAudio(ids))}>Delete (keep video) <kbd>Delete</kbd></button>
              <button role="menuitem" className="danger" disabled={disabled} onClick={close(()=>deleteAudio(ids,true))}>Ripple delete <kbd>Shift+Delete</kbd></button>
            </>}
          </div>;})()}
          <div className="sequence-playhead" style={{left:position/1000*scale}}><span/></div>
          <div className={`titles-track ${isCollapsed('T1')?'track-collapsed':''}`} style={collapsedStyle('T1')} aria-label="Text track">{clips.map(({scene:s,start,duration})=>{
            const caption=s.font_json.captions_enabled&&s.subtitle_text?s.subtitle_text:'';
            const blocks:{key:string;text:string;kind:'caption'|'text'|'text_box'|'text_plus';from:number;to:number;target:string}[]=[];
            const captionSegments=s.font_json.caption_segments||[];
            if(captionSegments.length){for(const segment of captionSegments)blocks.push({key:`${s.id}-caption-${segment.id}`,text:segment.text,kind:'caption',from:Math.max(0,Math.min(duration,segment.start_ms)),to:Math.max(0,Math.min(duration,segment.end_ms)),target:`caption:${segment.id}`});}
            else if(caption)blocks.push({key:`${s.id}-caption`,text:caption,kind:'caption',from:0,to:duration,target:'caption'});
            for(const layer of s.font_json.layers||[]){const from=Math.max(0,Math.min(duration,layer.start_ms||0)),to=Math.max(from+100,Math.min(duration,layer.end_ms||duration));if(to>from)blocks.push({key:layer.id,text:layer.text,kind:layer.kind||'text_plus',from,to,target:layer.id});}
            if(!blocks.length)return <button key={s.id} disabled={disabled||trackLocks.T1} className="title-clip" style={{left:start/1000*scale,width:Math.max(4,duration/1000*scale-2)}} onClick={()=>{onSelect(s.id);window.dispatchEvent(new CustomEvent('sceneforge-open-tab',{detail:{sceneId:s.id,tab:'Text'}}));}} title={`${s.title} · No text yet · click to add a caption or title`} aria-label={`${s.title}: no text yet`}><span className="lane-empty"><Type size={12}/>Add text</span></button>;
            return <React.Fragment key={s.id}>{blocks.map((block,i)=><button key={block.key} disabled={disabled||trackLocks.T1} className={`title-clip has-title text-edit-clip ${block.kind==='caption'?'caption-edit-clip':'title-edit-clip'}`} style={{left:(start+block.from)/1000*scale,width:Math.max(38,(block.to-block.from)/1000*scale-2),top:compact?1+(i%2)*13:2+(i%2)*22}} onClick={()=>{onSelect(s.id);seek(start+block.from);setTimeout(()=>window.dispatchEvent(new CustomEvent('sceneforge-open-tab',{detail:{sceneId:s.id,tab:'Text',textTarget:block.target}})),0);}} title={`${block.kind==='caption'?'Caption':block.kind==='text_plus'?'Text+':block.kind==='text_box'?'Text Box':'Text'} · ${block.text} · click to edit`} aria-label={`Edit ${block.kind==='caption'?(block.target.startsWith('caption:')?'caption segment':'caption'):block.kind==='text_plus'?'Text+':block.kind==='text_box'?'text box':'text'}: ${block.text}`}><span className={block.kind==='caption'?'lane-caption':'lane-title-text'} dir={block.kind==='caption'?(s.font_json.caption_direction||'auto'):'auto'}>{block.kind==='caption'?<Captions size={12}/>:<Type size={11}/>}<span>{block.text}</span></span></button>)}</React.Fragment>;
          })}</div>
          <div className={`picture-track ${dropTarget==="end"?"drop-target":""} ${isCollapsed('V1')?'track-collapsed':''}`} style={collapsedStyle('V1')} aria-label="Scene track" onDragOver={e=>{if(trackLocks.V1){e.preventDefault();return;}const r=e.currentTarget.getBoundingClientRect(),x=e.clientX-r.left+(scroll.current?.scrollLeft||0),ordered=[...authored].sort((a,b)=>a.start-b.start);const next=ordered.find(c=>x<(c.start+c.duration/2)/1000*scale);const prev=next?ordered[ordered.indexOf(next)-1]:ordered[ordered.length-1];const insert=next?`before:${next.scene.id}`:prev?`after:${prev.scene.id}`:'end';dragOverMedia(e,insert);}} onDragLeave={e=>{if(e.currentTarget===e.target)setDropTarget("");}} onDrop={e=>{if(trackLocks.V1){e.preventDefault();return;}const r=e.currentTarget.getBoundingClientRect(),x=e.clientX-r.left+(scroll.current?.scrollLeft||0),ordered=[...authored].sort((a,b)=>a.start-b.start);const next=ordered.find(c=>x<(c.start+c.duration/2)/1000*scale);const prev=next?ordered[ordered.indexOf(next)-1]:ordered[ordered.length-1];dropMedia(e,null,next?{before:next.scene.id}:prev?{after:prev.scene.id}:undefined);}}>
            {clips.map(({scene:s,start,duration,overlap})=><React.Fragment key={s.id}>
              <button draggable={!disabled&&!monitor&&!trackLocks.V1} disabled={disabled} onContextMenu={e=>{e.preventDefault();setFocusLane('scene');onSelect(s.id);setCtx({x:e.clientX,y:e.clientY,sceneId:s.id,kind:'scene'});}} onDragStart={e=>{if(trackLocks.V1){e.preventDefault();return;}setDrag(s.id);e.dataTransfer.effectAllowed="move";e.dataTransfer.setData("application/x-sceneforge-scene",s.id);}} onDragEnd={()=>setDrag("")} onDragOver={e=>{if(trackLocks.V1){e.preventDefault();return;}const r=e.currentTarget.getBoundingClientRect(),side=e.clientX<r.left+r.width*.22?'before':e.clientX>r.right-r.width*.22?'after':'inside';if(!dragOverMedia(e,`v:${s.id}:${side}`))e.preventDefault();}} onDragLeave={()=>setDropTarget('')} onDrop={e=>{if(trackLocks.V1){e.preventDefault();e.stopPropagation();return;}const r=e.currentTarget.getBoundingClientRect(),after=e.clientX>=r.left+r.width/2,insert=e.clientX<r.left+r.width*.22?{before:s.id}:e.clientX>r.right-r.width*.22?{after:s.id}:undefined;if(!dropMedia(e,insert?null:s.id,insert)){e.preventDefault();e.stopPropagation();drop(s.id,after);}}} className={`picture-clip ${s.id===selectedId?'selected':''} ${multi?.includes(s.id)?'multi':''} ${s.shots.length?'':'placeholder'} ${dropTarget.startsWith('v:'+s.id)?'drop-target':''}`} style={{left:start/1000*scale,width:Math.max(4,duration/1000*scale-2)}} aria-label={`Storyboard scene ${scenes.indexOf(s)+1}`} aria-current={s.id===selectedId?'true':undefined} onClick={e=>{setFocusLane('scene');if(e.ctrlKey||e.metaKey){onMulti?.(s.id,'toggle');return;}if(e.shiftKey){onMulti?.(s.id,'range');return;}onMulti?.(s.id,'clear');onSelect(s.id);seek(start);}} title={`${s.title} · ${(duration/1000).toFixed(1)}s${!s.shots.length?' · Add media':''} · Drag the whole scene to reorder; drop media near either edge to insert before/after`}>
                <div className="clip-label"><GripVertical size={12}/><strong>{s.title}</strong><small>{(duration/1000).toFixed(1)}s</small></div>
                {s.shots[0]?.asset&&s.shots[0].asset.type!=='audio'?<div className="filmstrip" data-kind={s.shots[0].asset.type} style={{backgroundImage:`url("${api.assetThumbUrl(s.shots[0].asset_id,160,s.shots[0].source_in_ms||0)}")`}}/>:s.shots.length?<div className="clip-placeholder"><Film size={22}/>Video source</div>:<div className="clip-placeholder"><Plus size={18}/>Add media</div>}
              </button>
              {!monitor&&s.shots.length>0&&s.shots.every(shot=>shot.asset?.type==='image')&&<div role="slider" tabIndex={disabled?-1:0} aria-label={`Resize ${s.title} duration`} aria-valuemin={0.5} aria-valuemax={3600} aria-valuenow={duration/1000} className="clip-duration-handle" style={{left:(start+duration)/1000*scale-9}} title="Drag to change duration; arrow keys adjust 0.1s"
                onPointerDown={e=>{if(disabled)return;e.preventDefault();e.stopPropagation();e.currentTarget.setPointerCapture?.(e.pointerId);setTrim({id:s.id,x:e.clientX,original:duration,ms:duration});}}
                onPointerMove={e=>{if(trim?.id!==s.id||!e.currentTarget.hasPointerCapture?.(e.pointerId))return;const ms=Math.max(500,Math.min(3600000,Math.round((trim.original+(e.clientX-trim.x)/scale*1000)/100)*100));setTrim({...trim,ms});}}
                onPointerUp={e=>{if(!trim||trim.id!==s.id)return;e.currentTarget.releasePointerCapture(e.pointerId);const ms=trim.ms;setTrim(null);if(ms!==trim.original)onDuration?.(s.id,ms);}}
                onPointerCancel={()=>setTrim(null)} onKeyDown={e=>{if(!disabled&&(e.key==='ArrowLeft'||e.key==='ArrowRight')){e.preventDefault();onDuration?.(s.id,Math.max(500,Math.min(3600000,duration+(e.key==='ArrowRight'?100:-100))));}}}/>} 
              {!monitor&&s.shots.length===1&&s.shots[0].asset?.type==='video'&&s.timing_mode!=='fixed'&&!s.voice_takes.some(t=>t.accepted)&&<>
                {(['in','out'] as const).map(edge=><div key={edge} role="slider" tabIndex={disabled?-1:0} aria-label={`${edge==='in'?'Trim video start':'Trim video end'} for ${s.title}`} className={`clip-video-trim-handle ${edge}`} style={{left:(edge==='in'?start:start+duration)/1000*scale-5}} title={`Drag to trim the video ${edge==='in'?'start':'end'}; source audio stays linked`}
                  onPointerDown={e=>beginShotTrim(s.id,s.shots[0],edge,e,duration)} onPointerMove={e=>moveShotTrim(s.id,s.shots[0],e)} onPointerUp={e=>finishShotTrim(s.id,s.shots[0].id,e)} onPointerCancel={()=>setTrim(null)}
                  onKeyDown={e=>{if(disabled||!(e.key==='ArrowLeft'||e.key==='ArrowRight'))return;e.preventDefault();const shot=s.shots[0],out=shot.source_out_ms??shot.asset?.duration_ms??0,delta=(e.key==='ArrowRight'?1:-1)*Math.round(1000/project.fps),si=edge==='in'?Math.max(0,shot.source_in_ms+delta):shot.source_in_ms,so=edge==='out'?Math.min(shot.asset?.duration_ms||out,out+delta):out;if(so-si>=100)onTrimShot?.(s.id,shot.id,si,so);}}/>)}
              </>}
              {overlap>0&&<button disabled={disabled} className={`clip-transition ${selectedId===s.id?'selected':''}`} style={{left:start/1000*scale,width:Math.max(20,overlap/1000*scale)}} aria-label={`Edit ${s.title} transition`} title={`${transitionLabel(s.transition_in_json.type)} · ${(overlap/1000).toFixed(2)}s (effective overlap)`} onClick={()=>{onSelect(s.id);seek(start);}}><span>⋈</span></button>}
            </React.Fragment>)}
          </div>
          <div className={`narration-track ${isCollapsed('A1')?'track-collapsed':''}`} style={collapsedStyle('A1')} aria-label="Narration track">{clips.map(({scene:s,start,duration})=>{const take=s.voice_takes.find(t=>t.accepted);return <button key={s.id} disabled={disabled||trackLocks.A1} onContextMenu={e=>{e.preventDefault();setCtx({x:e.clientX,y:e.clientY,sceneId:s.id,kind:'audio'});}} onDragOver={e=>{if(trackLocks.A1){e.preventDefault();return;}dragOverMedia(e,'a:'+s.id);}} onDragLeave={()=>setDropTarget('')} onDrop={e=>{if(trackLocks.A1){e.preventDefault();return;}dropMedia(e,s.id);}} data-scene-id={s.id} className={`narration-clip ${take?'has-take':''} ${dropTarget==='a:'+s.id?'drop-target':''}`} style={{left:start/1000*scale,width:Math.max(4,duration/1000*scale-2)}} onClick={()=>{onSelect(s.id);if(take)window.dispatchEvent(new CustomEvent('sceneforge-open-tab',{detail:{sceneId:s.id,tab:'Audio'}}));}} title={take?`${take.audio_asset?.original_filename||take.voice||'Narration'} · ${((take.effective_duration_ms??take.measured_duration_ms??0)/1000).toFixed(1)}s · click to edit, Delete to remove, drop audio to replace`:'Drop an audio file here to add sound to this scene'}><Volume2 size={13}/>{take?.audio_asset&&<NarrationWave take={take}/>}<span className="narration-label">{take?take.audio_asset?.original_filename||take.voice||'Narration':dropTarget==='a:'+s.id?'Drop to add audio':'No narration'}</span></button>})}</div>
          <div className={`source-audio-track ${isCollapsed('A2')?'track-collapsed':''}`} style={collapsedStyle('A2')} aria-label="Source clip audio track">{clips.map(({scene:s,start,duration})=>{const shots=s.shots.filter(x=>x.asset?.type==="video");const all=s.shots;const weights=all.map(x=>Math.max(1,x.duration_ms||x.asset?.duration_ms||duration/Math.max(1,all.length)));const total=weights.reduce((a,b)=>a+b,0);return shots.map(shot=>{const i=all.indexOf(shot),leftMs=duration*weights.slice(0,i).reduce((a,b)=>a+b,0)/total,widthMs=duration*weights[i]/total,sound=shot.audio_json||{};const label=shot.asset?.original_filename||s.title;return <div key={shot.id} className={sound.mute?"source-audio-clip-shell muted":"source-audio-clip-shell"} style={{left:(start+leftMs)/1000*scale,width:Math.max(4,widthMs/1000*scale-2)}}><button onContextMenu={e=>{e.preventDefault();onSelect(s.id);setCtx({x:e.clientX,y:e.clientY,sceneId:s.id,kind:'source',shotId:shot.id,startMs:start+leftMs,durationMs:widthMs});}} disabled={disabled||trackLocks.A2} className={sound.mute?"source-audio-clip has-source-audio muted":"source-audio-clip has-source-audio"} onClick={()=>{onSelect(s.id);window.dispatchEvent(new CustomEvent("sceneforge-open-tab",{detail:{sceneId:s.id,shotId:shot.id,tab:"Clip Audio"}}));}} title={`${label} · ${sound.mute?"muted":"on"} · ${sound.volume??100}% · click to edit clip sound`} aria-label={`${label} audio controls`}><Volume2 size={12}/><span>{sound.mute?"Muted":(sound.volume??100)+"%"}</span></button><button className="source-audio-mute" disabled={disabled||trackLocks.A2} aria-label={`${sound.mute?'Unmute':'Mute'} clip sound for ${label}`} title={`${sound.mute?'Unmute':'Mute'} this clip's embedded audio`} onClick={()=>onToggleClipAudio?.(shot.id,{...sound,mute:!sound.mute})}>{sound.mute?<VolumeX size={12}/>:<Volume2 size={12}/>}</button></div>})})}</div>
          {timeline.audio_tracks.map(t=>{const locked=trackLocks[t],laneClips=shownAudio.filter(c=>clipTrack(c)===t),audible=isAudioTrackAudible(timeline,t);return <div key={t} className={`project-audio-track ${dropTarget===t.toLowerCase()?'drop-target':''} ${locked?'locked':''} ${audible?'':'silent'} ${isCollapsed(t)?'track-collapsed':''}`} aria-label={t==='A3'?'Project audio timeline track':`Audio track ${t}`} data-track={t} style={{height:laneHeights[t],minHeight:laneHeights[t]}} onDragOver={e=>{if(locked){e.preventDefault();return;}dragOverMedia(e,t.toLowerCase());}} onDragLeave={()=>setDropTarget('')} onDrop={e=>{if(locked){e.preventDefault();return;}const r=e.currentTarget.getBoundingClientRect(),timeMs=Math.max(0,Math.round((e.clientX-r.left)/scale*1000/(1000/project.fps))*(1000/project.fps));dropMedia(e,null,{audioTrack:true,timeMs,track:t});}}>
            {laneClips.length===0&&<span className="project-audio-empty">{t==='A3'?'Drop MP3, WAV, M4A, AAC, OGG or FLAC here to add a movable timeline audio clip':`Drop audio here, or drag a clip up or down to move it to ${t}`}</span>}
            {laneClips.filter(c=>intersectsWindow(c.start_ms,clipEnd(c),visibleMs)||c.id===selectedAudioClipId).map(clip=>{const row=audioRows[clip.id]||0,startMs=clip.start_ms,sourceIn=clip.source_in_ms,sourceOut=clip.source_out_ms,isSelected=selectedAudioClipId===clip.id||audioSelection.includes(clip.id);return <div key={clip.id} className={`project-audio-row ${clip.group?'grouped':''} ${clip.mute?'muted':''} ${isSelected?'selected':''} ${audioDrag?.id===clip.id?'dragging':''}`} style={{top:3+row*laneRow,left:startMs/1000*scale,width:Math.max(24,(sourceOut-sourceIn)/1000*scale-2)}} role="group" aria-label={`Audio clip ${clip.name}`}>
              <span role="slider" tabIndex={disabled||locked?-1:0} aria-label={`Trim start of ${clip.name}`} aria-valuenow={sourceIn} className="project-audio-trim left" onPointerDown={e=>beginProjectAudioDrag(clip,'left',e)} onKeyDown={e=>{if(!disabled&&!locked&&(e.key==='ArrowLeft'||e.key==='ArrowRight')){e.preventDefault();applyAudioEdit(trimClip(projectAudio,clip.id,'in',(e.key==='ArrowLeft'?-1:1)*frameMs(project.fps)));}}}/>
              <button className="project-audio-body" onContextMenu={e=>{e.preventDefault();e.stopPropagation();if(!audioSelection.includes(clip.id))setAudioSelection([clip.id]);selectProjectAudio(clip.id);const rect=e.currentTarget.getBoundingClientRect();seek(startMs+Math.max(0,Math.min(1,(e.clientX-rect.left)/Math.max(1,rect.width)))*(sourceOut-sourceIn));setCtx({x:e.clientX,y:e.clientY,sceneId:selectedId,kind:'clip',clipId:clip.id});}} disabled={disabled||locked} aria-label={`Select audio clip ${clip.name}`} title={`${clip.name} · ${t} · ${TOOL_LABELS[tool][0]} tool · click to place the playhead; drag to move (up/down changes track); drag an edge to trim`} onPointerDown={e=>beginProjectAudioDrag(clip,'move',e)} onKeyDown={e=>{if(disabled||locked||!(e.key==='Delete'||e.key==='Backspace'))return;e.preventDefault();e.stopPropagation();const ids=audioSelection.includes(clip.id)?audioSelection:[clip.id];applyAudioEdit(e.shiftKey?rippleDelete(projectAudio,ids):{ok:true,clips:projectAudio.filter(c=>!ids.includes(c.id)),selected:[]},e.shiftKey?'Ripple delete: later clips on the track moved left.':'Audio clip removed.');}} onClick={e=>{if(tool==='blade'||e.ctrlKey||e.metaKey)return;selectProjectAudio(clip.id);const rect=e.currentTarget.getBoundingClientRect(),fraction=Math.max(0,Math.min(1,(e.clientX-rect.left)/Math.max(1,rect.width)));seek(startMs+fraction*(sourceOut-sourceIn));}}><Volume2 size={12}/><span>{clip.name}</span><small>{((sourceOut-sourceIn)/1000).toFixed(1)}s</small>{clip.gain?.length?<svg className="gain-line" aria-hidden="true" viewBox="0 0 100 100" preserveAspectRatio="none"><polyline points={envelopePath(clip)}/></svg>:null}</button>
              <span role="slider" tabIndex={disabled||locked?-1:0} aria-label={`Trim end of ${clip.name}`} aria-valuenow={sourceOut} className="project-audio-trim right" onPointerDown={e=>beginProjectAudioDrag(clip,'right',e)} onKeyDown={e=>{if(!disabled&&!locked&&(e.key==='ArrowLeft'||e.key==='ArrowRight')){e.preventDefault();applyAudioEdit(trimClip(projectAudio,clip.id,'out',(e.key==='ArrowLeft'?-1:1)*frameMs(project.fps)));}}}/>
            </div>})}
          </div>;})}


        </div>
      </div>
    </div>
    <footer className="sequence-status"><span>{staleExport?'EXPORT OUTDATED · Export again to include your latest changes':monitor?'LAST EXPORT · Export again after edits':'ASSEMBLY · Drag parts to reorder · Drop audio on a scene to add its sound · Drop images or videos on a scene, or after the last one'}</span><span>{scenes.some(s=>!s.shots.length)?'Empty placeholders are skipped on export · ':''}Estimated export {timecode(exportLength,project.fps)}</span></footer>
    {monitor&&exportAsset&&host&&createPortal(<div className="program-monitor"><header><strong>Last exported movie</strong><span>{staleExport?'Outdated — export again for current scenes':'Export again after edits'}</span><button title="Fullscreen movie" onClick={()=>void player.current?.requestFullscreen()}><Maximize2 size={15}/></button><button aria-label="Close movie preview" onClick={()=>{setMonitor(false);setPlaying(false);}}><X size={16}/></button></header><video ref={player} controls autoPlay src={api.assetStreamUrl(exportAsset)} onPlay={()=>setPlaying(true)} onPause={()=>setPlaying(false)} onEnded={()=>setPlaying(false)} onError={()=>setMediaError('The exported movie could not be loaded. Export again and retry.')} onTimeUpdate={e=>setPosition(e.currentTarget.currentTime*1000)}/>{mediaError&&<p role="alert">{mediaError}</p>}</div>,host)}
    {live&&!monitor&&host&&<SequencePlayer project={project} clips={authored} host={host} playing={playing} rate={liveRate} seekRequest={liveSeek} onTime={setPosition} onPlayingChange={setPlaying} onClose={()=>{setLive(false);setPlaying(false);}} onRefresh={onRefresh}/>}
  </section>;
}
