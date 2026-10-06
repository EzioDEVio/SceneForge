import {PROVIDER_NOTES, PROVIDER_OPTIONS} from "./providerCatalog";
import {FreeTimeline,seedFree} from './FreeTimeline';
import {CAMERA_MOTIONS} from './cameraMotions';
import {useSafeMenus} from "./SafeMenus";
import {ArrowUpLeft,ArrowDownLeft} from "lucide-react";
import {RouteDestination} from "./RouteArtwork";
import {InspectorSections} from "./InspectorSections";
import {draftScene,emptyEdits,mergeEdits,previousEdits,type EditorEdits} from "./editorDraft";
import {EditorDraftPreview} from "./EditorDraftPreview";
import {StoryTools,type StoryTab} from "./StoryTools";
import {TimelineTextTools,TextToolCard,LayerInspector,LayerPreview,useLayerTime,LAYER_TIME,LayerActions,LayerKind} from "./TimelineLayers";
import type {TimelineLayerClip} from "./api";
import {askConfirm} from "./dialogs";
import {registerCloseSave,saveBeforeClose} from "./closeGuard";
import {hasActiveWrites, BUILD_ID} from "./api";
import { previewFontFamily, BUNDLED_FAMILIES } from "./fonts";
import {Thumb} from "./Thumb";
import {planPoolInsert} from "./poolPlan";
import {planFileDrop, DraggedAsset, mediaKind} from "./timelineDrop";
import {LookPanel, adjustPreviewFilter, WhiteBalanceFilter, PreviewFinish, gradeKey} from "./LookPanel";
import {AudioClipEditor, removeSceneAudio} from "./AudioClipEditor";
import {FilmPreview, filmToneFilter} from "./FilmPreview";
import {FinishingPanel} from "./FinishingPanel";
import {OverlayCanvas, OverlayPanel} from "./Overlays";
import {KeyframeEditor, useScenePlayhead, withKeyframes} from "./KeyframeEditor";
import {TEXT_KEYS, keyframedPatch, textLayerAt} from "./keyframes";
import {InspectorResizer, applyInspectorWidth} from "./InspectorResizer";
import {InspectorTabs} from "./InspectorTabs";
import {FirstRunTour, ModelManager, ShortcutSheet, tourSeen} from "./HelpPanels";
import {WORKSPACES, WORKSPACE_EVENT, workspacePreset, type WorkspaceId, type WorkspacePreset} from "./workspaces";
import {AIEnginesPanel, AboutPanel} from "./InfoPanels";
import {CaptionStylePanel, CaptionPreview, AutoCaptions} from "./CaptionsPro";
import {ProgressCard} from "./ProgressCard";
import {BatchBar} from "./BatchBar";
import {ExportDialog} from "./ExportDialog";
import {ReframeProjectDialog} from "./ReframePanel";
import {TypewriterPanel} from "./TypewriterPanel";
import {TextTemplatePicker} from "./TextTemplates";
import {RestorePoints, useAutoSnapshots} from "./RestorePoints";
import {ShareDialog} from "./ShareDialog";
import VideoGenerationPanel from "./VideoGenerationPanel";
import {FeatureHelp} from "./FeatureHelp";
import {LocalEngineStarter} from "./LocalServices";
import {SubjectCutoutPanel, TexturedTitlePanel, VideoInTextPanel} from "./CreativeTools";
import {PreferencesPanel} from "./PreferencesPanel";
import {applyPreferences,readPreferences,writePreferences,type AppPreferences} from "./preferences";
import {SceneEffectsPanel, EffectsAccess, FxGroup, SceneFxPreview, RouteCanvas, AnnotationCanvas} from "./EffectsPanels";
import {EffectSettings, fxPreviewFilter, useEffectSchema} from "./EffectControls";
import {SpeedControls, ClipSoundControls} from "./SpeedControls";
import type {CaptionSegment,Overlay,ProjectAudioClip} from "./api";
import {AUDIO_TRACKS,type AudioTrackId,type TimelineSettings} from "./timeline/timeline.types";
import {CaptionSegmentsEditor} from "./CaptionSegmentsEditor";
import type {CaptionDirection} from "./CaptionSegmentsEditor";
import {sceneDuration} from "./duration";
import {TitleDesigner,TitleDesign,ANIMATIONS,ANIMATION_LABELS,TEXT_STYLES} from './TitleDesigner';
import React, { useEffect, useRef, useState } from "react";
import {
  ZoomIn, ZoomOut, Crosshair, MoreHorizontal,
  ArrowLeft, ArrowRight, ArrowUp, ArrowDown,
  Download, Play, Loader2, Trash2, X, Plus, Upload, Sparkles, Volume2,
  FileText, ImageIcon, Clock, Palette, Type, Wand2, Film, Settings, Key, Check,
  LayoutDashboard, ChevronRight, ChevronDown, Layers, Copy, PanelLeftClose, PanelLeftOpen, Search, CheckCircle2, Timer, Clapperboard, Moon, Sun,
  Package,
} from "lucide-react";
import { api, subscribeJob, Project, Scene, Shot, Job, VoiceTake, ProviderProfile, Asset, VoiceOption } from "./api";

import {MediaPool} from "./MediaPool";
import {FramingControls} from "./FramingControls";
import {EffectStack} from "./EffectStack";
import {LookPresets} from "./LookPresets";
import { ProjectTimeline, TRANSITIONS, sequenceClips } from "./ProjectTimeline";
import { CleanupPanel } from "./CleanupPanel";
import {ClipSoundVoiceIsolation} from "./VoiceIsolation";

const ASPECTS = ["16:9", "9:16", "1:1"];
const THEMES:{id:AppPreferences['theme'];label:string}[]=[
  {id:'graphite',label:'Graphite Night'},{id:'light',label:'Daylight'},
  {id:'midnight',label:'Midnight Blue'},{id:'warm',label:'Warm Studio'},
];

const MOTION_ICONS:Record<string,typeof ZoomIn>={zoom_in:ZoomIn,zoom_out:ZoomOut,close_up:Crosshair,pan_left:ArrowLeft,pan_right:ArrowRight,pan_up:ArrowUp,pan_down:ArrowDown,diagonal_up:ArrowUp,diagonal_down:ArrowDown,push_left:ZoomIn,pull_right:ZoomOut,push_right:ZoomIn,pull_left:ZoomOut,rise_left:ArrowUpLeft,drop_left:ArrowDownLeft,static:MoreHorizontal};
const MOTIONS=CAMERA_MOTIONS.map(([key,label])=>({key,label,Icon:MOTION_ICONS[key]}));

const EFFECTS: { key: string; label: string; swatch: string; group?:'filter'|'creative'|'pack'; help?:string }[] = [
  { key: "original", label: "Original", swatch: "none" },
  { key: "black_and_white", label: "B & W", swatch: "grayscale(1)" },
  { key: "sepia", label: "Sepia", swatch: "sepia(1)" },
  { key: "warm", label: "Warm", swatch: "saturate(1.3) hue-rotate(-8deg)" },
  { key: "cool", label: "Cool", swatch: "saturate(0.9) hue-rotate(12deg)" },
  { key: "vintage", label: "Vintage", swatch: "sepia(0.4) contrast(0.9) brightness(1.05)" },
  { key: "vignette", label: "Vignette", swatch: "contrast(1.1) brightness(0.9)" },
  { key: "soft_glow", label: "Soft glow", swatch: "blur(0.5px) brightness(1.15)" },
  { key: "glitch", label: "Glitch", swatch: "saturate(2) contrast(1.2) hue-rotate(15deg)" },
  { key: "film_grain", label: "Film grain", swatch: "contrast(1.08)" },
  { key: "high_contrast", label: "Punch", swatch: "contrast(1.35) saturate(1.12)" },
  { key: "faded", label: "Faded", swatch: "contrast(.8) brightness(1.07) saturate(.8)" },
  { key: "dream", label: "Dream", swatch: "blur(.6px) brightness(1.04) saturate(.8)" },
  { key: "cinematic", label: "Cinematic", swatch: "contrast(1.12) saturate(.85)" },
  { key: "noir", label: "Noir", swatch: "grayscale(1) contrast(1.45) brightness(.97)" },
  { key: "sharpen", label: "Sharpen", swatch: "contrast(1.08)" },
  { key: "negative", label: "Negative", swatch: "invert(1)" },
  { key: "vhs", label: "VHS", swatch: "saturate(1.3) contrast(1.08) hue-rotate(-6deg) blur(0.4px)" },
  { key: "glow", label: "Glow", swatch: "brightness(1.08) contrast(1.05) saturate(1.1) drop-shadow(0 0 6px rgba(255,255,255,.45))" },
  { key: "duotone", label: "Duotone", swatch: "grayscale(1) sepia(1) hue-rotate(190deg) saturate(2.2) contrast(1.1)" },
  { key: "newsprint", label: "Newspaper", swatch: "grayscale(1) contrast(1.55) sepia(0.18) brightness(1.02)" },
  { key: "old_film", label: "Old film", swatch: "sepia(0.5) contrast(1.1) brightness(0.85) saturate(0.7)" },
  { key: "teal_amber", label: "Teal & amber", swatch: "contrast(1.08) saturate(1.12) hue-rotate(7deg)" },
  { key: "pastel", label: "Pastel", swatch: "contrast(.9) brightness(1.06) saturate(.78)" },
  { key: "bleach_bypass", label: "Bleach bypass", swatch: "grayscale(.52) contrast(1.32) brightness(.98)" },
  { key: "golden_hour", label: "Golden hour", swatch: "sepia(.18) saturate(1.16) hue-rotate(-8deg) brightness(1.03)", group:'filter' },
  { key: "arctic", label: "Arctic", swatch: "saturate(.9) hue-rotate(13deg) contrast(1.04)", group:'filter' },
  { key: "portra", label: "Portra film", swatch: "sepia(.12) saturate(.92) contrast(.96) brightness(1.04)", group:'filter' },
  { key: "matte", label: "Matte fade", swatch: "contrast(.91) brightness(1.05) saturate(.87)", group:'filter' },
  { key: "pop_color", label: "Color pop", swatch: "saturate(1.34) contrast(1.12)", group:'filter' },
  { key: "teal_shadow", label: "Teal shadows", swatch: "saturate(1.05) hue-rotate(8deg) contrast(1.06)", group:'filter' },
  { key: "rose_glow", label: "Rose glow", swatch: "sepia(.12) hue-rotate(315deg) saturate(1.08) brightness(1.04)", group:'filter' },
  { key: "mono_blue", label: "Blue monochrome", swatch: "grayscale(1) sepia(.45) hue-rotate(175deg) contrast(1.08)", group:'filter' },
  { key: "chromatic_split", label: "Chromatic split", swatch: "drop-shadow(2px 0 rgba(255,40,90,.8)) drop-shadow(-2px 0 rgba(0,210,255,.8))", group:'creative', help:"Offsets color channels for energetic RGB edges. Works well on neon scenes, action shots, and music edits." },
  { key: "motion_trail", label: "Motion trail", swatch: "blur(.35px) contrast(1.14) saturate(1.12)", group:'creative', help:"Blends nearby frames to leave a soft movement trail. Best on clips with visible movement; fine details may soften." },
  { key: "print_2383", label: "2383-style print", swatch: "contrast(1.1) saturate(.9) sepia(.12) hue-rotate(-4deg)", group:'pack', help:"Film-print-style S-curve with cool shadows and warm mids (an FFmpeg curve approximation, not a measured stock emulation)." },
  { key: "tungsten_night", label: "Tungsten night", swatch: "brightness(.88) contrast(1.12) saturate(.82) hue-rotate(18deg)", group:'pack', help:"Blue-cyan night grade with deeper blacks." },
  { key: "cross_process", label: "Cross-process", swatch: "contrast(1.15) saturate(1.2) hue-rotate(-12deg)", group:'pack', help:"Crunchy slide-film-style contrast with yellow-green highlights and blue shadows." },
  { key: "halation", label: "Halation", swatch: "contrast(1.05) drop-shadow(0 0 5px rgba(255,90,40,.7))", group:'pack', help:"Red-orange glow around bright highlights, screen-blended like film halation. Strength sets how much glow." },
  { key: "focus_blur", label: "Focus blur", swatch: "blur(.8px) contrast(1.02)", group:'pack', help:"Keeps a round area sharp and blurs the rest. Set its size, position and blur below." },
  { key: "tilt_shift", label: "Tilt-shift", swatch: "blur(.6px) saturate(1.2) contrast(1.05)", group:'pack', help:"Sharp horizontal band with blurred top and bottom, for a miniature look." },
  { key: "mosaic", label: "Mosaic", swatch: "contrast(1.05) saturate(1.1)", group:'pack', help:"Pixelates the whole picture into square blocks. Choose the block size below." },
];

// Arabic-shaping-correct fonts (bundled, always render identically to
// preview): Noto Naskh/Sans Arabic. The rest are common Windows system
// fonts — they render fine for Latin text, but are NOT guaranteed to
// shape Arabic script correctly (no bundled guarantee), so Arabic
// projects should stick to the Noto options.
const FONT_FAMILIES = [...BUNDLED_FAMILIES,
  "Arial", "Calibri", "Segoe UI", "Tahoma", "Times New Roman", "Georgia", "Verdana", "Trebuchet MS",
];

function useJobProgress(jobId: string | null) {
  const [job, setJob] = useState<Job | null>(null);
  useEffect(() => {
    if (!jobId) {
      setJob(null);
      return;
    }
    let cancelled = false;
    let pollTimer: ReturnType<typeof setInterval> | null = null;

    const applyTerminalCheck = (j: Job) => {
      if (!cancelled) setJob(j);
      if (j.status === "succeeded" || j.status === "failed" || j.status === "cancelled") {
        if (pollTimer) clearInterval(pollTimer);
      }
    };

    api.getJob(jobId).then((j) => !cancelled && applyTerminalCheck(j)).catch(() => {});
    const unsub = subscribeJob(jobId, (evt) => {
      setJob((prev) => ({
        ...(prev as Job),
        id: jobId,
        status: evt.status ?? prev?.status ?? "queued",
        stage: evt.stage ?? prev?.stage ?? "",
        progress: evt.progress ?? prev?.progress ?? 0,
        error: evt.error ?? prev?.error ?? null,
      } as Job));
    });

    // Fallback polling: SSE can stall silently (browser/proxy buffering),
    // which would otherwise leave the UI frozen on a stale "queued"/"N%"
    // state forever even after the job actually finished server-side.
    // Poll the real status every 2s as a safety net regardless of
    // whether SSE is delivering events.
    pollTimer = setInterval(() => {
      api.getJob(jobId).then((j) => !cancelled && applyTerminalCheck(j)).catch(() => {});
    }, 2000);

    return () => {
      cancelled = true;
      if (pollTimer) clearInterval(pollTimer);
      unsub();
    };
  }, [jobId]);
  return job;
}

function useDrawerFocus(onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const panel = ref.current;
    panel?.focus();
    const keydown = (event: KeyboardEvent) => {
      const panels = document.querySelectorAll('[role="dialog"]');
      if (panels[panels.length - 1] !== panel) return;
      if (event.key === "Escape") {event.preventDefault(); closeRef.current();}
      if (event.key === "Tab" && panel) {
        const controls = Array.from(panel.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled):not([type="hidden"]), select:not(:disabled), textarea:not(:disabled), a[href]')).filter(el => !el.hidden && el.style.display !== "none");
        const first = controls[0], last = controls[controls.length - 1];
        if (!first) {event.preventDefault(); panel.focus();}
        else if (event.shiftKey && (document.activeElement === first || document.activeElement === panel)) {event.preventDefault(); last.focus();}
        else if (!event.shiftKey && document.activeElement === last) {event.preventDefault(); first.focus();}
      }
    };
    document.addEventListener("keydown", keydown);
    return () => {document.removeEventListener("keydown", keydown); previous?.focus();};
  }, []);
  return ref;
}

function ImageChatDrawer({
  scene, onClose, onImageAttached, onOpenSettings,
}: {
  scene: Scene; onClose: () => void; onImageAttached: () => void; onOpenSettings: () => void;
}) {
  const drawerRef = useDrawerFocus(onClose);
  const [prompt, setPrompt] = useState("");
  const [providers, setProviders] = useState<ProviderProfile[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [providerId,setProviderId] = useState("");
  const [size,setSize] = useState("1024x1024");
  const [imageCandidateCount,setImageCandidateCount]=useState<1|2|3>(1);
  const [paidImageBatchConfirmed,setPaidImageBatchConfirmed]=useState(false);
  const [imageCandidateProgress,setImageCandidateProgress]=useState(0);
  const [sd,setSd]=useState({family:'sd15',steps:30,cfg_scale:7,seed:-1,negative_prompt:'blurry, low quality, distorted, watermark, text',hires:false});
  const [history,setHistory] = useState<{id:string;prompt:string;provider:string}[]>([]);
  useEffect(()=>{api.imageHistory(scene.id).then(setHistory).catch(()=>{});},[scene.id]);
  const [generated, setGenerated] = useState<{ id: string }[]>([]);
  const [selectedGeneratedId,setSelectedGeneratedId]=useState("");
  const selectedGenerated=generated.find(item=>item.id===selectedGeneratedId)||generated[0]||null;

  useEffect(() => {
    api.listProviders().then(setProviders).catch(() => setProviders([]));
  }, []);

  const imageProvider = providers?.find((p) => p.capability === "image" && (!providerId || p.id===providerId));
  const configured = !!imageProvider;
  const [localSetup,setLocalSetup]=useState({folder:"",autostart:true});
  const [setupMessage,setSetupMessage]=useState("");
  useEffect(()=>{fetch("/api/local-image-settings").then(r=>r.ok?r.json():Promise.reject()).then(setLocalSetup).catch(()=>setSetupMessage("Could not load local engine settings."));},[]);
  const [engineStatus,setEngineStatus]=useState('');
  const [engineLog,setEngineLog]=useState<string|null>(null);
  const [startingEngine,setStartingEngine]=useState(false);
  async function engineAction(kind:'start'|'log'){
    if(!imageProvider)return;
    setStartingEngine(true);
    try{const r=await fetch(`/api/local-images/${imageProvider.id}/${kind}`,{method:kind==='start'?'POST':'GET'});const data=await r.json();if(!r.ok)throw Error(data.detail||'Engine request failed');if(kind==='log')setEngineLog(data.text);else setEngineStatus(`${data.state}: ${data.message||data.model||''}`);}catch(e){setEngineStatus(String(e));}finally{setStartingEngine(false);}
  }
  useEffect(()=>{if(imageProvider?.name!=='local_sd')return;const t=setInterval(()=>void checkEngine(),5000);return ()=>clearInterval(t)},[imageProvider?.id]);
  async function checkEngine(){
    setEngineStatus('Checking local engine…');
    try{const result=await api.localImageStatus(imageProvider!.id);setEngineStatus(result.ready?`API ready · ${result.model}`:`${result.state||'Unavailable'} · ${result.message||'Not ready'}`);}
    catch{setEngineStatus('Could not check local engine.');}
  }
  useEffect(()=>{setEngineStatus('');if(imageProvider?.name==='local_sd')void checkEngine();},[imageProvider?.id]);

  async function generate() {
    setBusy(true);
    setError(null);
    setGenerated([]);setSelectedGeneratedId("");setImageCandidateProgress(0);
    let completed=0;
    try {
      for(let i=0;i<imageCandidateCount;i++){
        setImageCandidateProgress(i+1);
        const localOptions=imageProvider?.name==='local_sd'?{...sd,seed:sd.seed<0?-1:(sd.seed+i)%4294967296}:undefined;
        const asset=await api.generateImage(scene.id,prompt,size,imageProvider?.id,localOptions);
        completed++;
        setGenerated(current=>[...current,{id:asset.id}]);
        setSelectedGeneratedId(current=>current||asset.id);
      }
      setHistory(await api.imageHistory(scene.id));
    } catch (e: any) {
      setError(completed?`Generated ${completed} of ${imageCandidateCount} images. ${e.message}`:e.message);
    } finally {
      setBusy(false);
    }
  }

  async function useImage() {
    if (!selectedGenerated) return;
    setBusy(true);setError(null);
    try {await api.addShot(scene.id, selectedGenerated.id);onImageAttached();onClose();}
    catch(e:any){setError(e.message);}finally{setBusy(false);}
  }

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className="drawer" ref={drawerRef} role="dialog" aria-modal="true" aria-label="Editor panel" tabIndex={-1} onClick={(e) => e.stopPropagation()}>
        <button className="icon-btn drawer-close" aria-label="Close panel" onClick={onClose}><X size={16}/></button>
        <h3>AI Image Studio — {scene.title}</h3>
        <p><small className="hint">
          Describe the shot you want (composition, lighting, period, people, colors).
          This thread is scoped to this part's visual brief only — it never touches
          narration or voice settings.
        </small></p>
        <div className="provider-form"><label className="control-label">Image provider<select aria-label="Image provider" value={imageProvider?.id||""} onChange={e=>setProviderId(e.target.value)}>{providers?.filter(p=>p.capability==="image").map(p=><option value={p.id} key={p.id}>{p.name} · {p.model}</option>)}</select></label><label className="control-label">Composition<select disabled={imageProvider?.name==="cloudflare"} aria-label="Image composition" value={size} onChange={e=>setSize(e.target.value)}><option value="1024x1024">Square</option><option value="1536x1024">Landscape</option><option value="1024x1536">Portrait</option></select></label></div>
        {imageProvider?.name==='local_sd'&&<fieldset className="provider-form"><legend>Local image quality</legend><details><summary>Local engine setup</summary><label>Stable Diffusion installation folder<input value={localSetup.folder} onChange={e=>setLocalSetup({...localSetup,folder:e.target.value})}/></label><label><input type="checkbox" checked={localSetup.autostart} onChange={e=>setLocalSetup({...localSetup,autostart:e.target.checked})}/>Start with SceneForge</label><p className="hint">Choose the folder containing webui-user.bat. Keep --api in its launch options. Your existing models will be reused.</p><button className="btn" disabled={startingEngine} onClick={async()=>{try{const r=await fetch('/api/local-image-settings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(localSetup)});const d=await r.json();if(!r.ok)throw Error(d.detail);setLocalSetup(d);setSetupMessage('Saved. Starting your local engine…');await engineAction('start');}catch(e:any){setSetupMessage(e.message)}}}>Save and start</button><p role="status" className="hint">{setupMessage}</p></details><div className="engine-actions"><button className="btn" disabled={startingEngine} onClick={()=>void engineAction('start')}>Start / retry engine</button><button className="btn" onClick={()=>void engineAction('log')}>View startup log</button></div>{engineLog!==null&&<div><button className="text-btn" onClick={()=>setEngineLog(null)}>Close log</button><pre className="engine-log">{engineLog}</pre></div>}<button type="button" onClick={()=>void checkEngine()}>Check engine</button><p role="status" className="hint">{engineStatus}</p>
          <label>Checkpoint family<select value={sd.family} onChange={e=>setSd({...sd,family:e.target.value})}><option value="sd15">SD 1.5 · 512 base</option><option value="sdxl">SDXL · 1024 base (requires SDXL checkpoint)</option></select></label>
          <label>Sampling steps<input type="number" min="10" max="60" value={sd.steps} onChange={e=>setSd({...sd,steps:Number(e.target.value)})}/></label>
          <label>Guidance (CFG)<input type="number" min="1" max="15" step="0.5" value={sd.cfg_scale} onChange={e=>setSd({...sd,cfg_scale:Number(e.target.value)})}/></label>
          <label>Seed (-1 random)<input type="number" min="-1" value={sd.seed} onChange={e=>setSd({...sd,seed:Number(e.target.value)})}/></label>
          <label>Negative prompt<textarea value={sd.negative_prompt} onChange={e=>setSd({...sd,negative_prompt:e.target.value})}/></label>
          <label><input type="checkbox" checked={sd.hires} onChange={e=>setSd({...sd,hires:e.target.checked})}/> High-resolution refinement · 1.5×, more VRAM</label>
          <p className="hint">Managed installation uses SD 1.5 with high-resolution refinement off. SDXL and refinement require your own WebUI/checkpoint. This menu does not install or switch models.</p>
        </fieldset>}
        {imageProvider&&<p className="hint">{PROVIDER_NOTES[imageProvider.name]}</p>}
        <textarea
          placeholder="Describe your subject, setting, composition, lighting, and style…"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />
        <div className="provider-form image-candidate-controls"><label className="control-label">Number of image options<select aria-label="Number of image options" value={imageCandidateCount} onChange={e=>{setImageCandidateCount(Number(e.target.value) as 1|2|3);setPaidImageBatchConfirmed(false);}}><option value={1}>1 image</option><option value={2}>2 images</option><option value={3}>3 images</option></select></label><p>{imageCandidateCount>1?`SceneForge makes ${imageCandidateCount} separate images; select one below. ${imageProvider?.name==='local_sd'?'Each uses another local render.':'Your provider may charge for each generated image.'}`:'Generate several options to compare before adding one to this scene.'}</p></div>
        {imageCandidateCount>1&&imageProvider?.name!=='local_sd'&&<label className="video-gen-paid-confirm image-batch-confirm"><input type="checkbox" checked={paidImageBatchConfirmed} onChange={e=>setPaidImageBatchConfirmed(e.target.checked)}/><span>I understand the provider may charge separately for each of the {imageCandidateCount} images.</span></label>}
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <button className="btn btn-primary" onClick={()=>void generate()} disabled={!configured || busy || !prompt.trim() || (imageCandidateCount>1&&imageProvider?.name!=='local_sd'&&!paidImageBatchConfirmed)}>
            {busy ? <><Loader2 size={14} className="spin" /> Generating {imageCandidateProgress} of {imageCandidateCount}…</> : <><Wand2 size={14} /> {imageCandidateCount>1?`Generate ${imageCandidateCount} images`:'Generate image'}</>}
          </button>
        </div>

        {!configured && providers !== null && (
          <div className="error-box" style={{ marginTop: 14, background: "#eef6fb", color: "#2c3e50", borderColor: "#bcdff0" }}>
            No image-generation provider is configured. This is reported honestly rather than
            faking a result.
            <div style={{ marginTop: 8 }}>
              <button className="btn" onClick={onOpenSettings}><Settings size={14} /> Open Settings</button>
            </div>
          </div>
        )}

        {error && <div className="error-box" style={{ marginTop: 14 }}>{error}</div>}

        {selectedGenerated && (
          <div style={{ marginTop: 14 }}>
            {generated.length>1&&<div className="image-candidate-grid" role="radiogroup" aria-label="Choose a generated image">{generated.map((item,index)=><button type="button" role="radio" aria-checked={item.id===selectedGenerated.id} className={item.id===selectedGenerated.id?'selected':''} key={item.id} onClick={()=>setSelectedGeneratedId(item.id)}><img src={api.assetStreamUrl(item.id)} alt={`Generated option ${index+1}`}/><span>Option {index+1}</span></button>)}</div>}
            <img src={api.assetStreamUrl(selectedGenerated.id)} alt="Selected generated image preview" style={{ width: "100%", borderRadius: 8 }} />
            <button className="btn btn-primary" style={{ marginTop: 8 }} disabled={busy} onClick={useImage}>
              <Check size={14} /> {generated.length>1?'Use selected image':'Use this image'}
            </button>
          </div>
        )}

        {!!history.length&&<section><h4>Recent generations</h4><div className="generation-history">{history.map(h=><button key={h.id} title={h.prompt} onClick={()=>{setGenerated([{id:h.id}]);setSelectedGeneratedId(h.id);setPrompt(h.prompt);}}><img src={api.assetStreamUrl(h.id)} alt={h.prompt}/><span>{h.provider}</span></button>)}</div></section>}
        <button className="btn" style={{ marginTop: 16 }} onClick={onClose}>Close</button>
      </div>
    </div>
  );
}

function SettingsPanel({ onClose, priority = false, initialTab = 'preferences', preferences, onPreferencesChange, disabled = false }: {
  onClose: () => void; priority?: boolean; initialTab?: 'preferences'|'providers'; preferences: AppPreferences;
  onPreferencesChange: (patch:Partial<AppPreferences>)=>void; disabled?:boolean;
}) {
  const drawerRef = useDrawerFocus(onClose);
  const tab=initialTab;
  const [providers,setProviders] = useState<ProviderProfile[]>([]);
  const [name,setName] = useState("openai");
  const choice = PROVIDER_OPTIONS.find(p=>p.name===name)!;
  const [key,setKey] = useState("");
  const [model,setModel] = useState(choice.model);
  const [url,setUrl] = useState(choice.url);
  const [busy,setBusy] = useState(false);
  const [message,setMessage] = useState("");
  const refresh = () => api.listProviders().then(setProviders).catch(e=>setMessage(e.message));
  useEffect(()=>{void refresh();},[]);
  const select = (value:string) => {
    const option=PROVIDER_OPTIONS.find(p=>p.name===value)!;
    const saved=providers.find(p=>p.name===value);
    setName(value);setModel(saved?.model||option.model);setUrl(saved?.base_url||option.url);setKey("");setMessage("");
  };
  async function save() {
    setBusy(true);setMessage("");
    try {await api.upsertProvider(choice.capability,name,key,model,url);setKey("");await refresh();window.dispatchEvent(new Event("sceneforge:providers-changed"));setMessage("Provider saved.");}
    catch(e:any){setMessage(e.message);}finally{setBusy(false);}
  }
  return <div className={`drawer-backdrop ${priority?'settings-front':''}`} onClick={onClose}><div className="drawer provider-studio" ref={drawerRef} role="dialog" aria-modal="true" aria-label="Editor panel" tabIndex={-1} onClick={e=>e.stopPropagation()}>
    <button className="icon-btn drawer-close" aria-label="Close panel" onClick={onClose}><X size={16}/></button>
    <h3>{tab==='preferences'?'Preferences':'AI engines · Manage providers'}</h3>
    {tab==='preferences'?<PreferencesPanel value={preferences} onChange={onPreferencesChange}/>:<>
    <p className="hint">Connect the image or video provider you want to use. Cloud API keys are protected by your operating system's credential store and are used only for your requests.</p><p className="hint">Local video generation uses ComfyUI and model files installed on this computer. Local narration engines are managed separately under Audio → Local voice engines.</p>
    <div className="provider-list">{providers.filter(p=>PROVIDER_OPTIONS.some(o=>o.name===p.name)).map(p=><article className="provider-card" key={p.id}><strong>{PROVIDER_OPTIONS.find(o=>o.name===p.name)?.label||p.name}</strong><small>{p.capability} · {p.model} · {p.masked_key||"No key required"}</small><div className="button-row"><button className="text-btn" disabled={busy} onClick={()=>select(p.name)}>Edit</button><button className="text-btn" disabled={busy} onClick={async()=>{try{await api.deleteProviderProfile(p.id);await refresh();window.dispatchEvent(new Event("sceneforge:providers-changed"));}catch(e:any){setMessage(e.message);}}}>Remove</button></div></article>)}</div>
    <fieldset disabled={busy} className="provider-form"><label className="control-label">Provider<select aria-label="Provider" value={name} onChange={e=>select(e.target.value)}>{PROVIDER_OPTIONS.map(o=><option value={o.name} key={o.name}>{o.label}</option>)}</select></label>
    <p className="hint">{PROVIDER_NOTES[name]}</p>
    {(name==="cloudflare"||name==="local_sd"||name==="elevenlabs"||name==="local_comfy")&&<label className="control-label">{name==="cloudflare"?"Cloudflare account ID":name==="elevenlabs"?"ElevenLabs API URL":"Local engine URL"}<input aria-label="Provider connection" value={url} onChange={e=>setUrl(e.target.value)}/></label>}
    <label className="control-label">Model<input disabled={name==="cloudflare"||choice.capability==="video"} aria-label="Provider model" value={model} onChange={e=>setModel(e.target.value)}/></label>

    {name!=="local_sd"&&name!=="local_comfy"&&<label className="control-label">{choice.capability==="image"?"API key (re-enter to save)":"Service token"}<input aria-label="Provider API key" type="password" autoComplete="off" value={key} onChange={e=>setKey(e.target.value)}/></label>}
    <button className="btn btn-primary" disabled={busy||(name!=="local_sd"&&name!=="local_comfy"&&!key.trim())} onClick={save}>{busy?"Saving…":"Save provider"}</button></fieldset>
    {message&&<p role="status">{message}</p>}</>}
    <button className="btn settings-close" onClick={onClose}>Close</button>
  </div></div>;
}

function VoicePanel({ scene, onChanged, beforeGenerate }: { scene: Scene; onChanged: () => void; beforeGenerate: () => Promise<boolean> }) {
  const [providers,setProviders]=useState<ProviderProfile[]>([]);
  const [providerId,setProviderId]=useState("unselected");
  const [voices,setVoices]=useState<VoiceOption[]>([]);
  const [voice,setVoice]=useState("af_heart");
  const [language,setLanguage]=useState(/[\u0600-\u06ff]/.test(scene.spoken_text)?"ar":"en");
  const [speed,setSpeed]=useState(1);
  const [localStatus,setLocalStatus]=useState("");
  async function connectEngine(engine:string) {
    setBusy(true);setErr(null);setLocalStatus("Checking local engine…");
    try {
      const result=await api.connectLocalSpeech(engine);
      setProviders(old=>[...old.filter(p=>p.id!==result.profile.id),result.profile]);
      setProviderId(result.profile.id);setVoices(result.voices.map(v=>typeof v === "string" ? {id:v,name:v} : v));setVoice(result.voices[0] || "");
      if(engine==="chatterbox"&&/[\u0600-\u06ff]/.test(scene.spoken_text))setLanguage("ar");
      if(engine==="kokoro"&&!['en','es','fr','hi','it','ja','pt','zh'].includes(language))setLanguage("en");
      setLocalStatus(result.message);
    } catch(e:any){setErr(e.message);setLocalStatus("Engine unavailable. No fallback voice was selected.");}
    finally{setBusy(false);}
  }
  const selectedEngine=providers.find(p=>p.id===providerId)?.name;
  const voicePrefix:Record<string,string>={en:"ab",es:"e",fr:"f",hi:"h",it:"i",ja:"j",pt:"p",zh:"z"};
  const availableVoices=selectedEngine==="kokoro"?voices.filter(v=>(voicePrefix[language]||"").includes(v.id[0])):voices;
  useEffect(()=>{if(availableVoices.length&&!availableVoices.some(v=>v.id===voice))setVoice(availableVoices[0].id);},[language,voices,providerId]);
  useEffect(()=>{const refreshProviders=()=>api.listProviders().then(p=>setProviders(p.filter(v=>v.capability==="speech"))).catch(()=>{});void refreshProviders();window.addEventListener("sceneforge:providers-changed",refreshProviders);return()=>window.removeEventListener("sceneforge:providers-changed",refreshProviders);},[]);
  async function connect(id:string){
    setProviderId(id);setVoices([]);setErr(null);if(providers.find(p=>p.id===id)?.name==="kokoro"&&!voicePrefix[language])setLanguage("en");
    if(!id)return;
    setBusy(true);
    try{const result=await api.providerVoices(id);const next=result.voices.map(v=>typeof v === "string" ? {id:v,name:v} : v);setVoices(next);setVoice(next[0]?.id||"");}
    catch(e:any){setErr(e.message);}finally{setBusy(false);}
  }
  const [open, setOpen] = useState(true);
  const [busy, setBusy] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function audition() {
    if(!(await beforeGenerate()))return;
    setBusy(true);
    setErr(null);
    try {
      const res = providerId ? await api.serviceTts(scene.id,providerId,voice,language,speed,true) : await api.voicePreview(scene.id, scene.spoken_text, language);
      setPreviewUrl(api.assetStreamUrl(res.asset.id));
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function generateLocalTake() {
    if(!(await beforeGenerate()))return;
    setBusy(true);
    setErr(null);
    try {
      if(providerId) await api.serviceTts(scene.id,providerId,voice,language,speed);
      else await api.localTtsTake(scene.id, language);
      onChanged();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function uploadTake(f: File) {
    setBusy(true);
    setErr(null);
    try {
      await api.uploadVoiceTake(scene.id, f);
      onChanged();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="voice-panel">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <strong style={{ display: "flex", alignItems: "center", gap: 6 }}><Volume2 size={14} /> Voice <FeatureHelp compact title="Voice and narration" description="Create narration with a chosen speech provider, use a local voice service, or upload a recording." steps="Write the script first, choose a language and engine, audition it, then generate a take and select the take to use. Local services must be installed and running."/></strong>
        <button className="btn" onClick={() => setOpen((o) => !o)}>{open ? "Hide" : "Settings / Audition"}</button>
      </div>
      {open && (
        <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
          <section className="local-voice-component"><h3>Local voice engines</h3><p className="hint">Natural speech runs on this computer after the engine and model are installed. No AI provider key is required.</p><div className="button-row"><button className="btn" disabled={busy} onClick={()=>connectEngine("chatterbox")}>Connect Chatterbox · Arabic + multilingual</button><button className="btn" disabled={busy} onClick={()=>connectEngine("kokoro")}>Connect Kokoro</button></div><p className="hint">These engines run in Docker Desktop (Linux containers) on this PC. Start one here, wait until it says it is running, then click Connect. Enter narration text before generating audio.</p><LocalEngineStarter engine="chatterbox" label="Chatterbox" onReady={()=>connectEngine("chatterbox")}/><LocalEngineStarter engine="kokoro" label="Kokoro" onReady={()=>connectEngine("kokoro")}/>{localStatus&&<p role="status">{localStatus}</p>}</section>
          <fieldset disabled={busy} className="provider-form"><label className="control-label">Narration engine<select aria-label="Narration engine" value={providerId} onChange={e=>connect(e.target.value)}><option value="unselected">Select a narration engine…</option><option value="">Diagnostic voice — robotic (espeak)</option>{providers.map(p=><option value={p.id} key={p.id}>{p.name}</option>)}</select></label>
          <label className="control-label">Language<select aria-label="Narration language" value={language} onChange={e=>setLanguage(e.target.value)}>{(selectedEngine==="kokoro"?["en","fr","es","it","pt","ja","zh","hi"]:["en","ar","fr","es","de","it","pt","ja","zh","hi","ko","ru","tr"]).map(v=><option value={v} key={v}>{{en:"English",ar:"Arabic",fr:"French",es:"Spanish",de:"German",it:"Italian",pt:"Portuguese",ja:"Japanese",zh:"Chinese",hi:"Hindi",ko:"Korean",ru:"Russian",tr:"Turkish"}[v]}</option>)}</select></label>
          {providerId&&<><label className="control-label">Voice<select aria-label="Narration voice" value={voice} onChange={e=>setVoice(e.target.value)}>{availableVoices.map(v=><option key={v.id} value={v.id}>{v.name}{[v.language,v.accent,v.gender].filter(Boolean).length?` · ${[v.language,v.accent,v.gender].filter(Boolean).join(" · ")}`:""}</option>)}</select></label><button className="text-btn" onClick={()=>connect(providerId)}>Refresh voices / test connection</button><label className="control-label">Speaking speed · {speed.toFixed(2)}×<input aria-label="Speaking speed" type="range" min={.5} max={2} step={.05} value={speed} onChange={e=>setSpeed(Number(e.target.value))}/></label></>}
          </fieldset>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button className="btn" onClick={audition} disabled={busy || !scene.spoken_text.trim() || (!!providerId&&!availableVoices.length)}>
              {providerId?"Audition natural voice":"Audition (local offline)"}
            </button>
            <button className="btn" onClick={generateLocalTake} disabled={busy || !scene.spoken_text.trim() || (!!providerId&&!availableVoices.length)}>
              {busy?"Working…":providerId?"Generate natural narration":"Generate narration (local offline)"}
            </button>
            <button className="btn" onClick={() => fileRef.current?.click()} disabled={busy}>
              Upload recorded audio
            </button>
            <button className="btn" disabled={busy || !scene.voice_takes.some(t => t.accepted)} onClick={async () => {setBusy(true); setErr(null); try {await removeSceneAudio(scene); onChanged();} catch(e:any) {setErr(e.message);} finally {setBusy(false);}}}>Use no narration</button>
            <input ref={fileRef} type="file" accept="audio/*" style={{ display: "none" }}
              onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadTake(f); }} />
          </div>
          <small className="hint">
            {!scene.spoken_text.trim() && <strong style={{display:"block"}}>Enter narration text to enable voice generation.</strong>}
            Select a local engine above. The diagnostic espeak voice is robotic and must be chosen explicitly. Narration is sent as continuous text, separately from typewriter animation.
          </small>
          {previewUrl && <audio controls src={previewUrl} style={{ width: "100%" }} />}
          {err && <div className="error-box">{err}</div>}
          {scene.voice_takes.length > 0 && (
            <div>
              <strong style={{ fontSize: 12 }}>Takes</strong>
              {scene.voice_takes.map((t: VoiceTake) => (
                <div key={t.id} className={`take-row ${t.accepted ? "accepted" : ""}`}>
                  <span>{t.provider || t.source}{t.stale ? " (stale — script changed)" : ""}</span>
                  <span>{t.measured_duration_ms ? `${(t.measured_duration_ms / 1000).toFixed(1)}s` : ""}</span>
                  {t.audio_asset && <audio controls src={api.assetStreamUrl(t.audio_asset.id)} style={{ height: 26 }} />}
                  {!t.accepted && (
                    <button className="btn" onClick={async () => { await api.selectTake(t.id); onChanged(); }}>
                      Use this take
                    </button>
                  )}
                  {t.accepted && <span>✓ selected</span>}
                  <button className="btn" disabled={busy} aria-label="Delete audio take" onClick={async()=>{if(!await askConfirm('Delete this audio take from the scene?'+(t.accepted?' The scene will have no narration until you choose another take.':'')))return;setBusy(true);setErr(null);try{await api.deleteTake(t.id);onChanged();}catch(e:any){setErr(e.message);}finally{setBusy(false);}}}>Delete</button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function TextLayers({scene,onChange,focusLayer}:{scene:Scene;onChange:(layers:NonNullable<Scene["font_json"]["layers"]>)=>void;focusLayer?:string|null}) {
  const [layers,setLayers]=useState(scene.font_json.layers||[]);
  const latest=useRef(layers);
  const change=(next:typeof layers)=>{latest.current=next;setLayers(next);onChange(next);};
  const playhead=useScenePlayhead(scene.id);
  // On keyframed layers, position/size edits change the keyframe at the playhead (keyframes.ts).
  const patch=(id:string,values:object)=>change(latest.current.map(l=>l.id===id?{...l,...keyframedPatch(l,values as any,TEXT_KEYS,textLayerAt(l,playhead) as any,playhead)}:l));
  useEffect(()=>{if(focusLayer){const card=[...document.querySelectorAll<HTMLElement>('[data-text-layer-id]')].find(el=>el.dataset.textLayerId===focusLayer);card?.scrollIntoView?.({block:'center'});card?.querySelector<HTMLTextAreaElement>('textarea')?.focus();}},[focusLayer]);
  const addLayer=(kind:'text'|'text_box'|'text_plus')=>change([...latest.current,{id:crypto.randomUUID(),kind,text:kind==='text_plus'?'Text+ title':kind==='text_box'?'Type your paragraph…':'Your title',x:50,y:25,size:64,color:'#FFFFFF',start_ms:0,end_ms:0,bold:kind!=='text',box_width:80,animation:kind==='text_plus'?'letters-pop':'none',animation_ms:800,exit_ms:0,spacing:0}]);
  return <section className="text-layers"><div className="section-heading"><h3>Text overlays</h3><span>{layers.length}/12</span><FeatureHelp compact title="Text, Text Box and Text+" description="Whole-video clips sit on upper tracks and can span scenes. Scene titles stay within one scene and offer animation and keyframes. Text is a plain title; Text Box wraps paragraphs; Text+ adds bold styling." steps="Drag a whole-video card above the video, or use Add Text below for a scene title. Select its timeline clip to edit. Apply saves a whole-video clip; render a scene to review animated scene titles."/></div><TimelineTextTools/><h4 className="scene-text-heading">Scene titles &amp; labels</h4><p className="hint">These stay inside this scene and support animations and keyframes. Start/end are scene times; end 0 means scene end. Captions follow speech separately.</p>
    {layers.map((l,i)=><article className={`layer-card kind-${l.kind||'text_plus'}`} key={l.id} data-text-layer-id={l.id}><div className="section-heading"><strong>{l.kind==='text_box'?'Text Box':l.kind==='text_plus'?'Text+':'Text'} · Layer {i+1}</strong><button className="text-btn" onClick={()=>change(latest.current.filter(v=>v.id!==l.id))}>Remove</button></div>
    <textarea aria-label={`Layer ${i+1} text`} dir="auto" value={l.text} onChange={e=>patch(l.id,{text:e.target.value})}/>
    <label className="control-label">Text tool<select aria-label={`Layer ${i+1} text tool`} value={l.kind||'text_plus'} onChange={e=>patch(l.id,{kind:e.target.value})}><option value="text">Text · simple title</option><option value="text_box">Text Box · wrapped paragraph</option><option value="text_plus">Text+ · advanced</option></select></label>
    {l.kind==='text_box'&&<label className="control-label">Text box width · {l.box_width||80}%<input aria-label={`Layer ${i+1} text box width`} type="range" min={20} max={100} value={l.box_width||80} onChange={e=>patch(l.id,{box_width:+e.target.value})}/></label>}
    <div className="layer-fields">{[{key:"x",label:"X position",max:100,step:1},{key:"y",label:"Y position",max:100,step:1},{key:"size",label:"Font size",max:200,step:1},{key:"start_ms",label:"Start (ms)",max:3600000,step:100},{key:"end_ms",label:"End (ms)",max:3600000,step:100}].map(field=>{const min=field.key==="size"?12:0;const value=Number((textLayerAt(l,playhead) as any)[field.key])||0;return <label className="control-label slider-field" key={field.key}>{field.label}<span className="slider-value">{value}</span><input type="range" min={min} max={field.max} step={field.step} value={value} onChange={e=>patch(l.id,{[field.key]:Number(e.target.value)})}/></label>})}
    <label className="control-label">Font<select value={l.family||'Noto Naskh Arabic'} onChange={e=>patch(l.id,{family:e.target.value})}>{BUNDLED_FAMILIES.map(v=><option key={v}>{v}</option>)}</select></label><label className="control-label">Alignment<select value={l.align||'center'} onChange={e=>patch(l.id,{align:e.target.value})}>{['left','center','right'].map(v=><option key={v}>{v}</option>)}</select></label>{(['outline_width','shadow','exit_ms'] as const).map(k=><label key={k} className="control-label">{k==='exit_ms'?'Exit fade (ms)':k==='shadow'?'Shadow':'Outline'}<input type="number" min={0} max={k==='exit_ms'?10000:10} value={l[k]||0} onChange={e=>patch(l.id,{[k]:Math.max(0,Math.min(k==='exit_ms'?10000:10,+e.target.value))})}/></label>)}<label className="control-label">Style<select aria-label={`Layer ${i+1} style`} value="" onChange={e=>{const st=TEXT_STYLES.find(x=>x.name===e.target.value);if(st)patch(l.id,st.values);}}><option value="">Apply a style…</option>{TEXT_STYLES.map(st=><option key={st.name} value={st.name}>{st.name}</option>)}</select></label><label className="control-label">Animation<select aria-label={`Layer ${i+1} animation`} value={l.animation||'none'} onChange={e=>patch(l.id,{animation:e.target.value})}>{ANIMATIONS.map(v=><option key={v} value={v}>{ANIMATION_LABELS[v]||v}</option>)}</select></label><label className="control-label">Letter spacing<input type="number" aria-label={`Layer ${i+1} letter spacing`} min={-5} max={40} step={1} value={l.spacing||0} onChange={e=>patch(l.id,{spacing:Math.max(-5,Math.min(40,+e.target.value||0))})}/></label>{['shine','neon'].includes(l.animation||'')&&<label className="control-label">{l.animation==='neon'?'Glow colour':'Shine colour'}<input type="color" aria-label={`Layer ${i+1} highlight colour`} value={l.highlight||'#FFD84D'} onChange={e=>patch(l.id,{highlight:e.target.value})}/></label>}<label className="control-label">Animation ms<input type="number" min={100} max={10000} defaultValue={l.animation_ms||800} onBlur={e=>patch(l.id,{animation_ms:Math.max(100,Math.min(10000,Number(e.target.value)||800))})}/></label><label className="control-label">Color<input type="color" value={l.color} onChange={e=>patch(l.id,{color:e.target.value})}/></label></div><label className="check-label"><input type="checkbox" checked={l.bold} onChange={e=>patch(l.id,{bold:e.target.checked})}/>Bold</label><KeyframeEditor sceneId={scene.id} label={`Layer ${i+1}`} startMs={l.start_ms||0} endMs={l.end_ms||sceneDuration(scene)} keyframes={l.keyframes} keys={TEXT_KEYS} current={ms=>textLayerAt(l,ms) as any} onChange={k=>change(latest.current.map(v=>v.id===l.id?withKeyframes(v,k):v))}/></article>)}
    <div className="text-add-actions">{(['text','text_box','text_plus'] as const).map(kind=><TextToolCard key={kind} kind={kind} label={kind==='text'?'Add Text':kind==='text_box'?'Add Text Box':'Add Text+'} help={kind==='text'?'Simple scene title':kind==='text_box'?'Wrapped paragraph':'Animation & keyframes'} disabled={layers.length>=12} title="Add a title inside this scene. Edit its style, animation and timing below." onClick={()=>addLayer(kind)}/>)}</div>
    <TextTemplatePicker count={layers.length} max={12} onAdd={added=>change([...latest.current,...added])}/>
  </section>;
}

type InspectorTab = "Media" | "Motion" | "Effects" | "Overlays" | "Text" | "Audio" | "Clip Audio";
const INSPECTOR_GUIDE:Record<InspectorTab,{description:string;steps:string}>={
  Media:{description:'Import and arrange still images and video clips for the selected scene. The Media Pool keeps source files available across scenes.',steps:'Import or generate media, select a thumbnail to choose it, then drag it onto the timeline or use the scene controls. Choose Fill to cover the frame or Fit to preserve the whole image.'},
  Motion:{description:'Set framing and camera movement for the selected image or video. Still-image movement is rendered as a pan or zoom; video speed controls affect playback.',steps:'Choose the media thumbnail first. Set Fill framing if movement is disabled, choose a motion preset, adjust its timing or speed, then render the scene to review it.'},
  Effects:{description:'Apply a scene look, color treatment, and effects such as film damage, spotlight, blur, annotations, or split screen.',steps:'Search the look tiles and hover to preview. Click a look to apply it, then use the effect cards below for detailed settings. Render the scene to check the final result.'},
  Overlays:{description:'Place extra image, video, emoji, or sticker layers over the scene without replacing its main media.',steps:'Choose or add an overlay. Select its row or click it in the preview to move, resize, rotate, animate, reorder, or remove it.'},
  Text:{description:'Add whole-video text clips, scene titles or captions. Whole-video clips can span scenes; scene titles support animation and keyframes; captions follow speech.',steps:'Drag a card onto an upper track, or click to add at the playhead. Use the Scene titles & labels buttons for text inside this scene. Select a clip to edit its words, timing and style.'},
  Audio:{description:'Add narration or a recording to the selected scene, manage voice takes, and adjust scene-level audio.',steps:'Enter a narration script or import a recording, choose a voice if needed, audition it, then select the take that should play. Click the A1 timeline block to return here.'},
  'Clip Audio':{description:'Control the sound embedded in the selected video clip, separately from narration.',steps:'Choose a video clip, then adjust volume, mute, narration ducking, and fade-in or fade-out. Click its A2 timeline block to open these controls.'},
};
const INSPECTOR_TABS: {name: InspectorTab; Icon: typeof Film}[] = [
  {name: "Media", Icon: ImageIcon}, {name: "Motion", Icon: Film},
  {name: "Effects", Icon: Palette}, {name: "Overlays", Icon: Layers}, {name: "Text", Icon: Type}, {name: "Audio", Icon: Volume2}, {name: "Clip Audio", Icon: Volume2},
];

function durationLabel(scene: Scene) {
  // Current length (trimmed audio + padding), not the length of the last render.
  const ms = scene.timing_mode === "fixed" ? scene.requested_duration_ms
    : scene.voice_takes.some(t => t.accepted) ? sceneDuration(scene) : scene.measured_duration_ms;
  return ms ? `${(ms / 1000).toFixed(1)}s` : "Auto";
}

// Each scene stays mounted while navigating, preserving its draft and render subscription.
// All writes for a scene run sequentially, so an older response cannot overwrite a newer edit.
function PartRow({layerActions,scene:savedScene, project, index, total, active, refresh, onMove, onDelete, onOpenSettings, onSaveState, onRecord, removeNarration, txPreview, selectedAudioClipId, onSelectAudioClip, onUpdateAudioClips}: {
  layerActions?:LayerActions;scene: Scene; project: Project; index: number; total: number; active: boolean; txPreview?: {key: string; from: string | null; to: string | null} | null;
  selectedAudioClipId?:string;onSelectAudioClip?:(id:string)=>void;onUpdateAudioClips?:(clips:ProjectAudioClip[])=>void;
  refresh: () => Promise<void>; onMove: (dir: -1 | 1) => void; onDelete: () => void;
  onOpenSettings: () => void; onSaveState: (id: string, state: string) => void; onRecord:(label:string,undo:()=>Promise<unknown>,redo:()=>Promise<unknown>)=>unknown; removeNarration:(scene:Scene)=>Promise<void>;
}) {
  const [editorEdits,setEditorEdits]=useState<EditorEdits>(emptyEdits);
  const gesture=useRef(false);
  const editsRef=useRef(editorEdits);editsRef.current=editorEdits;
  const scene=draftScene(savedScene,editorEdits);
  const hasDraft=!!Object.keys(editorEdits.scene).length||!!editorEdits.shots.length;
  function editMotionEffects(edit:Partial<EditorEdits>){const old=editsRef.current;const next=mergeEdits({...old,revision:old.revision??savedScene.revision},edit);editsRef.current=next;setEditorEdits(next);setPreviewMode("source");onSaveState(scene.id,"Draft · not saved");}
  async function saveParameters(edit:EditorEdits,label='scene settings'){
    const fresh=await api.getScene(scene.id);
    const before=previousEdits(fresh,edit);
    const after=previousEdits(draftScene(fresh,edit),edit);
    if(JSON.stringify(before)===JSON.stringify(after))return true;
    return onRecord(label,()=>api.saveEditorState(scene.id,before),()=>api.saveEditorState(scene.id,after));
  }
  async function applyEditor(){
    const next=editsRef.current;
    if(!Object.keys(next.scene).length&&!next.shots.length)return;
    const ok=await run(async()=>{const fresh=await api.getScene(scene.id);if(fresh.revision!==next.revision)throw new Error('The saved scene changed. Cancel and start from its latest settings.');const before=previousEdits(fresh,next);let first=true;const result=await onRecord('Motion and Effects',()=>api.saveEditorState(scene.id,before),async()=>{const saved=await api.saveEditorState(scene.id,first?next:{...next,revision:undefined});first=false;return saved;});if(result===false)throw new Error('Apply failed. Your draft is retained.');});
    if(ok){setEditorEdits(emptyEdits());onSaveState(scene.id,'Saved');}
  }
  function cancelEditor(){setEditorEdits(emptyEdits());setLookEpoch(x=>x+1);onSaveState(scene.id,'Saved');setError(null);}
  function draftShot(id:string,patch:Record<string,any>){editMotionEffects({shots:[{id,patch}]});}
  const [tab, setTab] = useState<InspectorTab>(() => workspacePreset(readPreferences().workspace).tab || "Media");
  useEffect(() => {const onWorkspace = (e: Event) => {const preset = (e as CustomEvent<WorkspacePreset>).detail; if (preset?.tab) setTab(preset.tab);}; window.addEventListener(WORKSPACE_EVENT, onWorkspace); return () => window.removeEventListener(WORKSPACE_EVENT, onWorkspace);}, []);
  const [textFocus,setTextFocus]=useState<string|null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [text, setText] = useState(scene.spoken_text || scene.original_text);
  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;
  const speakSeconds = wordCount / 2.5;   // natural narration pace, about 150 words a minute
  const [captions, setCaptions] = useState(scene.subtitle_text);
  const [captionSegments,setCaptionSegments]=useState<CaptionSegment[]>(scene.font_json.caption_segments||[]);
  const [draftLayers,setDraftLayers]=useState(scene.font_json.layers||[]);
  const [search, setSearch] = useState("");
  const soundRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [previewMode, setPreviewMode] = useState<"source" | "render">(scene.rendered_asset_id ? "render" : "source");
  const [selectedShotId, setSelectedShotId] = useState(scene.shots[0]?.id || "");
  const [zoom, setZoom] = useState(100);
  // Inspection zoom (magnify and pan the preview to check details); 1 = fit.
  const [safeZones, setSafeZones] = useState(false);
  const [mag, setMag] = useState(1);
  const [pan, setPan] = useState({x: 0, y: 0});
  const spaceDown = useRef(false);
  const setMagAt = (next: number, cx = 0.5, cy = 0.5) => {
    const m = Math.max(1, Math.min(4, +next.toFixed(2)));
    setPan(p => m === 1 ? {x: 0, y: 0} : {x: p.x + (cx - 0.5) * (1 / mag - 1 / m) * 100, y: p.y + (cy - 0.5) * (1 / mag - 1 / m) * 100});
    setMag(m);
  };
  useEffect(() => {
    if (!active) return;
    const onZoom = (e: Event) => {const d = (e as CustomEvent).detail; if (d === 'fit') {setMag(1); setPan({x: 0, y: 0});} else setMagAt(mag * (d > 0 ? 1.25 : 0.8));};
    const kd = (e: KeyboardEvent) => {if (e.code === 'Space') spaceDown.current = true;};
    const ku = (e: KeyboardEvent) => {if (e.code === 'Space') spaceDown.current = false;};
    window.addEventListener('sceneforge-preview-zoom', onZoom); window.addEventListener('keydown', kd); window.addEventListener('keyup', ku);
    return () => {window.removeEventListener('sceneforge-preview-zoom', onZoom); window.removeEventListener('keydown', kd); window.removeEventListener('keyup', ku);};
  }, [active, mag]);
  const fileRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const editorRef = useRef<HTMLElement>(null);
  const pending = useRef<Record<string, unknown>>({});
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const queue = useRef<Promise<boolean>>(Promise.resolve(true));
  const writes = useRef(0);
  const alive = useRef(true);
  const job = useJobProgress(jobId);
  const closeSaveRef=useRef<()=>Promise<boolean>>(async()=>false);
  closeSaveRef.current=async()=>{
    if(job&&['queued','running','cancelling'].includes(job.status))return false;
    if(hasDraft){setError("Apply or Cancel your Motion/Effects draft before leaving the project.");return false;}
    return flush();
  };
  useEffect(()=>registerCloseSave(scene.id,()=>closeSaveRef.current()),[scene.id]);
  const shot = scene.shots.find(s => s.id === selectedShotId) || scene.shots[0];
  useEffect(()=>{
    const handler=(event:Event)=>{const {sceneId,timeMs}=(event as CustomEvent).detail;if(sceneId!==scene.id)return;
      const video=videoRef.current;if(!video)return;
      const apply=()=>{video.pause();const offset=previewMode==='render'?0:(shot?.source_in_ms||0);video.currentTime=Math.max(0,Math.min(Number.isFinite(video.duration)?video.duration:Infinity,(timeMs+offset)/1000));};
      if(video.readyState>=1)apply();else video.addEventListener('loadedmetadata',apply,{once:true});
    };
    window.addEventListener('sceneforge-seek',handler);return()=>window.removeEventListener('sceneforge-seek',handler);
  },[scene.id,previewMode,shot?.id,shot?.source_in_ms]);
  const isGenerating = !!job && ["queued", "running", "cancelling"].includes(job.status);
  const rendered = scene.rendered_asset_id;
  const layerTime=useLayerTime();const [layerPlaying,setLayerPlaying]=useState(false);useEffect(()=>setLayerPlaying(false),[scene.id]);
  const sceneStart=sequenceClips(project.scenes).find(c=>c.scene.id===scene.id)?.start||0;
  function syncLayerPreviewTime(e:React.SyntheticEvent<HTMLVideoElement>){
    if(!active)return;
    const offset=previewMode==='render'?0:(shot?.source_in_ms||0);
    const local=Math.max(0,e.currentTarget.currentTime*1000-offset);
    // Native video playback updates the overlays. Paused source scrubs still follow the timeline,
    // including a held source frame when its file is shorter than the authored scene.
    if(!e.currentTarget.paused)window.dispatchEvent(new CustomEvent(LAYER_TIME,{detail:sceneStart+local}));
  }
  const selectedLayer=project.finishing_json?.layer_clips?.find(c=>c.id===layerActions?.selectedId);
  useEffect(()=>{if(active&&selectedLayer)setTab(['image','video'].includes(selectedLayer.kind)?'Media':'Text');},[active,selectedLayer?.id]);
  const kfPlayhead = useScenePlayhead(scene.id);   // keyframed text layers follow the timeline playhead
  const [renderRetry, setRenderRetry] = useState(0);
  // The scene render plays with the timeline audio and music under it; the key changes when either does.
  const previewMixKey = `${rendered}:${hashText(JSON.stringify([project.finishing_json?.audio_clips||[],project.finishing_json?.music||null,project.finishing_json?.timeline?.tracks||{},project.scenes.map(s=>[s.id,s.revision])]))}`;
  const acceptedTake = scene.voice_takes.find(t => t.accepted);
  useEffect(()=>{if(!('subtitle_text' in pending.current)){setCaptions(savedScene.subtitle_text);setCaptionSegments(savedScene.font_json.caption_segments||[]);}if(!(pending.current.font as any)?.layers)setDraftLayers(savedScene.font_json.layers||[]);},[savedScene.revision]);
  const [scriptOpen, setScriptOpen] = useState(() => {try {return localStorage.getItem("sceneforge.scriptOpen") === "1";} catch {return false;}});
  useEffect(() => {try {localStorage.setItem("sceneforge.scriptOpen", scriptOpen ? "1" : "0");} catch {/* storage unavailable */}}, [scriptOpen]);
  // Overlays are edited live (canvas drag + panel); the draft is saved with the scene.
  const [ovDraft, setOvDraft] = useState<Overlay[] | null>(null);
  const [ovSelected, setOvSelected] = useState(0);
  const [lookEpoch, setLookEpoch] = useState(0);   // bumped after a look preset apply/undo so the effect panels reload
  useEffect(() => {setOvDraft(null); setOvSelected(0);}, [scene.id]);
  const overlays = ovDraft ?? scene.overlays_json ?? [];
  const ovRef = useRef(overlays); ovRef.current = overlays;
  const [routeEditing, setRouteEditing] = useState(false);
  const [restoreNote, setRestoreNote] = useState('');
  useEffect(() => setRestoreNote(''), [scene.id]);
  useEffect(() => setRouteEditing(false), [scene.id]);   // latest overlays for drag-release saves
  const changeOverlays = (next: Overlay[], save = true) => {setOvDraft(next); if (save) draft({overlays: next});};
  // Timeline narration clicks open this scene's Audio tab.
  useEffect(() => {const open = (e: Event) => {const d = (e as CustomEvent).detail; if (d?.sceneId === scene.id && d.tab) {if(d.shotId)setSelectedShotId(d.shotId);if(d.textTarget){setTextFocus(d.textTarget);setTab(d.tab);setTimeout(()=>{const isCaption=String(d.textTarget).startsWith('caption:');const id=isCaption?String(d.textTarget).slice(8):d.textTarget;const attr=isCaption?'[data-caption-segment-id]':'[data-text-layer-id]';const card=[...(document.querySelectorAll<HTMLElement>(attr))].find(el=>(isCaption?el.dataset.captionSegmentId:el.dataset.textLayerId)===id);card?.scrollIntoView?.({block:'center'});card?.querySelector<HTMLTextAreaElement>('textarea')?.focus();},160);}else setTab(d.tab);}}; window.addEventListener('sceneforge-open-tab', open); return () => window.removeEventListener('sceneforge-open-tab', open);}, [scene.id]);
  useEffect(()=>{if(tab!=='Text'||!textFocus)return;const timer=setTimeout(()=>{if(textFocus==='caption'){const el=editorRef.current?.querySelector<HTMLTextAreaElement>('[aria-label="On-screen captions"]');el?.scrollIntoView?.({block:'center'});el?.focus();}else if(textFocus.startsWith('caption:')){const id=textFocus.slice(8);const card=[...(editorRef.current?.querySelectorAll<HTMLElement>('[data-caption-segment-id]')??[])].find(node=>node.dataset.captionSegmentId===id);card?.scrollIntoView?.({block:'center'});card?.querySelector<HTMLTextAreaElement>('textarea')?.focus();}else{const el=[...(editorRef.current?.querySelectorAll<HTMLElement>('[data-text-layer-id]')??[])].find(node=>node.dataset.textLayerId===textFocus);el?.scrollIntoView?.({block:'center'});el?.querySelector<HTMLTextAreaElement>('textarea')?.focus();}},80);return()=>clearTimeout(timer);},[tab,textFocus]);

  useEffect(() => { if (!active) editorRef.current?.querySelectorAll<HTMLMediaElement>("video, audio").forEach(media => media.pause()); }, [active]);
  useEffect(() => {
    if (job && ["succeeded", "failed", "cancelled"].includes(job.status)) {
      // Show the new render only after the project has reloaded, so the player never
      // opens the previous (or no) file and stays black.
      refresh().then(() => {if (job.status === "succeeded" && alive.current) {setRenderRetry(0); setPreviewMode("render");}}).catch(e => setError(e.message));
    }
  }, [job?.status]);
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; if (timer.current) clearTimeout(timer.current); };
  }, []);

  function run(action: () => Promise<unknown>): Promise<boolean> {
    writes.current++;
    setSaving(true); onSaveState(scene.id, "Saving…");
    const result = queue.current.then(async () => {
      try { await action(); await refresh(); return true; }
      catch (e: any) { if (alive.current) setError(e.message || "Could not save. Try again."); return false; }
    });
    queue.current = result.then(ok => {
      writes.current--;
      if (alive.current) {
        setSaving(writes.current > 0);
        onSaveState(scene.id, !ok ? "Save failed" : writes.current || Object.keys(pending.current).length ? "Saving…" : Object.keys(editsRef.current.scene).length||editsRef.current.shots.length ? "Draft · not saved" : "Saved");
      }
      return ok;
    });
    return result;
  }
  async function flush(): Promise<boolean> {
    if (timer.current) { clearTimeout(timer.current); timer.current = null; }
    const patch = pending.current;
    pending.current = {};
    if (!Object.keys(patch).length) return await queue.current;
    const ok = await run(async () => {
      const result=await saveParameters({scene:patch,shots:[]});
      if(result===false)throw new Error('Could not save the settings. Try again.');
    });
    if (!ok) pending.current = {...patch, ...pending.current};
    return ok;
  }
  function draft(patch: Record<string, unknown>) {
    if((tab==="Motion"||tab==="Effects")&&Object.keys(patch).every(k=>["look","effect_preset","effect_intensity","timing_mode","requested_duration_ms"].includes(k))){editMotionEffects({scene:patch});return;}
    pending.current = {...pending.current, ...patch,
      ...((pending.current.font||patch.font)?{font:{...(pending.current.font as object||{}),...(patch.font as object||{})}}:{}),
      ...((pending.current.look||patch.look)?{look:{...(pending.current.look as object||{}),...(patch.look as object||{})}}:{})};
    setPreviewMode("source");
    onSaveState(scene.id, "Unsaved changes");
    if (timer.current) clearTimeout(timer.current);
    if(!gesture.current)timer.current = setTimeout(() => { void flush(); }, 500);
  }
  function changeCaptionSegments(next:CaptionSegment[]) {
    setCaptionSegments(next);
    const text=next.map(segment=>segment.text.trim()).filter(Boolean).join(' ');
    setCaptions(text);
    draft({subtitle_text:text,font:{caption_segments:next}});
  }
  async function update(patch: Record<string, unknown>) {
    if(tab==="Motion"||tab==="Effects"){editMotionEffects({scene:patch});return;}
    if(gesture.current){draft(patch);return;}
    setPreviewMode("source");
    if (await flush()) await run(() => saveParameters({scene:patch,shots:[]}));
  }
  // Paste images, videos or audio from anywhere (browser, Explorer, screenshots) into this
  // scene. Text fields keep normal paste; only the active scene listens.
  useEffect(() => {
    if (!active) return;
    const onPaste = (e: ClipboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.closest('input, textarea, select, [contenteditable="true"]'))) return;
      const files = Array.from(e.clipboardData?.files || []);
      if (!files.length) return;
      e.preventDefault();
      void (async () => {
        let added = 0;
        for (const raw of files) {
          const ext = raw.type.split('/')[1]?.replace('jpeg', 'jpg').replace('quicktime', 'mov') || 'png';
          const file = raw.name && raw.name !== 'image.png' ? raw : new File([raw], `pasted-${new Date().toISOString().replace(/[:.]/g, '-')}.${ext}`, {type: raw.type});
          if (raw.type.startsWith('image/') || raw.type.startsWith('video/')) {await upload(file); added++;}
          else if (raw.type.startsWith('audio/')) {await run(async () => {await api.uploadVoiceTake(scene.id, file);}); added++;}
        }
        if (!added) setError('Only images, videos and audio can be pasted into a scene.');
      })();
    };
    window.addEventListener('paste', onPaste);
    return () => window.removeEventListener('paste', onPaste);
  }, [active, scene.id]);
  async function upload(file: File) {
    await run(async () => {
      const asset = await api.uploadAsset(project.id, file);
      const added = await api.addShot(scene.id, asset.id);
      setSelectedShotId(added.id); setPreviewMode("source");
    });
  }
  async function render() {
    setError(null);
    if (!(await flush())) return;
    if (!scene.voice_takes.some(t => t.accepted) && !(scene.font_json.typewriter_sound && scene.font_json.typewriter && scene.font_json.captions_enabled && captions.trim()) && !await askConfirm("No narration take is selected. Render this scene without narration?")) return;
    try { setJobId((await api.renderPart(scene.id)).job_id); }
    catch (e: any) { setError(e.message); }
  }
  const activeMotion = shot?.motion_json?.type || "static";
  const [hoverFx, setHoverFx] = useState<string | null>(null);   // look being previewed on hover
  useEffect(() => setHoverFx(null), [scene.id]);
  const effectSchema = useEffectSchema();   // per-effect settings (EffectControls.tsx)
  const selectedEffect = EFFECTS.find(f => f.key === (hoverFx || scene.effect_preset)) || EFFECTS[0];
  const strength = scene.effect_intensity / 100;
  const previewFilter = selectedEffect.swatch.replace(/([a-z-]+)\(([-.\d]+)([^)]*)\)/g,(_,fn,n,unit)=>{
    const base=["contrast","brightness","saturate"].includes(fn)?1:0;
    return `${fn}(${base+(Number(n)-base)*strength}${unit})`;
  });
  const liveAdjust = ((pending.current.look as any)?.adjust ?? scene.look_json?.adjust) || undefined;
  const pendingLook = (pending.current.look as any) || {};
  const liveRoute = ('route' in pendingLook ? pendingLook.route : (scene.look_json as any)?.route) || null;
  const liveAnnots = (('annotations' in pendingLook ? pendingLook.annotations : (scene.look_json as any)?.annotations) || []) as any[];
  const wbFilterId = `sf-wb-${scene.id}`;
  // With a LUT, the preview shows a server-graded frame (exact colour: LUT +
  // colour sliders), so only the look preset stays as a CSS approximation.
  const gradedSrc = (scene.look_json?.lut || (scene.look_json as any)?.tone?.amount || (scene.look_json as any)?.wheels) && shot ? api.gradedFrameUrl(scene.id, gradeKey(scene.look_json), 1280, shot.id) : null;
  const liveFilm = (pending.current.look as any)?.film !== undefined ? (pending.current.look as any).film : scene.look_json?.film;
  // "none" (the Original look) is not combinable with other CSS filter
  // functions: joined into a list it makes the whole value invalid, and the
  // browser then drops every filter. Keep only real filter functions.
  const liveFxParams = ('fx_params' in pendingLook ? pendingLook.fx_params : (scene.look_json as any)?.fx_params) || {};
  const tileFilter = (fx: {key: string; swatch: string}) => {const extra = fxPreviewFilter(effectSchema, fx.key, liveFxParams); return extra ? `${fx.swatch === "none" ? "" : fx.swatch} ${extra}`.trim() : fx.swatch;};
  const presetFilter = [previewFilter === "none" ? "" : previewFilter, fxPreviewFilter(effectSchema, selectedEffect.key, liveFxParams)].filter(Boolean).join(" ");
  const mediaFilter = [presetFilter, gradedSrc ? "" : adjustPreviewFilter(liveAdjust, wbFilterId), filmToneFilter(liveFilm)].filter(Boolean).join(' ') || undefined;
  const renderEffectTiles=(items:typeof EFFECTS)=>items.filter(fx=>fx.label.toLowerCase().includes(search.toLowerCase())).map(fx=><button key={fx.key} className={`effect-tile ${scene.effect_preset===fx.key?"selected":""}`} aria-pressed={scene.effect_preset===fx.key} onMouseEnter={()=>{setPreviewMode("source");setHoverFx(fx.key);}} onMouseLeave={()=>setHoverFx(null)} onFocus={()=>setHoverFx(fx.key)} onBlur={()=>setHoverFx(null)} onClick={()=>{setHoverFx(null);setPreviewMode("source");void update({effect_preset:fx.key});}}><div className="effect-image">{shot?.asset&&shot.asset.type!=="audio"?<img src={api.assetThumbUrl(shot.asset_id)} alt="" style={{filter:tileFilter(fx)}}/>:<div className="effect-swatch" style={{filter:tileFilter(fx)}}/>}{scene.effect_preset===fx.key&&<CheckCircle2 size={17}/>}</div><span>{fx.label}</span></button>);
  const canvasRatio = project.aspect.split(':').map(Number).reduce((a,b)=>a/b);
  async function uploadSound(file: File) {
    await run(async () => {
      const asset = await api.uploadAsset(project.id, file);
      await api.updateScene(scene.id, {font:{typewriter_sound_asset_id:asset.id,typewriter_sound:true,typewriter:true}});
    });
  }
  return (
    <section ref={editorRef} className="scene-editor" hidden={!active} aria-label={`Edit ${scene.title}`}>
      <div className="editor-main">
        <header className="scene-heading">
          <div><span className="eyebrow">SCENE {String(index + 1).padStart(2, "0")} / {String(total).padStart(2, "0")}</span><h2>{scene.title}</h2></div>
          <div className="scene-actions">
            <button className="icon-btn" title="Move scene up" aria-label="Move scene up" disabled={index === 0 || saving} onClick={() => onMove(-1)}><ArrowUp size={16}/></button>
            <button className="icon-btn" title="Move scene down" aria-label="Move scene down" disabled={index === total-1 || saving} onClick={() => onMove(1)}><ArrowDown size={16}/></button>
            <button className="icon-btn danger" title="Delete scene" aria-label="Delete scene" disabled={saving || Object.keys(pending.current).length > 0 || isGenerating} onClick={onDelete}><Trash2 size={16}/></button>
          </div>
        </header>
        <div className="preview-card">
          <div className="preview-toolbar"><div className="button-row"><button className="btn" onClick={()=>{setPreviewMode("source");editorRef.current?.querySelector<HTMLTextAreaElement>('[aria-label="Narration script"]')?.focus();}}>Edit narration</button><button className="btn" onClick={()=>{setTab("Text");setPreviewMode("source");}}>Edit captions & titles</button></div>
            <div className="segmented" aria-label="Preview mode">
              <button aria-pressed={previewMode === "source"} onClick={() => setPreviewMode("source")}>Preview</button>
              <button aria-pressed={previewMode === "render"} disabled={!rendered} onClick={() => setPreviewMode("render")}>Rendered scene</button>
            </div>
            <span className="aspect-badge">{project.aspect}</span>
          </div>
          <div className="preview-monitors"><div className={`canvas-viewport ${mag > 1 ? 'magnified' : ''}`}
            onWheel={e => {if (!e.ctrlKey) return; e.preventDefault(); const r = e.currentTarget.getBoundingClientRect(); setMagAt(mag * (e.deltaY < 0 ? 1.15 : 0.87), (e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height);}}
            onPointerDown={e => {if (mag <= 1 || !(e.button === 1 || (e.button === 0 && spaceDown.current))) return; e.preventDefault();
              const sx = e.clientX, sy = e.clientY, p0 = pan, r = e.currentTarget.getBoundingClientRect();
              const move = (ev: PointerEvent) => setPan({x: p0.x + (ev.clientX - sx) / r.width * 100 / mag, y: p0.y + (ev.clientY - sy) / r.height * 100 / mag});
              const up = () => {window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up);};
              window.addEventListener('pointermove', move); window.addEventListener('pointerup', up);}}>
            <div className="preview-canvas" style={{transform: mag > 1 ? `scale(${mag}) translate(${pan.x}%, ${pan.y}%)` : undefined, transformOrigin: "center", aspectRatio: project.aspect.replace(":", "/"), width: `min(${zoom}%, calc((var(--stage-height) - 40px) * ${canvasRatio * zoom / 100}))`}}><WhiteBalanceFilter id={wbFilterId} adjust={liveAdjust}/>{previewMode !== "render" && shot && <PreviewFinish adjust={liveAdjust}/>}{previewMode !== "render" && shot && hoverFx && hoverFx !== scene.effect_preset && <div className="hover-preview-chip" role="status">Previewing <b>{selectedEffect.label}</b> · click to apply</div>}{previewMode !== "render" && shot && liveFilm && <FilmPreview film={liveFilm}/>}{previewMode !== "render" && shot && <SceneFxPreview look={{...(scene.look_json || {}), ...((pending.current.look as any) || {})}} shots={scene.shots} filter={mediaFilter} aspect={project.width / project.height}/>}{previewMode!=="render"&&liveRoute&&<RouteDestination route={liveRoute} aspect={project.width/project.height} editing={routeEditing}/>}{previewMode !== "render" && shot && tab === "Effects" && !routeEditing && liveAnnots.length > 0 && <AnnotationCanvas annots={liveAnnots} onChange={a => draft({look: {annotations: a}})}/>}{previewMode !== "render" && shot && tab === "Effects" && routeEditing && liveRoute && <RouteCanvas route={liveRoute} onChange={r => draft({look: {route: r}})}/>}{previewMode !== "render" && shot && overlays.length > 0 && <OverlayCanvas sceneId={scene.id} overlays={overlays} frameAspect={project.width / project.height} selected={ovSelected} onSelect={i => {setOvSelected(i); setTab("Overlays");}} onChange={(i, patch, commit) => {const next = ovRef.current.map((x, k) => k === i ? {...x, ...patch} : x); ovRef.current = next; changeOverlays(next, !!commit);}} onCommit={() => draft({overlays: ovRef.current})}/>}
              {previewMode === "render" && rendered ? <video key={`${previewMixKey}:${renderRetry}`} ref={videoRef} onTimeUpdate={syncLayerPreviewTime} onPlay={()=>setLayerPlaying(true)} onPause={()=>setLayerPlaying(false)} onEnded={()=>setLayerPlaying(false)} className="canvas-media" controls preload="auto" poster={api.assetThumbUrl(rendered, 720)} src={api.scenePreviewUrl(scene.id,previewMixKey)}
                  onLoadedData={e=>{const v=e.currentTarget;if(v.paused&&v.currentTime===0){try{v.currentTime=0.001;}catch{/* not seekable yet */}}}}
                  onError={()=>{if(renderRetry<2)setTimeout(()=>setRenderRetry(n=>n+1),1200);}}/> :
                shot ? shot.asset?.type === "image" ? (shot.crop_json?<svg className="canvas-media" role="img" aria-label={`Cropped source for ${scene.title}`} viewBox={`${shot.crop_json.x*(shot.asset.width||1)} ${shot.crop_json.y*(shot.asset.height||1)} ${shot.crop_json.width*(shot.asset.width||1)} ${shot.crop_json.height*(shot.asset.height||1)}`} preserveAspectRatio={shot.fit==='cover'?'xMidYMid slice':'xMidYMid meet'} style={{filter:mediaFilter}}><image href={gradedSrc||api.assetStreamUrl(shot.asset_id)} width={shot.asset.width||1} height={shot.asset.height||1}/></svg>:<>{shot.fit === "contain_blur" && <img className="canvas-media canvas-blur-bg" aria-hidden="true" alt="" src={gradedSrc||api.assetStreamUrl(shot.asset_id)} style={{objectFit: "cover", filter: `${mediaFilter === "none" ? "" : mediaFilter} blur(14px) brightness(0.9)`}}/>}<img className="canvas-media" src={gradedSrc||api.assetStreamUrl(shot.asset_id)} alt={`Source media for ${scene.title}`} style={{objectFit: shot.fit === "cover" ? "cover" : "contain", filter:mediaFilter}}/></>) :
                  <>{shot.fit === "contain_blur" && <img className="canvas-media canvas-blur-bg" aria-hidden="true" alt="" src={gradedSrc||api.assetThumbUrl(shot.asset_id, 480)} style={{objectFit: "cover", filter: `${mediaFilter === "none" ? "" : mediaFilter} blur(14px) brightness(0.9)`}}/>}<video ref={videoRef} onTimeUpdate={syncLayerPreviewTime} onPlay={()=>setLayerPlaying(true)} onPause={()=>setLayerPlaying(false)} onEnded={()=>setLayerPlaying(false)} className="canvas-media canvas-fg" controls preload="metadata" poster={gradedSrc||undefined} src={api.assetStreamUrl(shot.asset_id)} style={{objectFit:shot.fit === "cover" ? "cover" : "contain",filter:mediaFilter}}/></> :
                  <div className="canvas-empty"><div className="empty-icon"><ImageIcon size={30}/></div><h3>Start with a visual</h3><p>Add an image or video to bring this scene to life.</p><button className="btn btn-primary" onClick={() => fileRef.current?.click()}><Plus size={15}/> Add media</button><button className="text-btn" onClick={() => setChatOpen(true)}><Sparkles size={14}/> Or generate an image</button></div>}
              {previewMode==="source"&&shot?.asset?.type==="image"&&scene.effect_preset==="glitch"&&strength>0&&<img aria-hidden="true" className="canvas-media glitch-slice glitch-full" src={api.assetStreamUrl(shot.asset_id)} alt="" style={{objectFit:shot.fit==="cover"?"cover":"contain",opacity:strength}}/>}
              {active&&txPreview&&<div className={`tx-live transition-sample sample-${txPreview.key} tx-on-canvas`} aria-hidden="true"><span>{txPreview.from?<img src={api.assetThumbUrl(txPreview.from,640)} alt=""/>:"A"}</span><span>{txPreview.to?<img src={api.assetThumbUrl(txPreview.to,640)} alt=""/>:"B"}</span><em className="tx-on-canvas-label">Previewing transition · click to apply</em></div>}{safeZones&&<div className={`safe-zones ${project.height>project.width*1.2?'portrait':'landscape'}`} aria-hidden="true"><span className="sz-top">Top controls</span><span className="sz-bottom">Captions · keep text above</span><span className="sz-right">Platform controls</span></div>}{previewMode==="source"&&shot&&<CaptionPreview font={scene.font_json as any} text={captions} projectW={project.width} projectH={project.height} time={kfPlayhead}/>}{previewMode==="source"&&shot&&(scene.font_json.layers||[]).map(l0=>textLayerAt(l0,kfPlayhead)).map(l=><div className={`canvas-text-layer kind-${l.kind||'text_plus'}`} key={l.id} dir="auto" style={{left:`${l.x}%`,top:`${l.y}%`,fontSize:`${l.size/project.width*100}cqw`,color:l.color,fontFamily:previewFontFamily(l.family||scene.font_json.family),fontWeight:l.bold?700:400,textAlign:(l.align||"center") as any,whiteSpace:'pre-wrap',overflowWrap:'anywhere',maxWidth:l.kind==='text_box'?`${l.box_width||80}%`:'95%',transform:`translate(${l.align==="left"?0:l.align==="right"?-100:-50}%,-50%)`,WebkitTextStroke:`${(l.outline_width||0)/project.width*100}cqw black`,textShadow:l.shadow?`${l.shadow/project.width*100}cqw ${l.shadow/project.width*100}cqw black`:"none",...(l.keyframes?.length?{rotate:`${l.rotation}deg`,opacity:l.opacity/100}:{})}}>{l.text}</div>)}
              {active&&<LayerPreview project={project} time={layerTime} actions={layerActions} playing={layerPlaying}/>}
            </div>
          </div>
          <div data-companion-preview data-draft-backdrop={shot?api.assetThumbUrl(shot.asset_id,960):undefined}/></div>
          <footer className="preview-footer">
            <span>{previewMode === "source" ? "Editing preview • Effects approximate; render for motion, captions & sound" : scene.is_stale ? "Previous render • Changes need a new render" : "Rendered scene"}</span>
            <label className="safe-toggle" title={project.height>project.width*1.2?"Shade the interface-covered areas in a vertical social video":"Show title-safe guides for the current canvas"}><input type="checkbox" aria-label="Show safe zones" checked={safeZones} onChange={e=>setSafeZones(e.target.checked)}/> Safe zones</label><span className="inspect-zoom" role="group" aria-label="Preview zoom"><button className="icon-reset" aria-label="Zoom out of the preview" disabled={mag <= 1} onClick={() => setMagAt(mag * 0.8)}>−</button><button className="text-btn" aria-label="Fit preview" title="Fit (Ctrl + mouse wheel zooms, middle-drag or Space + drag pans)" onClick={() => {setMag(1); setPan({x: 0, y: 0});}}>{Math.round(mag * 100)}%</button><button className="icon-reset" aria-label="Zoom into the preview" disabled={mag >= 4} onClick={() => setMagAt(mag * 1.25)}>+</button></span><label className="zoom-control">View <select aria-label="Canvas view size" value={zoom} onChange={e => setZoom(Number(e.target.value))}><option value={100}>Fit</option><option value={75}>75%</option><option value={50}>50%</option></select></label>
          </footer>
        </div>
        <div className="render-bar">
          <span className={`render-status ${scene.is_stale && rendered ? "needs-render" : ""}`}><span className="status-dot"/>{isGenerating ? `${job?.stage || "Rendering"} · ${Math.round(job?.progress || 0)}%` : !shot ? "Add media to render" : scene.is_stale && rendered ? "Changes since last render" : rendered ? "Scene ready" : "Ready for first render"}</span>
          <div className="button-row">
            {rendered && <a className="icon-btn" title="Download scene" aria-label="Download scene" href={api.assetDownloadUrl(rendered)} download><Download size={17}/></a>}
            {isGenerating ? <button className="btn" onClick={() => run(() => api.cancelJob(jobId!))}>Cancel render</button> : <button className="btn btn-primary" onClick={render} disabled={!shot}><Play size={15}/> Render scene</button>}
          </div>
        </div>
        {isGenerating && <ProgressCard title={`Rendering “${scene.title}”`} stage={job?.stage} progress={job?.progress || 0} status={job?.status} onCancel={job?.id ? () => void api.cancelJob(job.id).catch(() => {}) : undefined}/>}
        {(error || job?.status === "failed") && <div role="alert" className="error-box"><details><summary>Render/save failed — show details</summary><pre>{error || job?.error}</pre></details><button className="text-btn" onClick={()=>{setError(null);setJobId(null);}}>Dismiss</button>{error && <button className="text-btn" onClick={async () => { setError(null); await flush(); }}>Retry text save / dismiss</button>}</div>}
        <section className={`script-card ${scriptOpen ? "expanded" : ""}`} aria-label="Narration script">
          <div className="section-heading script-heading">
            <h3><FileText size={16}/> Narration script</h3>
            <span className="script-chip">{wordCount} words · ≈ {speakSeconds.toFixed(0)} s spoken</span>
            {acceptedTake ? <span className={`script-chip ${acceptedTake.stale ? "warn" : "ok"}`}>{acceptedTake.stale ? "Script changed · generate a new voice" : `Voice ${(((acceptedTake.effective_duration_ms ?? acceptedTake.measured_duration_ms) || 0) / 1000).toFixed(1)} s`}</span> : wordCount > 0 && <span className="script-chip">No voice yet</span>}
            <button className="text-btn script-expand" aria-expanded={scriptOpen} onClick={() => setScriptOpen(!scriptOpen)}>{scriptOpen ? "Collapse" : "Expand"}</button>
          </div>
          <textarea aria-label="Narration script" dir="auto" className="script-box" value={text} onChange={e => {setText(e.target.value); draft({original_text: e.target.value, spoken_text: e.target.value});}} onBlur={() => void flush()} placeholder="Tell your story. Paste or write the narration for this scene…"/>
          <div className="script-footer"><span>Saves automatically. After editing, generate a new voice so the audio matches.</span><button className="btn primary script-voice" onClick={async () => {if (await flush()) setTab("Audio");}}><Volume2 size={14}/> {acceptedTake ? "Voice & narration" : "Generate voice"} <ChevronRight size={14}/></button></div>
        </section>
      </div>
      <aside className="inspector" aria-label="Scene inspector" onPointerDownCapture={e=>{if((e.target as HTMLElement).matches('input[type="range"]')){gesture.current=true;if(timer.current)clearTimeout(timer.current);}}} onPointerUpCapture={()=>{if(gesture.current){gesture.current=false;void flush();}}} onPointerCancelCapture={()=>{gesture.current=false;void flush();}}>
        <InspectorResizer/>
        <div className="inspector-heading"><span className="eyebrow">SCENE SETTINGS · {tab.toUpperCase()}</span><span className="subtle">{durationLabel(scene)}</span><FeatureHelp title={tab} description={INSPECTOR_GUIDE[tab].description} steps={INSPECTOR_GUIDE[tab].steps}/></div>
        <InspectorTabs tabs={INSPECTOR_TABS.filter(({name})=>name!=="Clip Audio"||shot?.asset?.type==="video")} active={tab} onSelect={setTab} idPrefix={scene.id} panelId={`${scene.id}-panel`}/>
        <InspectorSections active={active} tab={tab} sceneTitle={scene.title} media={shot?scene.shots.indexOf(shot)+1:0}/>
        {(tab==="Motion"||tab==="Effects"||hasDraft)&&<EditorDraftPreview sceneId={scene.id} edits={editorEdits} dirty={hasDraft} active={active} busy={saving} onApply={()=>void applyEditor()} onCancel={cancelEditor}/>}
        <div className="inspector-body" role="tabpanel" id={`${scene.id}-panel`} aria-labelledby={`${scene.id}-${tab}-tab`}>
          {active&&layerActions&&selectedLayer&&tab===(['image','video'].includes(selectedLayer.kind)?'Media':'Text')&&<LayerInspector key={layerActions.selectedId} clip={selectedLayer} project={project} actions={layerActions} length={project.finishing_json?.free_timeline?.enabled?86400000:sequenceClips(project.scenes).reduce((n,c)=>Math.max(n,c.end),0)} onClose={()=>layerActions.onSelect('')}/>}

          {tab === "Media" && <>
            <div className="section-heading"><h3>Scene media</h3><span className="count-badge">{scene.shots.length}</span></div>
            <p className="hint">Images and clips play in the order shown.</p>
            <div className="media-grid">{scene.shots.map((s,i) => <div className={`media-item ${s.id === shot?.id ? "selected" : ""}`} key={s.id}>
              <button className="media-select" aria-label={`Select media ${i+1}`} aria-pressed={s.id === shot?.id} onClick={() => {setSelectedShotId(s.id); setPreviewMode("source");}}><Thumb assetId={s.asset_id} type={s.asset?.type}/><span>{String(i+1).padStart(2,"0")}</span></button>
              <button className="remove-media" aria-label={`Remove media ${i+1}`} disabled={false} onClick={() => run(() => api.deleteShot(s.id))}><X size={12}/></button>
            </div>)}</div>
            <button className="btn upload-btn" disabled={false} onClick={() => fileRef.current?.click()}><Upload size={16}/> Upload image or video</button>
            <button className="btn ai-btn" onClick={() => setChatOpen(true)}><Sparkles size={16}/> Generate image</button>{shot?.asset?.type==="image"&&<button className="btn" disabled={false} title="Make a cleaned-up copy: less noise, dust and scratches removed, better contrast, sharper and larger" onClick={()=>{setRestoreNote("Restoring… this can take a few seconds for large scans.");void run(async()=>{try{const restored=await api.restoreAsset(shot.asset_id);await api.addShot(scene.id,restored.id);await api.deleteShot(shot.id);setRestoreNote(`Done: “${restored.original_filename}” is now in this scene. The original is still in the Media Pool.`);window.dispatchEvent(new Event("sceneforge-media-changed"));}catch(e){setRestoreNote("");throw e;}});}}><Wand2 size={16}/> Restore old photo</button>}{restoreNote&&<p className="hint restore-note" role="status" aria-live="polite">{restoreNote}</p>}
            {shot && <label className="control-label">Frame fit<select aria-label="Frame fit" value={shot.fit} disabled={false} onChange={e => {const fit = e.currentTarget.value; setPreviewMode("source"); void run(()=>saveParameters({scene:{},shots:[{id:shot.id,patch:{fit}}]},"frame fit"));}}><option value="cover">Fill frame (crop)</option><option value="contain">Fit inside frame (show entire image)</option></select><span className="hint">Fit preserves the whole image with bars where needed. Fill crops the edges to cover the frame.</span></label>}
          </>}
          {tab === "Motion" && <>{shot&&<FramingControls key={shot.id} shot={shot} save={run} onDraft={patch=>draftShot(shot.id,patch)}/>}<h3>Camera movement</h3><p className="hint">Applied to {shot ? `media ${scene.shots.indexOf(shot)+1}` : "selected media"}. {shot?.fit !== "cover" ? "Motion requires Fill frame; Fit inside frame keeps the entire image still." : "Render to preview the movement."}</p><div className="motion-box">{MOTIONS.map(({key,label,Icon}) => <button key={key} className={`motion-btn ${activeMotion === key ? "selected" : ""}`} aria-pressed={activeMotion === key} disabled={!shot || shot.fit !== "cover"} onClick={() => draftShot(shot.id,{motion:{type:key,easing:(shot.motion_json as any)?.easing||"ease_in_out"}})}><Icon size={19}/><span>{label}</span></button>)}</div>{shot&&shot.asset?.type==="video"&&<SpeedControls key={"sp"+shot.id} shot={shot} disabled={false} save={speed=>draftShot(shot.id,{speed})}/ >}{shot&&<label className="control-label">Speed curve<select aria-label="Motion speed curve" value={(shot.motion_json as any)?.easing||"ease_in_out"} disabled={shot.fit!=="cover"} onChange={e=>{const easing=e.target.value; /* read now: the controlled select resets before the queued save runs */ draftShot(shot.id,{motion:{...(shot.motion_json||{type:"static"}),easing}});}}><option value="ease_in_out">Smooth (ease in and out)</option><option value="ease_in">Ease in (starts slow)</option><option value="ease_out">Ease out (ends slow)</option><option value="linear">Constant speed</option></select></label>}</>}
          {tab === "Effects" && <><h3>Image looks and effects</h3><EffectsAccess onNavigate={()=>setSearch("")}/><p className="hint">Preview on the canvas; click an option to apply it to this scene.</p><label className="search-control"><Search size={15}/><input type="search" aria-label="Search effects" placeholder="Search effects…" value={search} onChange={e => setSearch(e.target.value)}/></label><p className="hint looks-hint">Hover a look to preview it on the picture · click to apply</p><div className="filter-catalog"><section className="effect-category"><h4>Color filters · 8 additions</h4><p className="hint">Distinct color grades for a fast, consistent treatment.</p><div className="effects-grid">{renderEffectTiles(EFFECTS.filter(f=>f.group==='filter'))}</div></section><section className="effect-category"><h4>Creative effects · 2 additions</h4><p className="hint">Chromatic split separates color edges; Motion trail blends adjacent frames to accent movement.</p><div className="effects-grid">{renderEffectTiles(EFFECTS.filter(f=>f.group==='creative'))}</div></section><section className="effect-category"><h4>Film grades &amp; lens effects</h4><p className="hint">Film-style grades and halation are FFmpeg approximations, not stock emulations. Focus blur, Tilt-shift and Mosaic have their own settings below.</p><div className="effects-grid">{renderEffectTiles(EFFECTS.filter(f=>f.group==='pack'))}</div></section><section className="effect-category"><h4>Image looks and film treatments</h4><div className="effects-grid">{renderEffectTiles(EFFECTS.filter(f=>!f.group))}</div></section></div>{!EFFECTS.some(f => f.label.toLowerCase().includes(search.toLowerCase())) && <p className="hint">No matching image looks. Check additional effect groups below.</p>}<p className="hint">Thumbnails are approximate. Glitch tears the whole frame in bursts; choose its speed and block size below. Render to check the exact result.</p><button className="btn" disabled={!shot||isGenerating} onClick={render}><Play size={14}/> Render effect preview</button><label className="control-label">Effect strength · {scene.effect_intensity}%<input aria-label="Effect strength" type="range" min={0} max={100} step={5} disabled={scene.effect_preset==="original"} key={scene.effect_intensity} defaultValue={scene.effect_intensity} onChange={e=>draft({effect_intensity:Number(e.target.value)})} onBlur={()=>void flush()}/></label><button className="text-btn" disabled={scene.effect_preset === "original"} onClick={() => {setPreviewMode("source"); void update({effect_preset:"original"});}}>Reset to original</button><EffectSettings key={`fxp-${scene.id}-${lookEpoch}`} preset={scene.effect_preset} look={{...(scene.look_json || {}), ...pendingLook}} disabled={false} onDraft={look=>draft({look})}/><LookPanel key={`look-${lookEpoch}`} scene={scene} disabled={false} onDraft={look=>draft({look})} onSaveNow={async look=>{setPreviewMode("source");
  draft({look});
}}/><div className="fx-groups-heading"><h3><Layers size={15}/> More effects</h3><p className="hint">Open a group below, search by name, or use Quick access above.</p></div><SceneEffectsPanel key={`fx-${lookEpoch}`} scene={scene} query={search} disabled={false} onDraft={look=>draft({look})} liveRoute={liveRoute} routeEditing={routeEditing} onRouteEditing={setRouteEditing} liveAnnotations={liveAnnots} vertical={project.height>project.width*1.2} onAddMedia={() => fileRef.current?.click()}/><FxGroup id="reuse" items="Effect stack · Look presets" title="Combine & reuse looks" Icon={Package} description="Change the order effects are applied in, and save or load ready-made looks." active={0}><EffectStack look={{...(scene.look_json || {}), ...((pending.current.look as any) || {})}} disabled={false} onDraft={look=>draft({look})}/><LookPresets scene={scene} disabled={isGenerating} flush={flush} onRecord={onRecord} onDraft={patch=>editMotionEffects({scene:patch})} onApplied={()=>setLookEpoch(e=>e+1)}/></FxGroup></>}
          {tab === "Text" && <><AutoCaptions scene={scene} onDone={sc => {setCaptions(sc.subtitle_text);setCaptionSegments(sc.font_json.caption_segments||[]);void refresh();}} onStyle={f => update({font: f})}/><TextLayers key={`tl-${draftLayers.length}`} scene={{...scene,font_json:{...scene.font_json,layers:draftLayers}}} onChange={layers=>{setDraftLayers(layers);draft({font:{layers}});}} focusLayer={textFocus}/>{captionSegments.length>0?<><CaptionSegmentsEditor segments={captionSegments} onChange={changeCaptionSegments} direction={(scene.font_json.caption_direction||'auto') as CaptionDirection} onDirectionChange={direction=>void update({font:{caption_direction:direction}})} activeSegmentId={textFocus?.startsWith('caption:')?textFocus.slice(8):null} onFocusSegment={id=>setTextFocus(`caption:${id}`)}/><button className="text-btn" onClick={()=>{setCaptionSegments([]);setCaptions(text);draft({subtitle_text:text,font:{caption_segments:[]}});}}><Copy size={13}/> Copy narration to captions</button></>:<><div className="caption-manual-heading"><h3>On-screen captions</h3><label className="caption-direction-control">Direction<select aria-label="Caption text direction" value={scene.font_json.caption_direction||'auto'} onChange={e=>void update({font:{caption_direction:e.target.value}})}><option value="auto">Auto</option><option value="rtl">Right to left</option><option value="ltr">Left to right</option></select></label></div><p className="hint">Caption text is independent of narration. Add a caption here or generate timed clips above.</p><textarea aria-label="On-screen captions" dir={(scene.font_json.caption_direction||'auto') as CaptionDirection} className="caption-box" value={captions} onChange={e => {setCaptions(e.target.value); draft({subtitle_text:e.target.value,font:{caption_segments:[]}});}} onBlur={() => void flush()} placeholder="Write the text to appear on your video…"/><button className="text-btn" onClick={() => {setCaptions(text); draft({subtitle_text:text,font:{caption_segments:[]}});}}><Copy size={13}/> Copy narration to captions</button></>}<fieldset><CaptionStylePanel scene={scene} onChange={f => {if(f.typewriter&&!captions.trim()&&text.trim()){setCaptions(text);draft({subtitle_text:text});}void update({font:f});}}/></fieldset><TypewriterPanel scene={scene} captions={captions} narration={text} update={update} onCopyNarration={()=>{setCaptions(text);draft({subtitle_text:text});}} onUploadSound={()=>soundRef.current?.click()}/><p className="hint">Render text preview to see captions, titles and the typewriter (with its sound) together. Titles have their own typewriter option under the title’s Animation.</p></>}
          {tab === "Clip Audio" && shot?.asset?.type === "video" && <><ClipSoundControls key={"cs"+shot.id} shot={shot} save={audio=>{const before=shot.audio_json||{volume:100,mute:false,duck:true};void onRecord("clip sound",()=>api.updateShot(shot.id,{audio:before}),()=>api.updateShot(shot.id,{audio}));}}><ClipSoundVoiceIsolation project={project} scene={scene} shot={shot} onRecord={onRecord} onSelectAudioClip={onSelectAudioClip}/></ClipSoundControls><p className="hint">These controls affect the selected video's embedded audio track. Narration and music remain under Audio.</p></>}
          {tab === "Overlays" && <><OverlayPanel scene={scene} overlays={overlays} selected={ovSelected} onSelect={setOvSelected} onChange={changeOverlays} disabled={false}/><SubjectCutoutPanel scene={scene} disabled={isGenerating} onDone={async()=>{setOvDraft(null);await refresh();window.dispatchEvent(new Event('sceneforge-media-changed'));}}/><TexturedTitlePanel scene={scene} disabled={isGenerating} onDone={async()=>{setOvDraft(null);await refresh();}}/><VideoInTextPanel scene={scene} disabled={isGenerating} onDone={async()=>{setOvDraft(null);await refresh();}}/></>}{tab === "Audio" && <div className="audio-workspace">{acceptedTake?.audio_asset && <AudioClipEditor key={acceptedTake.id} scene={scene} take={acceptedTake} disabled={false} onChanged={refresh} onRemove={()=>void removeNarration(scene)}/>}<FinishingPanel project={project} disabled={false} onChanged={refresh} selectedClipId={selectedAudioClipId} onSelectClip={onSelectAudioClip} onUpdateAudioClips={onUpdateAudioClips}/><section className="audio-card"><h3>Voice & narration</h3><p className="hint">Connect a local speech component or upload a recording. Select a take before rendering.</p><VoicePanel scene={{...scene,spoken_text:text}} onChanged={refresh} beforeGenerate={flush}/></section></div>}
          <section className="timing-section"><h3><Clock size={15}/> Scene duration</h3><label className="control-label">Timing mode<select aria-label="Timing mode" value={scene.timing_mode} disabled={false} onChange={e => update({timing_mode:e.target.value})}><option value="audio_driven">Match narration</option><option value="fixed">Fixed duration</option></select></label>
          {scene.timing_mode === "fixed" && <label className="control-label">Seconds<input aria-label="Scene duration in seconds" type="number" min={1} max={120} step={0.5} defaultValue={(scene.requested_duration_ms || 5000)/1000} key={scene.requested_duration_ms} onBlur={e => {const v=Math.max(1,Math.min(120,Number(e.target.value)||5)); if (v*1000 !== scene.requested_duration_ms) void update({requested_duration_ms:Math.round(v*1000)});}}/></label>}
          <p className="hint">{scene.timing_mode === "fixed" ? "Narration is trimmed or padded to fit this length." : "Uses the selected narration take, including lead and trail padding."}</p></section>
        </div>
        {tab==="Text"&&<footer className="text-preview-footer"><button className="btn btn-primary" disabled={!shot||isGenerating} onClick={render}>Render text preview</button></footer>}
      </aside>
      <input ref={soundRef} type="file" accept="audio/*" hidden onChange={e=>{const f=e.target.files?.[0];if(f)void uploadSound(f);e.target.value="";}}/>
      <input ref={fileRef} type="file" accept="image/*,video/*" hidden onChange={e => {const f=e.target.files?.[0]; if(f) void upload(f); e.target.value="";}}/>
      {chatOpen && active && <ImageChatDrawer scene={scene} onClose={() => setChatOpen(false)} onImageAttached={refresh} onOpenSettings={onOpenSettings}/>}
    </section>
  );
}

function BuildNotice() {
  const [message,setMessage]=useState("");
  useEffect(()=>{api.health().then(h=>{if(h.build!==BUILD_ID)setMessage("Backend update required: this interface is connected to an older SceneForge backend, so some settings (such as LUTs) would not be saved. Close every SceneForge and start.bat window, then start SceneForge again from the newest folder.");else if(h.credential_warning)setMessage(h.credential_warning);}).catch(()=>setMessage("Cannot verify backend version. Check that the SceneForge server is running."));},[]);
  return message?<div className="error-box" role="alert">{message}</div>:null;
}
function hashText(text:string){let h=0;for(let i=0;i<text.length;i++)h=(h*31+text.charCodeAt(i))|0;return (h>>>0).toString(36);}

export default function App() {
  useSafeMenus();
  const [preferences,setPreferences]=useState<AppPreferences>(()=>readPreferences());
  useEffect(()=>{applyPreferences(preferences);},[preferences]);
  const [editorEpoch,setEditorEpoch]=useState(0);
  const [project, setProject] = useState<Project | null>(null);
  useEffect(()=>{
    document.documentElement.dataset.desktopShell=String(!!(window as any).sceneforgeDesktop);
    const mode=project?'editor':'home';
    (window as any).sceneforgeDesktop?.setWorkspaceMode?.(mode)?.catch?.(()=>{});
  },[project?.id]);
  const projectRef = useRef<Project | null>(null);
  const refreshVersion = useRef(0);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectSearch,setProjectSearch]=useState("");
  const [selectedId, setSelectedId] = useState("");
  const [selectedAudioClipId,setSelectedAudioClipId]=useState("");
  const [newTitle, setNewTitle] = useState("Untitled documentary");
  const [newAspect, setNewAspect] = useState<string>('16:9');
  const [newFps, setNewFps] = useState<number>(30);
  function updatePreferences(patch:Partial<AppPreferences>) {
    setPreferences(current=>{const next={...current,...patch};writePreferences(next);return next;});
  }
  /** Workspace presets drive the existing layout state: the inspector width and hidden
   *  class here, and (through WORKSPACE_EVENT) the inspector tab and the timeline height. */
  function applyWorkspaceLayout(preset:WorkspacePreset){
    const shell=document.querySelector<HTMLElement>('.studio-shell');if(!shell)return;
    shell.dataset.workspace=preset.id;
    if(preset.inspectorWidth)shell.dataset.inspectorPreset=String(preset.inspectorWidth);else delete shell.dataset.inspectorPreset;
    shell.classList.toggle('inspector-hidden',preset.inspectorHidden);
    applyInspectorWidth(preset.inspectorWidth);
  }
  function switchWorkspace(id:WorkspaceId){
    const preset=workspacePreset(id);
    updatePreferences({workspace:preset.id});
    applyWorkspaceLayout(preset);
    window.dispatchEvent(new CustomEvent(WORKSPACE_EVENT,{detail:preset}));
  }
  useEffect(()=>{if(!project)return;const t=setTimeout(()=>applyWorkspaceLayout(workspacePreset(readPreferences().workspace)),0);return()=>clearTimeout(t);},[project?.id]);
  const [tourOpen,setTourOpen]=useState(false);
  useEffect(()=>{if(project&&!tourSeen())setTourOpen(true);},[project?.id]);
  const appShortcut=useRef<(e:KeyboardEvent)=>void>(()=>{});
  const editorOpen=useRef(false);editorOpen.current=!!project;
  // "?" opens the keyboard shortcut sheet (not while typing or while another dialog is open).
  useEffect(()=>{const onKey=(e:KeyboardEvent)=>{if(!(e.key==='?'&&!e.ctrlKey&&!e.metaKey || e.key==='/'&&(e.ctrlKey||e.metaKey))||e.altKey||e.defaultPrevented)return;const t=e.target as HTMLElement|null;if(t?.closest('input,textarea,select,[contenteditable]:not([contenteditable="false"])'))return;if(!editorOpen.current||document.querySelector('dialog[open],[role="dialog"]'))return;e.preventDefault();setInfoPanel({panel:'shortcuts'});};window.addEventListener('keydown',onKey);return()=>window.removeEventListener('keydown',onKey);},[]);
  const [titleDraft, setTitleDraft] = useState("");
  const [exportPanel,setExportPanel]=useState(true);
  const [exportExpanded,setExportExpanded]=useState(false);
  const [mediaVersion,setMediaVersion]=useState(0);
  useEffect(()=>{const bump=()=>setMediaVersion(v=>v+1);window.addEventListener('sceneforge-media-changed',bump);return()=>window.removeEventListener('sceneforge-media-changed',bump);},[]);
  const [importStatus,setImportStatus]=useState('');
  const [importedSceneIds,setImportedSceneIds]=useState<string[]>([]);
  const [menu,setMenu]=useState('');
  const [storyTab,setStoryTab]=useState<StoryTab|null>(null);
  const [reframeOpen,setReframeOpen]=useState(false);
  const [themeMenuOpen,setThemeMenuOpen]=useState(false);
  const importRef=useRef<HTMLInputElement>(null),audioImportRef=useRef<HTMLInputElement>(null),folderRef=useRef<HTMLInputElement>(null);
  const [history,setHistory]=useState<{undo:()=>Promise<unknown>;redo:()=>Promise<unknown>;label:string}[]>([]);
  const [future,setFuture]=useState<typeof history>([]);
  async function record(label:string,undo:()=>Promise<unknown>,redo:()=>Promise<unknown>){
    if(await action(async()=>{await redo();await refresh();})){setHistory(h=>[...h.slice(-99),{undo,redo,label}]);setFuture([]);return true;}return false;
  }
  async function undoTimeline(){const item=history[history.length-1];if(item&&await action(async()=>{await item.undo();await refresh();})){setHistory(h=>h.slice(0,-1));setFuture(f=>[...f,item]);}}
  async function redoTimeline(){const item=future[future.length-1];if(item&&await action(async()=>{await item.redo();await refresh();})){setFuture(f=>f.slice(0,-1));setHistory(h=>[...h,item]);}}
  const [selectedLayerId,setSelectedLayerId]=useState('');
  useEffect(()=>setSelectedLayerId(''),[selectedId,project?.id]);
  async function updateFreeTimeline(patch:Partial<import('./api').Finishing>,label:string){
    if(!project)return false;const before=projectRef.current?.finishing_json||{};
    const write=async(value:import('./api').Finishing)=>api.updateProject(project.id,{finishing:value});
    return record(label,()=>write(before),()=>write({...before,...patch}));
  }
  async function updateLayerClips(next:TimelineLayerClip[]){
    if(!project)return false;
    const before=projectRef.current?.finishing_json?.layer_clips||[];
    if(JSON.stringify(before)===JSON.stringify(next))return true;
    const write=async(value:TimelineLayerClip[])=>api.updateProject(project.id,{finishing:{...(projectRef.current?.finishing_json||{}),layer_clips:value}});
    return await record('video, image or text clip edit',()=>write(before),()=>write(next));
  }
  async function addLayerClip(kind:LayerKind,ms:number,track:number,ids?:string[],files?:File[]){
    const current=projectRef.current;if(!current||busy)return;
    const length=current.finishing_json?.free_timeline?.enabled?86400000:sequenceClips(current.scenes).reduce((n,c)=>Math.max(n,c.end),0);
    if(length<100){setError('Add a scene first, then place video, image and text clips above it.');return;}
    let assets: {id:string;original_filename:string;type:string;duration_ms?:number|null}[]=[];
    if(kind==='image'||kind==='video'){
      if(files?.length){const images=files.filter(f=>['image','video'].includes(mediaKind(f.name)||''));if(images.length!==files.length){setError('Upper tracks accept images, videos and text. Drop audio on an audio track.');return;}
        const ok=await action(async()=>{for(const file of images)assets.push(await api.uploadAsset(current.id,file));setMediaVersion(v=>v+1);});if(!ok)return;
      }else{const pool=await api.listAssets(current.id);assets=pool.filter(a=>ids?.includes(a.id));if(!assets.length||assets.some(a=>!['image','video'].includes(a.type))){setError('Choose images or videos for the upper tracks.');return;}}
    }
    const start=Math.round(Math.max(0,Math.min(length-100,ms)));
    const added=(['image','video'].includes(kind)?assets:[null]).map((asset,i):TimelineLayerClip=>({id:crypto.randomUUID(),kind:asset?.type==='video'?'video':asset?'image':kind,name:asset?.original_filename|| (kind==='text_plus'?'Text+':kind==='text_box'?'Text box':'Text'),asset_id:asset?.id,...(asset?{}:{text:kind==='text_box'?'Your paragraph':'YOUR TITLE'}),track:Math.min(5,track+i),start_ms:start,duration_ms:Math.round(Math.min(asset?.type==='video'?(asset.duration_ms||3000):3000,length-start)),...(asset?.type==='video'?{source_in_ms:0,mute:true,volume:100}:{}),x:50,y:50,width:asset?35:65,rotation:0,opacity:100,size:kind==='text_plus'?96:72,color:'#ffffff',family:kind==='text_plus'?'Anton':'Noto Sans',align:'center'}));
    await updateLayerClips([...(projectRef.current?.finishing_json?.layer_clips||[]),...added]);
    if(added[0])setSelectedLayerId(added[0].id);
  }
  async function updateProjectAudioClips(next:ProjectAudioClip[]){
    if(!project)return;
    const before=(projectRef.current?.finishing_json||project.finishing_json||{}).audio_clips||[];
    const write=async(clips:ProjectAudioClip[])=>{const current=projectRef.current||project;await api.updateProject(project.id,{finishing:{...(current.finishing_json||{}),audio_clips:clips}});};
    if(JSON.stringify(before)===JSON.stringify(next))return;
    await record('timeline audio edit',()=>write(before),()=>write(next));
  }
  async function updateTimelineSettings(next:TimelineSettings,options?:{undoable?:boolean;label?:string}){
    if(!project)return;
    const before=(projectRef.current?.finishing_json||project.finishing_json||{}).timeline;
    const write=async(value:TimelineSettings|undefined)=>{const current=projectRef.current||project;const fin={...(current.finishing_json||{})};if(value)fin.timeline=value;else delete fin.timeline;await api.updateProject(project.id,{finishing:fin});};
    if(JSON.stringify(before)===JSON.stringify(next))return;
    if(options?.undoable)await record(options.label||'timeline change',()=>write(before),()=>write(next));
    else await action(async()=>{await write(next);await refresh();});
  }
  // Moves scene narration (A1) or a video clip's own sound (A2) onto timeline audio (A3)
  // so the user can cut it and delete only the unwanted part. One undoable step.
  // `then` (Clean up) may replace the new clip with edited pieces inside the same undo step.
  async function detachAudio(sceneId:string,source:'narration'|'shot',placeMs:number,shotId?:string,durationMs?:number,then?:(clip:ProjectAudioClip)=>Promise<ProjectAudioClip[]>){
    if(!project)return;
    const scene=project.scenes.find(s=>s.id===sceneId);if(!scene)return;
    let made:{asset:Asset;offset_ms:number}|null=null;
    if(!await action(async()=>{made=await api.detachAudio(sceneId,{source,shot_id:shotId,duration_ms:durationMs?Math.round(durationMs):undefined});}))return;
    const res=made as unknown as {asset:Asset;offset_ms:number};
    const before=(projectRef.current?.finishing_json||project.finishing_json||{}).audio_clips||[];
    const clip=projectAudioClip(res.asset,placeMs+res.offset_ms);
    const placed=then?await then(clip):[clip];
    const writeClips=async(clips:ProjectAudioClip[])=>{const current=projectRef.current||project;await api.updateProject(project.id,{finishing:{...(current.finishing_json||{}),audio_clips:clips}});};
    if(source==='narration'){
      const take=scene.voice_takes.find(t=>t.accepted);if(!take)return;
      await record('move narration to timeline audio',async()=>{await writeClips(before);await api.selectTake(take.id);await api.updateScene(scene.id,{timing_mode:scene.timing_mode,requested_duration_ms:scene.requested_duration_ms});},async()=>{await removeSceneAudio(scene);await writeClips([...before,...placed]);});
    }else{
      const shot=scene.shots.find(x=>x.id===shotId);if(!shot)return;
      const audio=shot.audio_json||{volume:100,mute:false,duck:true};
      await record('detach clip sound',async()=>{await writeClips(before);await api.updateShot(shot.id,{audio});},async()=>{await api.updateShot(shot.id,{audio:{...audio,mute:true}});await writeClips([...before,{...clip,volume:Math.max(0,Math.min(200,Number(audio.volume??100)))}]);});
    }
    setSelectedAudioClipId(clip.id);
    setImportStatus(`${source==='narration'?'Narration':'Clip sound'} moved to A3 as “${clip.name}”. Cut it with the scissors and delete only the part you don't want.`);
  }
  function projectAudioClip(asset:{id:string;original_filename:string;duration_ms?:number|null},startMs=0,track?:string):ProjectAudioClip{
    const duration=Math.max(200,Math.round(asset.duration_ms||1000));
    const clip:ProjectAudioClip={id:crypto.randomUUID(),asset_id:asset.id,name:asset.original_filename||'Audio clip',start_ms:Math.max(0,Math.round(startMs)),source_in_ms:0,source_out_ms:duration,source_duration_ms:duration,volume:100,fade_in_ms:0,fade_out_ms:0,mute:false};
    if(track&&track!=='A3'&&(AUDIO_TRACKS as readonly string[]).includes(track))clip.track=track as AudioTrackId;
    return clip;
  }
  async function addTimelineAudioAssets(assets:{id:string;original_filename:string;duration_ms?:number|null}[],startMs=0,track?:string){
    if(!project||!assets.length)return;
    const existing=(projectRef.current?.finishing_json||project.finishing_json||{}).audio_clips||[];
    const created=assets.map(asset=>projectAudioClip(asset,startMs,track));
    await updateProjectAudioClips([...existing,...created]);
    const last=created[created.length-1];if(last)setSelectedAudioClipId(last.id);
  }
  async function importMedia(files:FileList|null){
    if(!project||!files)return;setMenu('');
    setLibraryTab('Media Pool');
    await action(async()=>{let count=0;const failures:string[]=[];
      for(const file of Array.from(files)){if(!/\.(png|jpe?g|webp|gif|bmp|mp4|mov|mkv|webm|avi|mp3|wav|m4a|ogg|flac)$/i.test(file.name))continue;
        setImportStatus(`Importing ${file.name}…`);
        try{await api.uploadAsset(project.id,file);count++;}catch(e:any){failures.push(`${file.name}: ${e.message}`);}
      }
      setMediaVersion(v=>v+1);setImportStatus(`${count} file(s) imported to Media Pool. Select files to add to your timeline.`);
      if(failures.length)throw new Error(failures.join('\n'));
    });
  }
  async function addPoolAssets(assets:Asset[]){
    if(!project||!assets.length)return;
    const plan=planPoolInsert(projectRef.current?.scenes||project.scenes,assets);
    const made: {id:string;created:boolean;before:Scene|null;after:Scene|null;asset:Asset}[]=[];
    const redo=async()=>{for(let i=0;i<plan.length;i++){let item=made[i];if(item?.after){await api.restoreScene(item.id,item.after);setSelectedId(item.id);continue;}const {asset,sceneId}=plan[i];let id=sceneId||'';let before:Scene|null=null;if(sceneId)before=await api.getScene(sceneId);else id=(await api.addScene(project.id)).id;await api.updateScene(id,{title:asset.original_filename,timing_mode:'fixed',requested_duration_ms:asset.type==='video'?(asset.duration_ms||4000):4000});await api.addShot(id,asset.id);const after=await api.getScene(id);made[i]={id,created:!sceneId,before,after,asset};setSelectedId(id);}};
    const undo=async()=>{for(const item of [...made].reverse()){if(item.created)await api.deleteScene(item.id);else if(item.before)await api.restoreScene(item.id,item.before);}};
    await record('add media to timeline',undo,redo);
  }
  // Timeline drops. Audio goes to the target scene's narration lane and the
  // scene switches to "match narration" so picture and sound stay one clip.
  // Images/videos dropped on a scene are added to it; dropped after the last
  // scene they fill empty starter parts, then create new scenes.
  async function attachAudio(sceneId:string,take:()=>Promise<{id:string}>){
    const before=(projectRef.current?.scenes||project?.scenes||[]).find(s=>s.id===sceneId);if(!before)return;
    const prior=before.voice_takes.find(t=>t.accepted)?.id;let takeId='';
    await record('attach audio',async()=>{await api.clearNarration(sceneId);if(prior)await api.selectTake(prior);await api.updateScene(sceneId,{timing_mode:before.timing_mode,requested_duration_ms:before.requested_duration_ms});},async()=>{if(takeId)await api.selectTake(takeId);else{const created=await take();takeId=created.id;if(!prior)await api.selectTake(takeId);}await api.updateScene(sceneId,{timing_mode:'audio_driven'});});
  }
  async function removeNarration(scene:Scene){
    const take=scene.voice_takes.find(t=>t.accepted);if(!take)return;
    await record('remove narration',async()=>{await api.selectTake(take.id);await api.updateScene(scene.id,{timing_mode:scene.timing_mode,requested_duration_ms:scene.requested_duration_ms});},async()=>removeSceneAudio(scene));
  }
  async function placeVisuals(sceneId:string|null,assets:Asset[],insert?:{before?:string;after?:string}){
    if(!project)return;
    if(sceneId){const before=await api.getScene(sceneId);let after:Scene|null=null;await record('add media to scene',async()=>{await api.restoreScene(sceneId,before);},async()=>{if(after)await api.restoreScene(sceneId,after);else{for(const a of assets)await api.addShot(sceneId,a.id);after=await api.getScene(sceneId);}});return;}
    if(insert){
      const created:Scene[]=[];const redo=async()=>{for(let i=0;i<assets.length;i++){let scene=created[i];if(scene)await api.restoreScene(scene.id,scene);else{const made=await api.addScene(project.id);await api.updateScene(made.id,{title:assets[i].original_filename,timing_mode:'fixed',requested_duration_ms:assets[i].type==='video'?(assets[i].duration_ms||4000):4000});await api.addShot(made.id,assets[i].id);scene=await api.getScene(made.id);created[i]=scene;}setSelectedId(scene.id);}const ids=(projectRef.current?.scenes||project.scenes).map(s=>s.id).filter(id=>!created.some(c=>c.id===id));let at=insert.before?ids.indexOf(insert.before):ids.indexOf(insert.after!)+1;if(at<0)at=ids.length;ids.splice(at,0,...created.map(c=>c.id));await api.reorderScenes(project.id,ids);};
      await record('insert media in timeline',async()=>{for(const scene of [...created].reverse())await api.deleteScene(scene.id);},redo);return;
    }
    for(const {asset,sceneId:target} of planPoolInsert(projectRef.current?.scenes||project.scenes,assets)){
      const scene=target?{id:target}:await api.addScene(project.id);
      await api.updateScene(scene.id,{title:asset.original_filename,timing_mode:'fixed',requested_duration_ms:asset.type==='video'?(asset.duration_ms||4000):4000});
      await api.addShot(scene.id,asset.id);setSelectedId(scene.id);
    }
  }
  async function addGeneratedVideoToTimeline(assetId:string,placement:'after'|'inside'){
    if(!project)throw new Error('Open a project before adding generated video.');
    const asset=await api.getAsset(assetId);const target=selected?.id||null;
    if(placement==='inside'&&target)await placeVisuals(target,[asset]);
    else if(placement==='after'&&target)await placeVisuals(null,[asset],{after:target});
    else await addPoolAssets([asset]);
    const latest=await api.getProject(project.id);projectRef.current=latest;setProject(latest);setMediaVersion(v=>v+1);setLibraryTab('Scenes');
    window.dispatchEvent(new Event('sceneforge-media-changed'));
    const inserted=latest.scenes.find(s=>s.shots.some(shot=>shot.asset_id===assetId));
    if(inserted)setSelectedId(inserted.id);
    return inserted?.id;
  }
  async function captionGeneratedScene(sceneId:string){
    if(!project)throw new Error('Open a project before generating captions.');
    await api.autoCaptions(sceneId,{provider:'auto'});
    const latest=await api.getProject(project.id);projectRef.current=latest;setProject(latest);setSelectedId(sceneId);
    window.dispatchEvent(new CustomEvent('sceneforge-open-tab',{detail:{sceneId,tab:'Text'}}));
  }
  async function dropFilesOnTimeline(sceneId:string|null,files:File[],insert?:{before?:string;after?:string;audioTrack?:boolean;timeMs?:number;track?:string}){
    if(!project)return;
    if(insert?.audioTrack){
      const audioFiles=files.filter(file=>mediaKind(file.name)==='audio'),unsupported=files.filter(file=>mediaKind(file.name)!=='audio').map(file=>file.name),uploaded:Asset[]=[];
      await action(async()=>{for(const file of audioFiles){setImportStatus(`Importing ${file.name}…`);try{uploaded.push(await api.uploadAsset(project.id,file));}catch(e:any){unsupported.push(`${file.name}: ${e.message}`);}}setMediaVersion(v=>v+1);});
      if(uploaded.length){await addTimelineAudioAssets(uploaded,insert.timeMs||0,insert.track);setImportStatus(`${uploaded.length} audio clip${uploaded.length===1?'':'s'} added to ${insert.track||'A3'}. Drag to move; drag an edge to trim.${unsupported.length?` Skipped: ${unsupported.slice(0,3).join(', ')}.`:''}`);}
      else setImportStatus(unsupported.length?`No audio clips added. Skipped: ${unsupported.slice(0,3).join(', ')}.`:'No supported audio files found.');
      return;
    }
    const plan=planFileDrop(files,!!sceneId);
    const notes:string[]=[];
    await action(async()=>{
      if(plan.audio&&sceneId){setImportStatus(`Adding ${plan.audio.name}…`);await attachAudio(sceneId,()=>api.uploadVoiceTake(sceneId,plan.audio!));notes.push(`${plan.audio.name} added to the scene’s audio`);}
      const uploaded:Asset[]=[];
      for(const f of plan.visuals){setImportStatus(`Importing ${f.name}…`);uploaded.push(await api.uploadAsset(project.id,f));}
      await placeVisuals(sceneId,uploaded,insert);
      if(uploaded.length)notes.push(`${uploaded.length} image/video file(s) ${sceneId?'added to the scene':'placed on the timeline'}`);
      setMediaVersion(v=>v+1);await refresh();
    });
    if(plan.extraAudio.length)notes.push(sceneId?`${plan.extraAudio.length} more audio file(s) skipped — one audio file per scene`:`Audio not added — drop audio onto a scene`);
    if(plan.rejected.length)notes.push(`Skipped unsupported: ${plan.rejected.slice(0,3).join(', ')}${plan.rejected.length>3?'…':''}`);
    setImportStatus(notes.join('. ')+(notes.length?'.':''));
  }
  async function dropAssetsOnTimeline(sceneId:string|null,dragged:DraggedAsset[],insert?:{before?:string;after?:string;audioTrack?:boolean;timeMs?:number;track?:string}){
    if(!project)return;
    const audio=dragged.filter(a=>a.type==='audio'),visual=dragged.filter(a=>a.type==='image'||a.type==='video');
    if(insert?.audioTrack){await addTimelineAudioAssets(audio,insert.timeMs||0,insert.track);setImportStatus(audio.length?`${audio.length} audio clip${audio.length===1?'':'s'} added to ${insert.track||'A3'}.`:'Drop an audio item from the Media Pool onto an audio track (A3–A8).');return;}
    await action(async()=>{
      if(audio[0]&&sceneId)await attachAudio(sceneId,()=>api.useAudioAsset(sceneId,audio[0].id) as Promise<{id:string}>);
      await placeVisuals(sceneId,visual as unknown as Asset[],insert);
      await refresh();
    });
    setImportStatus(audio.length&&!sceneId?'Audio not added — drop audio onto a scene.':audio.length>1?'Only the first audio file was added; one audio file per scene.':'');
  }
  async function usePoolAsset(asset:Asset){if(!selected)return;await action(async()=>{if(asset.type==='audio')await api.useAudioAsset(selected.id,asset.id);else await api.addShot(selected.id,asset.id);await refresh();});}

  async function importAudio(file:File|undefined){
    if(!selected||!file)return;setMenu('');
    await action(async()=>{const take=await api.uploadVoiceTake(selected.id,file);await api.selectTake(take.id);await refresh();});
  }
  useEffect(()=>{const close=(e:MouseEvent)=>{const target=e.target as Element;if(!target.closest('.editor-menu'))setMenu('');if(!target.closest('.theme-control'))setThemeMenuOpen(false);};const escape=(e:KeyboardEvent)=>{if(e.key==='Escape'){setMenu('');setThemeMenuOpen(false);}};document.addEventListener('click',close);document.addEventListener('keydown',escape);return()=>{document.removeEventListener('click',close);document.removeEventListener('keydown',escape);};},[]);
  const [exportScenes,setExportScenes] = useState<Scene[]>([]);
  const [exportLayers,setExportLayers]=useState<TimelineLayerClip[]>([]);
  const [exportJobId, setExportJobId] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsInitialTab,setSettingsInitialTab]=useState<'preferences'|'providers'>('preferences');
  function openSettings(tab:'preferences'|'providers'='preferences') {setSettingsInitialTab(tab);setSettingsOpen(true);}
  const [infoPanel, setInfoPanel] = useState<{panel:string;section?:string}|null>(null);
  useEffect(()=>{const open=(e:Event)=>{const detail=(e as CustomEvent).detail;if(detail?.panel==='preferences'){openSettings('preferences');return;}if(detail?.panel==='projects')return;if(detail?.panel==='tour'){setTourOpen(true);return;}setInfoPanel(detail||null);};window.addEventListener('sceneforge-open-panel',open);return()=>window.removeEventListener('sceneforge-open-panel',open);},[]);
  useEffect(()=>{const open=()=>openSettings('providers');window.addEventListener('sceneforge-open-settings',open);return()=>window.removeEventListener('sceneforge-open-settings',open);},[]);
  const [sidebar, setSidebar] = useState(true);
  const [libraryTab,setLibraryTab] = useState<'Scenes'|'Media Pool'|'Transitions'>('Scenes');
  const [states, setStates] = useState<Record<string,string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [shareOpen,setShareOpen]=useState(false);
  const sharedExport=useRef('');
  const exportJob = useJobProgress(exportJobId);
  const exporting = !!exportJob && ["queued", "running", "cancelling"].includes(exportJob.status);
  const layerActions:LayerActions={selectedId:selectedLayerId,onSelect:id=>{if(id!==selectedLayerId)void saveBeforeClose().then(ok=>{if(ok)setSelectedLayerId(id);});},onDraft:isDirty=>setStates(s=>({...s,timelineLayer:isDirty?"Unsaved":"Saved"})),onChange:updateLayerClips,onAdd:(...args)=>void addLayerClip(...args),disabled:busy||exporting};

  useAutoSnapshots(project?.id, busy||exporting);   // 0.9.0 automatic restore points
  useEffect(()=>{if(exportJob?.status==='succeeded'&&exportJob.artifact_asset_id&&sharedExport.current!==exportJob.id){sharedExport.current=exportJob.id;setShareOpen(true);}},[exportJob?.id,exportJob?.status,exportJob?.artifact_asset_id]);
  const dirty = Object.values(states).some(s => s !== "Saved");
  const statesRef = useRef(states); statesRef.current = states;
  const [clip, setClip] = useState<{kind:'scene'|'audio';id:string;label:string}|null>(null);
  const [hoverTx, setHoverTx] = useState<string|null>(null);   // transition previewed on the picture
  const [multi, setMulti] = useState<string[]>([]);            // several parts selected on the timeline
  const [exportOpen, setExportOpen] = useState(false);
  const [savingRestore,setSavingRestore]=useState(false);
  const savingRestoreRef=useRef(false);
  const [videoGenOpen,setVideoGenOpen]=useState(false);
  const [projectMode, setProjectMode] = useState<'new'|'open'>('open');
  /** Back to the project list (to start a new project or open another), after saves finish. */
  async function goToProjects(mode:'new'|'open'){
    if(project&&!(await saveBeforeClose())){setError('Could not save the current edits. Keep the project open and retry.');return;}
    if(project&&!(await saveTitle()))return;
    for(let i=0;i<40&&(Object.values(statesRef.current).some(v=>v!=="Saved")||hasActiveWrites());i++)await new Promise(r=>setTimeout(r,250));
    if(Object.values(statesRef.current).some(v=>v!=="Saved")||hasActiveWrites()){setError('The current edits are still saving. Wait for the saved status, then return to projects.');return;}
    await action(async()=>{setProjects(await api.listProjects());projectRef.current=null;setProject(null);setProjectMode(mode);setMulti([]);setVideoGenOpen(false);});
  }
  useEffect(()=>{
    const onPanel=(e:Event)=>{const d=(e as CustomEvent).detail;if(d?.panel==='projects')void goToProjects(d.mode==='open'?'open':'new');};
    const onKey=(e:KeyboardEvent)=>appShortcut.current(e);
    window.addEventListener('sceneforge-open-panel',onPanel);window.addEventListener('keydown',onKey);
    return()=>{window.removeEventListener('sceneforge-open-panel',onPanel);window.removeEventListener('keydown',onKey);};
  },[]);
  async function duplicateScene(id:string, after?:string){
    if(!project)return;
    await action(async()=>{const dup=await api.duplicateScene(id);
      if(after&&after!==id){const ids=project.scenes.map(s=>s.id).filter(x=>x!==dup.id);const at=ids.indexOf(after);ids.splice(at+1,0,dup.id);await api.reorderScenes(project.id,ids);}
      await refresh();setSelectedId(dup.id);setImportStatus(`Duplicated “${dup.title}”. Change its effects without affecting the original.`);});
  }
  async function pasteClip(targetId:string){
    if(!clip||!project)return;
    if(clip.kind==='scene'){await duplicateScene(clip.id,targetId);return;}
    await action(async()=>{await api.pasteAudio(targetId,clip.id);await refresh();setImportStatus(`Pasted ${clip.label}. Adjust its volume and fades in the Audio tab.`);});
  }
  const failed = Object.values(states).some(s => s === "Save failed");
  const status = failed ? "Save failed" : Object.values(states).some(s=>s.startsWith("Draft")) ? "Draft changes · Apply or Cancel" : states.timelineLayer==="Unsaved" ? "Overlay changes · Apply to save" : dirty ? "Saving changes…" : "All changes saved";
  const selected = project?.scenes.find(s => s.id === selectedId) || project?.scenes[0];
  const closeRef=useRef<(saveChanges:boolean,exiting:boolean)=>Promise<{ready:boolean;reason?:string}>>(async()=>({ready:false,reason:'save-failed'}));
  closeRef.current=async(saveChanges,exiting)=>{
    if(busy)return {ready:false,reason:'pending-work'};
    if(saveChanges){
      if(!(await saveBeforeClose()))return {ready:false,reason:'save-failed'};
      if(!(await saveTitle())||hasActiveWrites())return {ready:false,reason:'save-failed'};
    } else if(hasActiveWrites())return {ready:false,reason:'pending-work'};
    if(!exiting)return {ready:true};
    if(exporting)return {ready:false,reason:'active-work'};
    const status=await api.closeStatus();
    return status.ready?{ready:true}:{ready:false,reason:'active-work'};
  };
  useEffect(()=>{
    const target=window as Window & {__sceneForgePrepareClose?:(saveChanges:boolean,exiting:boolean)=>Promise<{ready:boolean;reason?:string}>};
    target.__sceneForgePrepareClose=(saveChanges,exiting)=>closeRef.current(saveChanges,exiting);
    return()=>{delete target.__sceneForgePrepareClose;};
  },[]);
  projectRef.current = project;
  useEffect(() => {api.listProjects().then(setProjects).catch(e => setError(e.message)).finally(() => setLoading(false));}, []);
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {if(dirty) {e.preventDefault(); e.returnValue="";}};
    window.addEventListener("beforeunload",warn); return () => window.removeEventListener("beforeunload",warn);
  }, [dirty]);
  useEffect(() => {
    if(exportJob && ["succeeded","failed","cancelled"].includes(exportJob.status)) void refresh().catch(e => setError(e.message));
  },[exportJob?.status]);
  const preparingProjectAction=useRef(false);
  async function prepareProjectAction():Promise<boolean>{
    if(preparingProjectAction.current)return false;
    preparingProjectAction.current=true;
    try{
      const draft=projectRef.current?.scenes.find(scene=>statesRef.current[scene.id]?.startsWith('Draft'));
      if(draft){
        setSelectedId(draft.id);
        window.dispatchEvent(new CustomEvent('sceneforge-open-tab',{detail:{sceneId:draft.id,tab:'Motion'}}));
        setError(`Apply or Cancel the Motion/Effects changes in “${draft.title}” before switching timelines or exporting.`);
        return false;
      }
      if(!(await saveBeforeClose())||!(await saveTitle())){
        setError('Could not finish saving. Retry any failed save or wait for the scene render to finish. Your edits are retained.');
        return false;
      }
      for(let i=0;i<40&&(Object.values(statesRef.current).some(v=>v!=="Saved")||hasActiveWrites());i++)await new Promise(r=>setTimeout(r,250));
      if(Object.values(statesRef.current).some(v=>v!=="Saved")||hasActiveWrites()){
        setError('Changes have not finished saving. Apply pending changes or retry a failed save before continuing.');return false;
      }
      setError(null);return true;
    }finally{preparingProjectAction.current=false;}
  }
  async function openFreeTimeline(){
    if(busy||exporting||!(await prepareProjectAction()))return;
    const current=projectRef.current;if(!current)return;
    setFreeSourceView(false);
    if(!current.finishing_json?.free_timeline?.enabled)await updateFreeTimeline({free_timeline:current.finishing_json?.free_timeline?{...current.finishing_json.free_timeline,enabled:true}:seedFree(current)},'enable free timeline');
  }
  async function openExportDialog(){if(!busy&&!exporting&&await prepareProjectAction())setExportOpen(true);}
  async function renderFullVideo(settings?: Record<string, unknown>){
    if(!project||busy||exporting)return;
    if(!(await prepareProjectAction()))return;
    const current=projectRef.current;if(!current)return;
    await action(async()=>{const free=current.finishing_json?.free_timeline;const placed=new Set(free?.clips.map(c=>c.scene_id));const empty=current.scenes.filter(s=>!s.shots.length&&(!free?.enabled||placed.has(s.id)));
      if(!current.scenes.some(s=>s.shots.length)&&!free?.enabled){setError('Add an image or video before rendering the full video.');return;}
      if(empty.length&&!await askConfirm(`Skip ${empty.length} empty scene(s) and render all scenes with media?`))return;
      setExportPanel(true);setExportExpanded(false);setExportScenes(structuredClone(current.scenes));setExportLayers(structuredClone(current.finishing_json?.layer_clips||[]));
      setExportJobId((await api.exportProject(current.id,empty.length>0,settings||{quality:'draft'})).job_id);
    });
  }
  async function refresh() {
    const id=projectRef.current?.id; if(!id) return;
    const version=++refreshVersion.current;
    const p=await api.getProject(id);
    if(projectRef.current?.id===id && version===refreshVersion.current) setProject(p);
  }
  async function action(fn: () => Promise<unknown>): Promise<boolean> {
    setBusy(true); setError(null);
    try {await fn(); return true;} catch(e:any) {setError(e.message); return false;} finally {setBusy(false);}
  }
  async function openProject(id:string) {
    await action(async () => {const p=await api.getProject(id); projectRef.current=p; setProject(p);setMediaVersion(v=>v+1);setImportStatus(''); setTitleDraft(p.title); setSelectedId(p.scenes[0]?.id||""); setStates({}); setExportJobId(null);setHistory([]);setFuture([]);});
  }
  async function removeProject(p:Project) {
    if(!await askConfirm(`Delete “${p.title}” and its scenes? This cannot be undone. Original and cached media files are retained on disk.`))return;
    await action(async()=>{await api.deleteProject(p.id);setProjects(old=>old.filter(x=>x.id!==p.id));});
  }
  async function createProject() {
    await action(async () => {const p=await api.createProject(newTitle.trim()||"Untitled documentary",newAspect,newFps); await openProject(p.id); setProjects(await api.listProjects());});
  }
  async function resizeDuration(id:string,ms:number){
    const scene=project?.scenes.find(s=>s.id===id);if(!scene)return;
    const take=scene.voice_takes.find(t=>t.accepted);
    if(take&&ms<(take.effective_duration_ms??take.measured_duration_ms??0)+(scene.lead_ms||0)+(scene.trail_ms||0)&&!await askConfirm('This duration may cut narration short. Switch to fixed timing?'))return;
    await record('duration',()=>api.updateScene(id,{timing_mode:scene.timing_mode,requested_duration_ms:scene.requested_duration_ms}),()=>api.updateScene(id,{timing_mode:'fixed',requested_duration_ms:ms}));
  }
  const [titleCard,setTitleCard]=useState(false);
  const [freeSourceView,setFreeSourceView]=useState(false);
  useEffect(()=>setFreeSourceView(false),[project?.id]);
  async function addTitleCard(design:TitleDesign){
    if(!project||!design.text.trim())return;
    await action(async()=>{
      const canvas=document.createElement('canvas');canvas.width=project.width;canvas.height=project.height;
      const ctx=canvas.getContext('2d')!;ctx.fillStyle=design.background;if(design.gradient){const g=ctx.createLinearGradient(0,0,canvas.width,canvas.height);g.addColorStop(0,design.background);g.addColorStop(1,design.background2);ctx.fillStyle=g;}ctx.fillRect(0,0,canvas.width,canvas.height);
      const blob=await new Promise<Blob>((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(Error('Could not create background')),'image/png'));
      const asset=await api.uploadAsset(project.id,new File([blob],'title-background.png',{type:'image/png'}));
      let titleScene:Scene|null=null;
      await record('add title card',async()=>{if(titleScene)await api.deleteScene(titleScene.id);},async()=>{const scene=titleScene?await api.restoreScene(titleScene.id,titleScene):await api.addScene(project.id);if(!titleScene){await api.addShot(scene.id,asset.id);await api.updateScene(scene.id,{title:'Title · '+design.text.slice(0,40),timing_mode:'fixed',requested_duration_ms:Math.round(design.duration*1000),font:{captions_enabled:false,layers:[{...design.layer,id:crypto.randomUUID(),text:design.text}]}});}titleScene=await api.getScene(scene.id);setSelectedId(scene.id);});
      const selectedTitleId=(titleScene as Scene|null)?.id;setTitleCard(false);setLibraryTab('Scenes');await refresh();if(selectedTitleId)setSelectedId(selectedTitleId);
    });
  }
  async function addPart() {
    if(!project)return;let snapshot:Scene|null=null,sceneId='';
    await record('add scene',async()=>{if(snapshot)await api.deleteScene(sceneId);},async()=>{const scene=snapshot?await api.restoreScene(snapshot.id,snapshot):await api.addScene(project.id);sceneId=scene.id;snapshot=await api.getScene(scene.id);setSelectedId(scene.id);});
  }
  async function moveScene(id:string,dir:-1|1) {
    if(!project) return;
    const ids=project.scenes.map(s=>s.id), i=ids.indexOf(id), j=i+dir;
    if(i<0||j<0||j>=ids.length) return;
    const before=project.scenes.map(s=>s.id);[ids[i],ids[j]]=[ids[j],ids[i]];await record('scene order',()=>api.reorderScenes(project.id,before),()=>api.reorderScenes(project.id,ids));
  }
  async function deleteScene(id:string) {
    const snapshot=(projectRef.current?.scenes||[]).find(s=>s.id===id);if(!snapshot)return;
    if(!await askConfirm("Ripple delete this scene and close the gap? You can undo it from Edit → Undo.")) return;
    await record('delete scene',()=>api.restoreScene(id,snapshot),()=>api.deleteScene(id));
    setStates(prev=>{const next={...prev};delete next[id];return next;});
    setSelectedId((projectRef.current?.scenes||[]).find(s=>s.id!==id)?.id||'');
  }
  async function saveTitle() {
    if(!project) return true;
    if(titleDraft===project.title) {setStates(prev=>({...prev,title:"Saved"})); return true;}
    const title=titleDraft.trim()||"Untitled documentary";
    const ok=await action(async () => {await api.updateProject(project.id,{title}); await refresh();});
    if(ok) setTitleDraft(title);
    setStates(prev=>({...prev,title:ok?"Saved":"Save failed"}));
    return ok;
  }
  async function saveRestorePoint(){
    if(!project||busy||exporting||savingRestoreRef.current)return;
    savingRestoreRef.current=true;setSavingRestore(true);
    try{
      if(!(await saveBeforeClose())||!(await saveTitle())){setError('Could not save current edits. Retry before saving a restore point.');return;}
      await action(async()=>{const r=await api.saveSnapshot(project.id,{auto:false});setImportStatus(r.saved?'Restore point saved.':r.reason||'No changes since the last restore point.');});
    }finally{savingRestoreRef.current=false;setSavingRestore(false);}
  }
  appShortcut.current=(e:KeyboardEvent)=>{
    if(e.defaultPrevented||e.altKey||!(e.ctrlKey||e.metaKey)||document.querySelector('dialog[open],[role="dialog"]'))return;
    const t=e.target as HTMLElement|null;
    if(t?.closest('input,textarea,select,[contenteditable]:not([contenteditable="false"])'))return;
    const k=e.key.toLowerCase();
    if(k==='n'||k==='o'){e.preventDefault();if(!busy&&!exporting)void goToProjects(k==='n'?'new':'open');}
    else if(k==='s'&&!e.shiftKey&&project){e.preventDefault();void saveRestorePoint();}
    else if(k==='e'&&!e.shiftKey&&project){e.preventDefault();void openExportDialog();}
    else if(k===','&&!e.shiftKey&&project){e.preventDefault();openSettings('preferences');}
    else if(k==='a'&&e.shiftKey&&project){e.preventDefault();setInfoPanel({panel:'ai'});}
  };
  if(!project) return <main className="project-home"><BuildNotice/>
    <div className="project-home-header"><div className="brand"><span className="brand-mark"><Film size={22}/></span> SceneForge <span className="version-chip">STUDIO</span></div><div className="home-menubar"><div className="editor-menu"><button aria-expanded={menu==='HomeFile'} onClick={()=>setMenu(menu==='HomeFile'?'':'HomeFile')}>File</button>{menu==='HomeFile'&&<div className="editor-menu-items"><button onClick={()=>{setMenu('');openSettings('preferences');}}>Preferences…</button></div>}</div></div></div>
    <section className="home-intro"><span className="eyebrow">YOUR STORY, FRAME BY FRAME</span><h1>Make room for<br/>your next story.</h1><p>Turn scripts, images, and narration into a video.<br/>One scene at a time.</p></section>
    {error && <div role="alert" className="error-box">{error}</div>}
    <section className="new-project"><div><h2>Create a project</h2><p className="hint">Start with three scenes. Add more as your story grows.</p></div><div className="create-form"><label className="control-label">Project name<input autoFocus={projectMode==='new'} aria-label="New project name" value={newTitle} onChange={e=>setNewTitle(e.target.value)}/></label><label className="control-label">Format<select aria-label="New project aspect ratio" value={newAspect} onChange={e=>setNewAspect(e.target.value)}>{ASPECTS.map(a=><option key={a}>{a}</option>)}</select></label><label className="control-label">Frame rate<select aria-label="New project frame rate" value={newFps} onChange={e=>setNewFps(Number(e.target.value))}>{[24,25,30,50,60].map(f=><option key={f} value={f}>{f} fps</option>)}</select></label><button className="btn btn-primary" disabled={busy} onClick={createProject}><Plus size={16}/> Create project</button></div></section><section className="sample-project"><div><h2>New to SceneForge?</h2><p className="hint">Open a ready-made 3-scene project with pictures, captions, a typewriter title, stickers, effects, music and sound effects. Press Render scene to see it come to life, then change anything.</p></div><button className="btn" disabled={busy} onClick={()=>void action(async()=>{const p=await api.createSampleProject();await openProject(p.id);setProjects(await api.listProjects());})}><Sparkles size={16}/> Try a sample project</button></section>
    <div className="section-heading"><h2>Your projects</h2><span className="subtle">{projects.length} projects</span></div>
    <label className="search-control"><Search size={16}/><input aria-label="Search projects" placeholder="Find a project…" value={projectSearch} onChange={e=>setProjectSearch(e.target.value)}/></label>
    {loading ? <p role="status">Loading projects…</p> : <div className="project-grid">{projects.filter(p=>p.title.toLowerCase().includes(projectSearch.toLowerCase())).map(p=><article className="project-tile" key={p.id}><button className="project-open-button" disabled={busy} onClick={()=>openProject(p.id)}><div className="project-cover"><Film size={30}/><span>{p.aspect}</span></div><strong>{p.title}</strong><span className="project-open">Open project <ArrowRight size={15}/></span></button><button className="text-btn project-delete" aria-label={`Delete project ${p.title}`} disabled={busy} onClick={()=>removeProject(p)}><Trash2 size={14}/> Delete</button></article>)}{!projects.filter(p=>p.title.toLowerCase().includes(projectSearch.toLowerCase())).length&&<p className="hint">{projects.length?"No matching projects.":"Your saved projects will appear here."}</p>}</div>}
    <button className="btn" disabled={busy} onClick={()=>setStoryTab("Project templates")}>Project templates…</button>
    {storyTab&&<StoryTools initialTab={storyTab} onClose={()=>setStoryTab(null)} onRecord={record} onOpen={openProject} disabled={busy}/> }
    {settingsOpen&&<SettingsPanel key={settingsInitialTab} initialTab={settingsInitialTab} onClose={()=>setSettingsOpen(false)} preferences={preferences} onPreferencesChange={updatePreferences}/>}
    {infoPanel?.panel==='models'&&<ModelManager onClose={()=>setInfoPanel(null)}/>}
  </main>;
  return <div className="studio-shell"><BuildNotice/>
    {storyTab&&<StoryTools key={project.id+selected?.id} project={project} scene={selected} initialTab={storyTab} onClose={()=>setStoryTab(null)} onRecord={record} onOpen={openProject} onScenesAdded={(scenes,message)=>{setMulti([]);setImportedSceneIds(scenes.map(s=>s.id));setLibraryTab('Scenes');setSelectedId(scenes[0]?.id||selectedId);setImportStatus(message);}} disabled={busy||exporting||dirty}/> }
    <header className="studio-toolbar">
      <div className="brand"><span className="brand-mark"><Film size={19}/></span><span>SceneForge</span></div>
      <span className="toolbar-divider"/>
      <div className="project-identity"><input aria-label="Project name" value={titleDraft} onChange={e=>{setTitleDraft(e.target.value); setStates(prev=>({...prev,title:"Unsaved changes"}));}} onBlur={()=>void saveTitle()}/><span role="status" className={`save-status ${failed ? "save-error" : ""}`}>{busy ? "Saving…" : status}</span></div>
      <div className="toolbar-end"><button className="btn back-projects" disabled={busy} onClick={()=>void goToProjects('open')} title="Save current changes and return to your projects"><ArrowLeft size={14}/> Projects</button><select aria-label="Project aspect ratio" value={project.aspect} disabled={busy||exporting} onChange={e=>action(async()=>{await api.updateProject(project.id,{aspect:e.target.value}); await refresh();})}>{ASPECTS.map(a=><option key={a}>{a}</option>)}</select><label className="workspace-switcher" title={workspacePreset(preferences.workspace).description}><LayoutDashboard size={14}/><span>Workspace</span><select aria-label="Workspace" value={preferences.workspace} onChange={e=>switchWorkspace(e.target.value as WorkspaceId)}>{WORKSPACES.map(w=><option key={w.id} value={w.id}>{w.label}</option>)}</select></label><div className="theme-control"><button className="theme-toggle" aria-label={`Theme: ${THEMES.find(x=>x.id===preferences.theme)?.label}`} aria-haspopup="menu" aria-expanded={themeMenuOpen} title="Choose editor theme" onClick={()=>setThemeMenuOpen(open=>!open)}>{preferences.theme==='light'?<Sun size={16}/>:<Moon size={16}/>}<span>Theme</span><ChevronDown size={13}/></button>{themeMenuOpen&&<div className="theme-popover" role="menu" aria-label="Editor theme">{THEMES.map(item=><button key={item.id} role="menuitemradio" aria-checked={preferences.theme===item.id} onClick={()=>{updatePreferences({theme:item.id});setThemeMenuOpen(false);}}><i className={`theme-swatch ${item.id}`}/>{item.label}{preferences.theme===item.id&&<CheckCircle2 size={14}/>}</button>)}</div>}</div><button className="btn video-gen-launch" disabled={busy||exporting} onClick={()=>setVideoGenOpen(true)}><Clapperboard size={15}/>Generate video</button><button className="btn btn-primary export-launch" title="Export video (Ctrl+E)" disabled={exporting||busy||(!project.scenes.length&&!project.finishing_json?.free_timeline?.enabled)} onClick={()=>void openExportDialog()}><Upload size={15}/>{exporting ? `Exporting ${Math.round(exportJob?.progress||0)}%` : "Export video"}</button></div>
    </header>
    {titleCard&&<TitleDesigner width={project.width} height={project.height} busy={busy} onClose={()=>setTitleCard(false)} onCreate={d=>void addTitleCard(d)}/>}
    {project&&!storyTab&&multi.length>1&&selected&&<BatchBar source={selected} scenes={project.scenes.filter(x=>multi.includes(x.id))} onClear={()=>setMulti([])} onDone={()=>void refresh()}/>}
    {exportOpen&&project&&<ExportDialog project={project} onClose={()=>setExportOpen(false)} onExport={settings=>{setExportOpen(false);void renderFullVideo(settings);}} onReframe={()=>{setExportOpen(false);setReframeOpen(true);}}/>}
    {reframeOpen&&project&&<ReframeProjectDialog project={project} onClose={()=>setReframeOpen(false)} onOpen={id=>{setReframeOpen(false);void openProject(id);}}/>}
    {videoGenOpen&&project&&<VideoGenerationPanel project={project} selectedSceneId={selected?.id||null} onClose={()=>setVideoGenOpen(false)} onOpenSettings={()=>openSettings('providers')} onAdd={addGeneratedVideoToTimeline} onCaptions={captionGeneratedScene}/>}
    {exporting&&exportJob&&<ProgressCard floating title="Exporting video" stage={exportJob.stage} progress={exportJob.progress||0} status={exportJob.status} onCancel={()=>void api.cancelJob(exportJob.id).catch(()=>{})}/>}
    {(error||exportJob?.status==="failed")&&<div role="alert" className="error-box">{error?<p>{error}</p>:<details><summary>Export failed — show details</summary><pre>{exportJob?.error}</pre></details>}<button className="text-btn" onClick={()=>{setError(null);if(exportJob?.status==='failed')setExportJobId(null);}}>Dismiss</button></div>}
    <div className="editor-menubar">
      {['File','AI Engines','Edit','View','Help'].map(name=><div className="editor-menu" key={name}><button aria-expanded={menu===name} onClick={()=>setMenu(menu===name?'':name)}>{name}</button>{menu===name&&<div className="editor-menu-items">
       {name==='AI Engines'&&<><button onClick={()=>{setMenu('');setInfoPanel({panel:'ai',section:'cloud'});}}>AI providers · API keys</button><button onClick={()=>{setMenu('');setInfoPanel({panel:'ai',section:'sd'});}}>Local image engines</button><button onClick={()=>{setMenu('');setInfoPanel({panel:'ai',section:'voices'});}}>Local voice engines</button><button onClick={()=>{setMenu('');setInfoPanel({panel:'ai'});}}>AI help &amp; setup</button></>}
       {name==='File'&&<><button disabled={busy||exporting} onClick={()=>{setMenu('');void goToProjects('new');}}>New project… <kbd>Ctrl+N</kbd></button><button disabled={busy||exporting} onClick={()=>{setMenu('');void goToProjects('open');}}>Open project… <kbd>Ctrl+O</kbd></button><button disabled={!project||busy||exporting} onClick={()=>{setMenu('');setInfoPanel({panel:'restore'});}}>Restore points…</button><button disabled={busy||exporting||savingRestore} title="Save the current edits and keep a restore point (Ctrl+S)" onClick={()=>{setMenu('');void saveRestorePoint();}}>Save restore point <kbd>Ctrl+S</kbd></button><button disabled={busy||exporting||dirty||!project.scenes.length} onClick={()=>{setMenu('');setExportOpen(true);}}>Export video… <kbd>Ctrl+E</kbd></button><button onClick={()=>{setMenu('');openSettings('preferences');}}>Preferences… <kbd>Ctrl+,</kbd></button><button disabled={busy||exporting} onClick={()=>{setMenu('');void addPart();}}>New scene</button><button disabled={busy||exporting} onClick={()=>{setMenu('');setVideoGenOpen(true);}}>Generate video from text…</button><button disabled={busy||exporting||dirty} onClick={()=>{setMenu('');setReframeOpen(true);}}>Create vertical 9:16 version (auto-reframe)…</button><button disabled={busy||exporting} onClick={()=>importRef.current?.click()}>Import files to Media Pool…</button><button disabled={busy||exporting} onClick={()=>folderRef.current?.click()}>Import folder to Media Pool…</button><button disabled={!selected||busy||exporting} onClick={()=>audioImportRef.current?.click()}>Import audio to selected scene…</button></>}
       {name==='Edit'&&<>{(["Script → Scenes","AutoCut","Stabilize video","Project templates"] as StoryTab[]).map(t=><button key={t} disabled={busy||dirty||exporting} onClick={()=>{setMenu('');setStoryTab(t);}}>{t}…</button>)}<button disabled={!history.length||busy||dirty||exporting} onClick={()=>{setMenu('');void undoTimeline();}}>Undo {history[history.length-1]?.label||'timeline edit'} <kbd>Ctrl+Z</kbd></button><button disabled={!future.length||busy||dirty||exporting} onClick={()=>{setMenu('');void redoTimeline();}}>Redo {future[future.length-1]?.label||'timeline edit'} <kbd>Ctrl+Y</kbd></button><button disabled={!selected||busy||exporting} onClick={()=>{setMenu('');if(selected)void deleteScene(selected.id);}}>Delete selected scene… <kbd>Delete</kbd></button></>}
       {name==='View'&&<><button onClick={()=>{setSidebar(!sidebar);setMenu('');}}>Toggle scene library</button><button onClick={()=>{document.querySelector('.studio-shell')?.classList.toggle('inspector-hidden');setMenu('');}}>Toggle inspector</button><button onClick={()=>{setExportPanel(!exportPanel);setMenu('');}}>Show / hide export result</button><button onClick={()=>{setMenu('');if(document.fullscreenElement)void document.exitFullscreen();else void document.documentElement.requestFullscreen();}}>Fullscreen / restore</button><div className="menu-section-label" role="presentation">Workspace</div>{WORKSPACES.map(w=><button key={w.id} aria-pressed={preferences.workspace===w.id} title={w.description} onClick={()=>{setMenu('');switchWorkspace(w.id);}}>{preferences.workspace===w.id?'✓ ':''}{w.label} workspace</button>)}</>}
       {name==='Help'&&<><button onClick={()=>{setMenu('');setInfoPanel({panel:'shortcuts'});}}>Keyboard shortcuts <kbd>Ctrl+/ or ?</kbd></button><button onClick={()=>{setMenu('');setTourOpen(true);}}>Show tour</button><button onClick={()=>{setMenu('');setInfoPanel({panel:'models'});}}>AI models…</button><a className="menu-link" href={api.diagnosticsUrl()} download onClick={()=>setMenu('')} title="Download a zip with versions, settings (no API keys), model status and recent logs for a bug report">Export diagnostics (.zip)</a><button onClick={()=>{setMenu('');setInfoPanel({panel:'about'});}}>About SceneForge</button></>}
      </div>}</div>)}<span className="menu-help">Import audio into A1 · Scissors: choose a cut position · Render complex scenes before cutting</span>
    </div>
    <input hidden ref={importRef} type="file" accept="image/*,video/*,audio/*" multiple onChange={e=>{void importMedia(e.target.files);e.target.value='';}}/>
    <input hidden ref={folderRef} type="file" multiple {...{webkitdirectory:''} as any} onChange={e=>{void importMedia(e.target.files);e.target.value='';}}/>
    <input hidden ref={audioImportRef} type="file" accept="audio/*" onChange={e=>{void importAudio(e.target.files?.[0]);e.target.value='';}}/>
    {exportPanel&&exportJob?.status==='succeeded'&&exportJob.artifact_asset_id&&<section className="export-result" aria-label="Export result"><header><CheckCircle2 size={16}/><span>Last export ready · Export again after edits</span>{!!exportJob.warnings?.length&&<span className="hint" role="note">{exportJob.warnings.join(' ')}</span>}<a href={api.assetDownloadUrl(exportJob.artifact_asset_id)} download>Download MP4</a><button className="text-btn" onClick={()=>setShareOpen(true)}>Share…</button><button aria-label={exportExpanded?'Minimize export result':'Expand export result'} onClick={()=>setExportExpanded(!exportExpanded)}>{exportExpanded?'−':'+'}</button><button aria-label="Close export result" onClick={()=>setExportPanel(false)}><X size={14}/></button></header>{exportExpanded&&<video controls src={api.assetStreamUrl(exportJob.artifact_asset_id)}/>}</section>}
    <div className={`workspace ${sidebar ? "" : "sidebar-collapsed"}`}>
      <nav className="scene-sidebar" aria-label="Scenes"><div className="sidebar-header"><h2><Layers size={16}/> Scenes <span className="count-badge">{project.scenes.length}</span></h2><button className="icon-btn" aria-label={sidebar?"Collapse scene list":"Expand scene list"} title={sidebar?"Collapse scene list":"Expand scene list"} onClick={()=>setSidebar(!sidebar)}>{sidebar?<PanelLeftClose size={16}/>:<PanelLeftOpen size={16}/>}</button></div>
      {sidebar&&<><div className="library-tabs" aria-label="Asset library">{(['Scenes','Media Pool','Transitions'] as const).map(t=><button key={t} aria-pressed={libraryTab===t} onClick={()=>setLibraryTab(t)}>{t}</button>)}</div>
      <div className="library-content">
      {libraryTab==='Media Pool'&&<>{importStatus&&<p className="hint" aria-live="polite">{importStatus}</p>}<MediaPool projectId={project.id} version={mediaVersion} disabled={busy||exporting} onImport={()=>importRef.current?.click()} onFolder={()=>folderRef.current?.click()} onAdd={addPoolAssets} onUse={usePoolAsset} canUse={!!selected}/></>}

      {libraryTab==='Scenes'&&<>{importedSceneIds.some(id=>project.scenes.some(s=>s.id===id))&&<section className="imported-scene-links" aria-label="Added script scenes"><div className="button-row"><strong>Added scenes · click to edit</strong><button className="text-btn" onClick={()=>setImportedSceneIds([])}>Dismiss</button></div>{importedSceneIds.map(id=>project.scenes.find(s=>s.id===id)).filter((s):s is Scene=>!!s).map((s,i)=><button className="btn" key={s.id} aria-label={`Edit imported scene ${i+1}: ${s.title}`} aria-pressed={selectedId===s.id} onClick={()=>setSelectedId(s.id)}>{i+1}. {s.title}</button>)}</section>}<p className="sidebar-hint">PROJECT BIN · Select a part to edit</p><div className="scene-list">{project.scenes.map((s,i)=><button key={s.id} className={`scene-nav ${selected?.id===s.id?"selected":""}`} aria-label={`Select scene ${i+1}: ${s.title}`} aria-current={selected?.id===s.id?"true":undefined} onClick={()=>setSelectedId(s.id)}><div className="scene-thumb">{s.shots[0]?<Thumb assetId={s.shots[0].asset_id} type={s.shots[0].asset?.type}/>:<Film size={22}/>}<span>{String(i+1).padStart(2,"0")}</span></div><div className="scene-nav-meta"><strong>{s.title}</strong><span>{durationLabel(s)} · {s.shots.length} media</span></div></button>)}</div><button className="btn add-scene" disabled={busy||exporting} onClick={()=>setTitleCard(true)}><Type size={16}/> Add title card</button><button className="btn add-scene" disabled={busy} onClick={addPart}><Plus size={16}/> Add scene</button></>}
      {libraryTab==='Transitions'&&<><p className="sidebar-hint">INCOMING TO · {selected?.title||'Select a part'}</p><div className="library-presets transition-presets">{TRANSITIONS.map(([key,label])=><button key={key} onMouseEnter={()=>setHoverTx(key)} onMouseLeave={()=>setHoverTx(null)} onFocus={()=>setHoverTx(key)} onBlur={()=>setHoverTx(null)} aria-pressed={selected?.transition_in_json.type===key} disabled={!selected?.shots.length||selected.id===project.scenes.find(s=>s.shots.length)?.id||busy||exporting} onClick={()=>selected&&record('transition',()=>api.updateScene(selected.id,{transition_in:selected.transition_in_json}),()=>api.updateScene(selected.id,{transition_in:{type:key,duration_ms:key==='cut'?0:(selected.transition_in_json.duration_ms||500)}}))}><div aria-hidden="true" className={`transition-sample sample-${key}`}><span>A</span><span>B</span></div><span>{label}</span></button>)}</div><p className="hint">Select the incoming part, then a transition. Adjust its duration above the tracks.</p></>}
      </div><div className="sidebar-bottom"><span className="status-dot"/> Local workspace<span>Scene editor</span></div></>}
      </nav>
      <main className="editing-area">
        {project.scenes.map((scene,i)=><PartRow layerActions={layerActions} key={`${scene.id}-${editorEpoch}`} scene={scene} project={project} index={i} total={project.scenes.length} active={selected?.id===scene.id} txPreview={hoverTx&&selected&&project.scenes.indexOf(selected)>0?{key:hoverTx,from:project.scenes[project.scenes.indexOf(selected)-1]?.shots[0]?.asset_id||null,to:selected.shots[0]?.asset_id||null}:null} refresh={refresh} onMove={dir=>moveScene(scene.id,dir)} onDelete={()=>deleteScene(scene.id)} onOpenSettings={()=>openSettings('providers')} onSaveState={(id,state)=>setStates(prev=>({...prev,[id]:state}))} onRecord={record} removeNarration={removeNarration} selectedAudioClipId={selectedAudioClipId} onSelectAudioClip={setSelectedAudioClipId} onUpdateAudioClips={updateProjectAudioClips}/>)}
        {!project.scenes.length&&project.finishing_json?.free_timeline?.enabled&&selectedLayerId&&project.finishing_json.layer_clips?.find(c=>c.id===selectedLayerId)&&<LayerInspector clip={project.finishing_json.layer_clips.find(c=>c.id===selectedLayerId)!} project={project} actions={layerActions} length={86400000} onClose={()=>setSelectedLayerId('')}/>}
        {!project.scenes.length&&project.finishing_json?.free_timeline?.enabled&&selectedAudioClipId&&<FinishingPanel project={project} disabled={busy||exporting} selectedClipId={selectedAudioClipId} onSelectClip={setSelectedAudioClipId} onChanged={refresh} onUpdateAudioClips={updateProjectAudioClips}/>}
        {!project.scenes.length&&<div className="empty-project"><Film size={40}/><h2>Your story starts here</h2><button className="btn btn-primary" disabled={busy} onClick={addPart}><Plus size={16}/> Add your first scene</button></div>}
        <div id="sequence-viewer"/>
      </main>
    </div>
    {project.finishing_json?.free_timeline?.enabled&&!freeSourceView?<FreeTimeline project={project} disabled={busy||exporting} onEdit={updateFreeTimeline} onSelectScene={setSelectedId} layerActions={layerActions} onSelectAudio={setSelectedAudioClipId} onUndo={undoTimeline} onRedo={redoTimeline} canUndo={!!history.length} canRedo={!!future.length} onExport={()=>void renderFullVideo()} onRefresh={refresh} onViewSources={()=>setFreeSourceView(true)}/>:<><div className="free-timeline-switch">{freeSourceView&&project.finishing_json?.free_timeline?.enabled&&<><p role="status">Original source scenes · Free timeline cuts stay saved and are used for export. Source edits affect every linked excerpt.</p><button disabled={busy||exporting||dirty} onClick={()=>void updateFreeTimeline({free_timeline:{...project.finishing_json!.free_timeline!,enabled:false}},"use scene assembly for export")}>Use Scene assembly for export</button></>}<button disabled={busy||exporting} title="Place scene excerpts, images, video, text and audio anywhere on project tracks. Existing scene order stays available." onClick={()=>void openFreeTimeline()}>Free timeline · move clips anywhere</button></div>
    <ProjectTimeline exportLayers={exportLayers} layerActions={layerActions} onSelectAll={()=>setMulti(project.scenes.map(s=>s.id))} onDetachAudio={(sceneId,source,placeMs,shotId,durationMs)=>void detachAudio(sceneId,source,placeMs,shotId,durationMs)} onUpdateTimeline={(next,options)=>void updateTimelineSettings(next,options)} notice={importStatus} onDropFiles={(id,files,insert)=>void dropFilesOnTimeline(id,files,insert)} onDropAssets={(id,assets,insert)=>void dropAssetsOnTimeline(id,assets,insert)} onDuration={resizeDuration} onTrimShot={(sceneId,shotId,sourceIn,sourceOut)=>{const shot=project.scenes.find(s=>s.id===sceneId)?.shots.find(x=>x.id===shotId);if(shot){const before={source_in_ms:shot.source_in_ms,source_out_ms:shot.source_out_ms};void record("trim video clip",()=>api.updateShot(shotId,before),()=>api.updateShot(shotId,{source_in_ms:sourceIn,source_out_ms:sourceOut}));}}} onRender={()=>void renderFullVideo()} onRefresh={()=>refresh()} exportScenes={exportScenes} exportAsset={exportJob?.status==="succeeded"?exportJob.artifact_asset_id:null} project={project} selectedId={selected?.id||""} selectedAudioClipId={selectedAudioClipId} onAudioClipSelect={setSelectedAudioClipId} onUpdateAudioClips={clips=>void updateProjectAudioClips(clips)} disabled={busy||exporting} onSelect={setSelectedId} onAdd={addPart} multi={multi} onSelectScenes={ids=>{setMulti(ids);if(ids[0])setSelectedId(ids[0]);}} onMulti={(id,mode)=>{if(!project)return;setMulti(m=>{if(mode==='clear')return [];const base=m.length?m:(selected?[selected.id]:[]);if(mode==='toggle')return base.includes(id)?base.filter(x=>x!==id):[...base,id];const ids=project.scenes.map(x=>x.id),a=ids.indexOf(selected?.id||id),b=ids.indexOf(id);return ids.slice(Math.min(a,b),Math.max(a,b)+1);});}} clipboard={clip} onClipboard={c=>{setClip(c);setImportStatus(c.kind==='scene'?`Copied scene “${c.label}”. Select a scene and press Ctrl+V (or right-click → Paste) to paste it after that scene.`:`Copied ${c.label}. Select another scene's narration and press Ctrl+V to paste.`);}} onDuplicate={id=>void duplicateScene(id)} onPaste={id=>void pasteClip(id)} onReorder={ids=>record('scene order',()=>api.reorderScenes(project.id,project.scenes.map(s=>s.id)),()=>api.reorderScenes(project.id,ids))} onUpdate={(id,patch)=>record('transition',()=>api.updateScene(id,{transition_in:project.scenes.find(s=>s.id===id)!.transition_in_json}),()=>api.updateScene(id,patch))} onDelete={()=>selected&&void deleteScene(selected.id)} onDeleteScene={id=>void deleteScene(id)} onToggleClipAudio={(shotId,audio)=>{const shot=project.scenes.flatMap(s=>s.shots).find(x=>x.id===shotId);if(!shot)return;const before=shot.audio_json||{volume:100,mute:false,duck:true};void record('toggle clip sound',()=>api.updateShot(shotId,{audio:before}),()=>api.updateShot(shotId,{audio}));}} onAudio={()=>audioImportRef.current?.click()} onRemoveAudio={()=>selected&&void removeNarration(selected)} onRemoveSceneAudio={id=>{const s=project.scenes.find(x=>x.id===id);if(s)void removeNarration(s);}} onUndo={undoTimeline} onRedo={redoTimeline} canUndo={!!history.length} canRedo={!!future.length} onSplit={(at,baked)=>{if(!selected)return;const snapshot=selected;let rightId="";void record("split scene",async()=>{if(rightId)await api.deleteScene(rightId);await api.restoreScene(snapshot.id,snapshot);setEditorEpoch(v=>v+1);setSelectedId(snapshot.id);},async()=>{const right=await api.splitScene(snapshot.id,at,baked);rightId=right.id;setEditorEpoch(v=>v+1);setSelectedId(right.id);});}}/>
    </>}
    {settingsOpen&&<SettingsPanel key={settingsInitialTab} priority={videoGenOpen} initialTab={settingsInitialTab} onClose={()=>setSettingsOpen(false)} preferences={preferences} onPreferencesChange={updatePreferences} disabled={busy||exporting}/>}

    {infoPanel?.panel==='ai'&&<AIEnginesPanel section={infoPanel.section} onClose={()=>setInfoPanel(null)} onOpenSettings={()=>{setInfoPanel(null);openSettings('providers');}}/>}
    {infoPanel?.panel==='about'&&<AboutPanel onClose={()=>setInfoPanel(null)}/>}
    {infoPanel?.panel==='restore'&&project&&<RestorePoints project={project} onClose={()=>setInfoPanel(null)} onOpen={id=>{setInfoPanel(null);void openProject(id);}}/>}
    {infoPanel?.panel==='shortcuts'&&<ShortcutSheet onClose={()=>setInfoPanel(null)}/>}
    {infoPanel?.panel==='models'&&<ModelManager onClose={()=>setInfoPanel(null)}/>}
    {tourOpen&&<FirstRunTour onClose={()=>setTourOpen(false)}/>}
    <CleanupPanel project={project} disabled={busy||exporting} record={async(...args)=>{await record(...args);}} onUpdateAudioClips={clips=>updateProjectAudioClips(clips)} onDetachNarration={(sceneId,placeMs,then)=>detachAudio(sceneId,'narration',placeMs,undefined,undefined,then)} onScenesChanged={id=>{setEditorEpoch(v=>v+1);setSelectedId(id);}}/>
    {shareOpen&&exportJob?.status==='succeeded'&&exportJob.artifact_asset_id&&<ShareDialog assetId={exportJob.artifact_asset_id} fileName={`${project.title||'SceneForge'}-export.mp4`} onClose={()=>setShareOpen(false)} onReveal={(window as any).sceneforgeDesktop?.revealExport?id=>(window as any).sceneforgeDesktop.revealExport(id):undefined}/>}
  </div>;
}
