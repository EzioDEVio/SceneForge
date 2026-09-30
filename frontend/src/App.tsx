Warning: truncated output (original token count: 34663)
Total output lines: 1243

import {askConfirm} from "./dialogs";
import {registerCloseSave,saveBeforeClose} from "./closeGuard";
import {hasActiveWrites, BUILD_ID} from "./api";
import { previewFontFamily } from "./fonts";
import {Thumb} from "./Thumb";
import {planPoolInsert} from "./poolPlan";
import {planFileDrop, DraggedAsset} from "./timelineDrop";
import {LookPanel, adjustPreviewFilter, WhiteBalanceFilter, PreviewFinish, gradeKey} from "./LookPanel";
import {AudioClipEditor, removeSceneAudio} from "./AudioClipEditor";
import {FilmPreview, filmToneFilter} from "./FilmPreview";
import {FinishingPanel} from "./FinishingPanel";
import {OverlayCanvas, OverlayPanel} from "./Overlays";
import {InspectorResizer} from "./InspectorResizer";
import {AIEnginesPanel, AboutPanel} from "./InfoPanels";
import {CaptionStylePanel, CaptionPreview, AutoCaptions} from "./CaptionsPro";
import {ProgressCard} from "./ProgressCard";
import {BatchBar} from "./BatchBar";
import {ExportDialog} from "./ExportDialog";
import {ShareDialog} from "./ShareDialog";
import VideoGenerationPanel from "./VideoGenerationPanel";
import {FeatureHelp} from "./FeatureHelp";
import {PreferencesPanel} from "./PreferencesPanel";
import {applyPreferences,readPreferences,writePreferences,type AppPreferences} from "./preferences";
import {SceneEffectsPanel, SceneFxPreview, RouteCanvas, AnnotationCanvas} from "./EffectsPanels";
import {SpeedControls, ClipSoundControls} from "./SpeedControls";
import type {CaptionSegment,Overlay} from "./api";
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
  ChevronRight, Layers, Copy, PanelLeftClose, PanelLeftOpen, Search, CheckCircle2, Timer, Clapperboard,
} from "lucide-react";
import { api, subscribeJob, Project, Scene, Shot, Job, VoiceTake, ProviderProfile, Asset, VoiceOption } from "./api";

import {MediaPool} from "./MediaPool";
import {FramingControls} from "./FramingControls";
import { ProjectTimeline, TRANSITIONS } from "./ProjectTimeline";

const ASPECTS = ["16:9", "9:16", "1:1"];

const MOTIONS: { key: string; label: string; Icon: typeof ZoomIn }[] = [
  { key: "zoom_in", label: "Zoom in", Icon: ZoomIn },
  { key: "zoom_out", label: "Zoom out", Icon: ZoomOut },
  { key: "close_up", label: "Close up", Icon: Crosshair },
  { key: "pan_left", label: "Pan left", Icon: ArrowLeft },
  { key: "pan_right", label: "Pan right", Icon: ArrowRight },
  { key: "pan_up", label: "Pan up", Icon: ArrowUp },
  { key: "pan_down", label: "Pan down", Icon: ArrowDown },
  { key: "diagonal_up", label: "Diagonal rise", Icon: ArrowUp },
  { key: "diagonal_down", label: "Diagonal descend", Icon: ArrowDown },
  { key: "push_left", label: "Push & pan left", Icon: ZoomIn },
  { key: "pull_right", label: "Pull & pan right", Icon: ZoomOut },
  { key: "static", label: "Static (no motion)", Icon: MoreHorizontal },
];

const EFFECTS: { key: string; label: string; swatch: string }[] = [
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
];

// Arabic-shaping-correct fonts (bundled, always render identically to
// preview): Noto Naskh/Sans Arabic. The rest are common Windows system
// fonts — they render fine for Latin text, but are NOT guaranteed to
// shape Arabic script correctly (no bundled guarantee), so Arabic
// projects should stick to the Noto options.
const FONT_FAMILIES = [
  // bundled with SceneForge (identical on every computer and in the render)
  "Noto Sans", "Poppins", "Bebas Neue", "Anton", "Pacifico",
  "Noto Naskh Arabic", "Noto Sans Arabic", "Amiri", "Tajawal", "Lalezar",
  // system fonts (may differ between computers)
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
          <p className="hint">Choose the family of your loaded checkpoint. This does not install or switch models. Start with SD 1.5 for your v1-5 checkpoint.</p>
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

const PROVIDER_NOTES:Record<string,string> = {
  openai:"Paid image API. Uses your OpenAI account.",
  gemini:"Image API billing depends on your Google account and model; not advertised as free.",
  cloudflare:"Free daily Workers AI allowance; limits apply. Paid accounts may incur usage charges. FLUX Schnell uses the model’s default composition.",
  huggingface:"Small monthly inference credit, not unlimited free images. Extra usage follows your HF account billing. Model availability varies.",
  together:"Together AI image models, including a limited free FLUX Schnell model. Usage and quota follow your account.",
  local_sd:"Runs on your computer. Install AUTOMATIC1111 and an image checkpoint, then start it with --api. No API key or Docker required. GPU memory limits apply; model downloads are separate. Use current to keep the loaded model.",
  elevenlabs:"Hosted multilingual voice generation. Usage and quota follow your ElevenLabs account.",
  local_comfy:"Runs open-weight video models on your computer through ComfyUI. Model files and trusted API workflows are downloaded/imported separately; no API key or per-video provider fee. GPU, RAM and disk requirements vary by model.",
  google_veo:"Paid cloud video generation through Google Gemini API. Add a Google AI Studio key. SceneForge displays an estimate before submission; Google controls final billing.",
  runway:"Paid cloud video generation through Runway API. Add a Runway developer key and credits. SceneForge displays an estimate before submission; Runway controls final billing.",
};
const PROVIDER_OPTIONS = [
  {name:"cloudflare", label:"Cloudflare · Free allowance", capability:"image", model:"@cf/black-forest-labs/flux-1-schnell", url:""},
  {name:"huggingface", label:"Hugging Face · Limited credits", capability:"image", model:"black-forest-labs/FLUX.1-schnell", url:""},
  {name:"together", label:"Together AI · FLUX images", capability:"image", model:"black-forest-labs/FLUX.1-schnell-Free", url:""},
  {name:"local_sd", label:"Local · Stable Diffusion", capability:"image", model:"current", url:"http://127.0.0.1:7860"},
  {name:"openai", label:"OpenAI · Images", capability:"image", model:"gpt-image-1", url:""},
  {name:"gemini", label:"Google Gemini · Images", capability:"image", model:"gemini-3.1-flash-image", url:""},
  {name:"elevenlabs", label:"ElevenLabs · Voice", capability:"speech", model:"eleven_multilingual_v2", url:"https://api.elevenlabs.io/v1"},
  {name:"local_comfy", label:"Local · ComfyUI video", capability:"video", model:"ComfyUI local video engine", url:"http://127.0.0.1:8188"},
  {name:"google_veo", label:"Google Veo · Video", capability:"video", model:"veo-3.1-generate-preview", url:""},
  {name:"runway", label:"Runway · Video", capability:"video", model:"gen4.5", url:""},
];
function SettingsPanel({ onClose, priority = false, initialTab = 'preferences', preferences, onPreferencesChange, project, onProjectSetupChange, disabled = false }: {
  onClose: () => void; priority?: boolean; initialTab?: 'preferences'|'providers'; preferences: AppPreferences;
  onPreferencesChange: (patch:Partial<AppPreferences>)=>void; project?:Project|null;
  onProjectSetupChange?: (aspect:string,fps:number)=>void|Promise<void>; disabled?:boolean;
}) {
  const drawerRef = useDrawerFocus(onClose);
  const [tab,setTab]=useState<'preferences'|'providers'>(initialTab);
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
    <h3>Settings — {tab==='preferences'?'Preferences':'AI providers'}</h3>
    <div className="settings-tabs" role="tablist" aria-label="Settings sections"><button role="tab" aria-selected={tab==='preferences'} onClick={()=>setTab('preferences')}>Preferences</button><button role="tab" aria-selected={tab==='providers'} onClick={()=>setTab('providers')}>AI providers</button></div>
    {tab==='preferences'?<PreferencesPanel value={preferences} onChange={onPreferencesChange} project={project} onProjectSetup={onProjectSetupChange} disabled={disabled}/>:<>
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
          <section className="local-voice-component"><h3>Local voice engines</h3><p className="hint">Natural speech runs on this computer after the engine and model are installed. No AI provider key is required.</p><div className="button-row"><button className="btn" disabled={busy} onClick={()=>connectEngine("chatterbox")}>Connect Chatterbox · Arabic + multilingual</button><button className="btn" disabled={busy} onClick={()=>connectEngine("kokoro")}>Connect Kokoro</button></div><p className="hint">Connect to your installed voice service. For a Docker installation, keep its engine and voice container running. Enter narration text before generating audio.</p>{localStatus&&<p role="status">{localStatus}</p>}</section>
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
  …14663 tokens truncated…unknown>){
    if(await action(async()=>{await redo();await refresh();})){setHistory(h=>[...h.slice(-99),{undo,redo,label}]);setFuture([]);}
  }
  async function undoTimeline(){const item=history[history.length-1];if(item&&await action(async()=>{await item.undo();await refresh();})){setHistory(h=>h.slice(0,-1));setFuture(f=>[...f,item]);}}
  async function redoTimeline(){const item=future[future.length-1];if(item&&await action(async()=>{await item.redo();await refresh();})){setFuture(f=>f.slice(0,-1));setHistory(h=>[...h,item]);}}
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
  async function dropFilesOnTimeline(sceneId:string|null,files:File[],insert?:{before?:string;after?:string}){
    if(!project)return;
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
  async function dropAssetsOnTimeline(sceneId:string|null,dragged:DraggedAsset[],insert?:{before?:string;after?:string}){
    if(!project)return;
    const audio=dragged.filter(a=>a.type==='audio'),visual=dragged.filter(a=>a.type==='image'||a.type==='video');
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
  useEffect(()=>{const close=(e:MouseEvent)=>{if(!(e.target as Element).closest('.editor-menu'))setMenu('');};const escape=(e:KeyboardEvent)=>{if(e.key==='Escape')setMenu('');};document.addEventListener('click',close);document.addEventListener('keydown',escape);return()=>{document.removeEventListener('click',close);document.removeEventListener('keydown',escape);};},[]);
  const [exportScenes,setExportScenes] = useState<Scene[]>([]);
  const [exportJobId, setExportJobId] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsInitialTab,setSettingsInitialTab]=useState<'preferences'|'providers'>('preferences');
  function openSettings(tab:'preferences'|'providers'='preferences') {setSettingsInitialTab(tab);setSettingsOpen(true);}
  const [infoPanel, setInfoPanel] = useState<{panel:string;section?:string}|null>(null);
  useEffect(()=>{const open=(e:Event)=>setInfoPanel((e as CustomEvent).detail||null);window.addEventListener('sceneforge-open-panel',open);return()=>window.removeEventListener('sceneforge-open-panel',open);},[]);
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
  useEffect(()=>{if(exportJob?.status==='succeeded'&&exportJob.artifact_asset_id&&sharedExport.current!==exportJob.id){sharedExport.current=exportJob.id;setShareOpen(true);}},[exportJob?.id,exportJob?.status,exportJob?.artifact_asset_id]);
  const dirty = Object.values(states).some(s => s !== "Saved");
  const statesRef = useRef(states); statesRef.current = states;
  const [clip, setClip] = useState<{kind:'scene'|'audio';id:string;label:string}|null>(null);
  const [hoverTx, setHoverTx] = useState<string|null>(null);   // transition previewed on the picture
  const [multi, setMulti] = useState<string[]>([]);            // several parts selected on the timeline
  const [exportOpen, setExportOpen] = useState(false);
  const [videoGenOpen,setVideoGenOpen]=useState(false);
  const [projectMode, setProjectMode] = useState<'new'|'open'>('open');
  /** Back to the project list (to start a new project or open another), after saves finish. */
  async function goToProjects(mode:'new'|'open'){
    for(let i=0;i<40&&Object.values(statesRef.current).some(v=>v!=="Saved");i++)await new Promise(r=>setTimeout(r,250));
    await action(async()=>{setProjects(await api.listProjects());projectRef.current=null;setProject(null);setProjectMode(mode);});
  }
  useEffect(()=>{
    const onPanel=(e:Event)=>{const d=(e as CustomEvent).detail;if(d?.panel==='projects')void goToProjects(d.mode==='open'?'open':'new');};
    const onKey=(e:KeyboardEvent)=>{const t=e.target as HTMLElement|null;if(!(e.ctrlKey||e.metaKey)||t?.closest('input,textarea,select,[contenteditable="true"]'))return;
      if(e.key.toLowerCase()==='n'){e.preventDefault();void goToProjects('new');}else if(e.key.toLowerCase()==='o'){e.preventDefault();void goToProjects('open');}};
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
  const status = failed ? "Save failed" : dirty ? "Saving changes…" : "All changes saved";
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
  async function renderFullVideo(settings?: Record<string, unknown>){
    if(!project||busy||exporting)return;
    // Background saves no longer lock the timeline; wait for them before exporting.
    for(let i=0;i<40&&Object.values(statesRef.current).some(v=>v!=="Saved");i++)await new Promise(r=>setTimeout(r,250));
    if(Object.values(statesRef.current).some(v=>v!=="Saved")){setImportStatus("Changes are still saving. Try Render full video again in a moment.");return;}
    await action(async()=>{const empty=project.scenes.filter(s=>!s.shots.length);
      if(!project.scenes.some(s=>s.shots.length))return;
      if(empty.length&&!await askConfirm(`Skip ${empty.length} empty scene(s) and render all scenes with media?`))return;
      setExportPanel(true);setExportExpanded(false);setExportScenes(structuredClone(project.scenes));
      setExportJobId((await api.exportProject(project.id,empty.length>0,settings||{quality:'draft'})).job_id);
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
  async function updateProjectPageSetup(aspect:string,fps:number) {
    if(!project||(aspect===project.aspect&&fps===project.fps))return;
    const ok=await action(async()=>{await api.updateProject(project.id,{aspect,fps});await refresh();});
    if(!ok)throw new Error("Could not save the page setup. Check the save status and try again.");
  }
  async function resizeDuration(id:string,ms:number){
    const scene=project?.scenes.find(s=>s.id===id);if(!scene)return;
    const take=scene.voice_takes.find(t=>t.accepted);
    if(take&&ms<(take.effective_duration_ms??take.measured_duration_ms??0)+(scene.lead_ms||0)+(scene.trail_ms||0)&&!await askConfirm('This duration may cut narration short. Switch to fixed timing?'))return;
    await record('duration',()=>api.updateScene(id,{timing_mode:scene.timing_mode,requested_duration_ms:scene.requested_duration_ms}),()=>api.updateScene(id,{timing_mode:'fixed',requested_duration_ms:ms}));
  }
  const [titleCard,setTitleCard]=useState(false);
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
    if(!await askConfirm("Delete this scene? You can undo this from Edit → Undo.")) return;
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
  if(!project) return <main className="project-home"><BuildNotice/>
    <div className="project-home-header"><div className="brand"><span className="brand-mark"><Film size={22}/></span> SceneForge <span className="version-chip">STUDIO</span></div><button className="btn" onClick={()=>openSettings('preferences')}><Settings size={14}/> Preferences</button></div>
    <section className="home-intro"><span className="eyebrow">YOUR STORY, FRAME BY FRAME</span><h1>Make room for<br/>your next story.</h1><p>Turn scripts, images, and narration into a video.<br/>One scene at a time.</p></section>
    {error && <div role="alert" className="error-box">{error}</div>}
    <section className="new-project"><div><h2>Create a project</h2><p className="hint">Start with three scenes. Add more as your story grows.</p></div><div className="create-form"><label className="control-label">Project name<input autoFocus={projectMode==='new'} aria-label="New project name" value={newTitle} onChange={e=>setNewTitle(e.target.value)}/></label><label className="control-label">Format<select aria-label="New project aspect ratio" value={newAspect} onChange={e=>setNewAspect(e.target.value as AppPreferences['defaultAspect'])}>{ASPECTS.map(a=><option key={a}>{a}</option>)}</select></label><label className="control-label">Frame rate<select aria-label="New project frame rate" value={newFps} onChange={e=>setNewFps(Number(e.target.value) as AppPreferences['defaultFps'])}>{[24,25,30,50,60].map(f=><option key={f} value={f}>{f} fps</option>)}</select></label><button className="btn btn-primary" disabled={busy} onClick={createProject}><Plus size={16}/> Create project</button></div></section>
    <div className="section-heading"><h2>Your projects</h2><span className="subtle">{projects.length} projects</span></div>
    <label className="search-control"><Search size={16}/><input aria-label="Search projects" placeholder="Find a project…" value={projectSearch} onChange={e=>setProjectSearch(e.target.value)}/></label>
    {loading ? <p role="status">Loading projects…</p> : <div className="project-grid">{projects.filter(p=>p.title.toLowerCase().includes(projectSearch.toLowerCase())).map(p=><article className="project-tile" key={p.id}><button className="project-open-button" disabled={busy} onClick={()=>openProject(p.id)}><div className="project-cover"><Film size={30}/><span>{p.aspect}</span></div><strong>{p.title}</strong><span className="project-open">Open project <ArrowRight size={15}/></span></button><button className="text-btn project-delete" aria-label={`Delete project ${p.title}`} disabled={busy} onClick={()=>removeProject(p)}><Trash2 size={14}/> Delete</button></article>)}{!projects.filter(p=>p.title.toLowerCase().includes(projectSearch.toLowerCase())).length&&<p className="hint">{projects.length?"No matching projects.":"Your saved projects will appear here."}</p>}</div>}
    {settingsOpen&&<SettingsPanel key={settingsInitialTab} initialTab={settingsInitialTab} onClose={()=>setSettingsOpen(false)} preferences={preferences} onPreferencesChange={updatePreferences} project={null}/>}
  </main>;
  return <div className="studio-shell"><BuildNotice/>
    <header className="studio-toolbar">
      <button className="brand brand-button" title="Back to projects" disabled={dirty||busy||exporting} onClick={()=>action(async()=>{setProjects(await api.listProjects()); projectRef.current=null; setProject(null);})}><span className="brand-mark"><Film size={19}/></span><span>SceneForge</span></button>
      <span className="toolbar-divider"/>
      <div className="project-identity"><input aria-label="Project name" value={titleDraft} onChange={e=>{setTitleDraft(e.target.value); setStates(prev=>({...prev,title:"Unsaved changes"}));}} onBlur={()=>void saveTitle()}/><span role="status" className={`save-status ${failed ? "save-error" : ""}`}>{busy ? "Saving…" : status}</span></div>
      <div className="toolbar-end"><select aria-label="Project aspect ratio" value={project.aspect} disabled={busy||exporting} onChange={e=>action(async()=>{await api.updateProject(project.id,{aspect:e.target.value}); await refresh();})}>{ASPECTS.map(a=><option key={a}>{a}</option>)}</select><button className="icon-btn" title="Settings" aria-label="Settings" onClick={()=>openSettings('preferences')}><Settings size={18}/></button><button className="btn video-gen-launch" disabled={busy||exporting} onClick={()=>setVideoGenOpen(true)}><Clapperboard size={15}/>Generate video</button><button className="btn btn-primary" disabled={exporting||dirty||busy||!project.scenes.length} onClick={()=>setExportOpen(true)}><Upload size={15}/>{exporting ? `Exporting ${Math.round(exportJob?.progress||0)}%` : "Export video"}</button></div>
    </header>
    {titleCard&&<TitleDesigner width={project.width} height={project.height} busy={busy} onClose={()=>setTitleCard(false)} onCreate={d=>void addTitleCard(d)}/>}
    {project&&multi.length>1&&selected&&<BatchBar source={selected} scenes={project.scenes.filter(x=>multi.includes(x.id))} onClear={()=>setMulti([])} onDone={()=>void refresh()}/>}
    {exportOpen&&project&&<ExportDialog project={project} onClose={()=>setExportOpen(false)} onExport={settings=>{setExportOpen(false);void renderFullVideo(settings);}}/>}
    {videoGenOpen&&project&&<VideoGenerationPanel project={project} selectedSceneId={selected?.id||null} onClose={()=>setVideoGenOpen(false)} onOpenSettings={()=>openSettings('providers')} onAdd={addGeneratedVideoToTimeline} onCaptions={captionGeneratedScene}/>}
    {exporting&&exportJob&&<ProgressCard floating title="Exporting video" stage={exportJob.stage} progress={exportJob.progress||0} status={exportJob.status} onCancel={()=>void api.cancelJob(exportJob.id).catch(()=>{})}/>}
    {(error||exportJob?.status==="failed")&&<div role="alert" className="error-box"><details><summary>Operation failed — show details</summary><pre>{error||exportJob?.error}</pre></details><button className="text-btn" onClick={()=>{setError(null);if(exportJob?.status==='failed')setExportJobId(null);}}>Dismiss</button></div>}
    <div className="editor-menubar">
      {['File','AI Engines','Edit','View','Help'].map(name=><div className="editor-menu" key={name}><button aria-expanded={menu===name} onClick={()=>{if(name==='AI Engines'){setInfoPanel({panel:'ai'});setMenu('');}else setMenu(menu===name?'':name);}}>{name}</button>{menu===name&&<div className="editor-menu-items">
       {name==='File'&&<><button disabled={busy||exporting} onClick={()=>{setMenu('');void goToProjects('new');}}>New project… <kbd>Ctrl+N</kbd></button><button disabled={busy||exporting} onClick={()=>{setMenu('');void goToProjects('open');}}>Open project… <kbd>Ctrl+O</kbd></button><button disabled={busy||exporting} onClick={()=>{setMenu('');void addPart();}}>New scene</button><button disabled={busy||exporting} onClick={()=>{setMenu('');setVideoGenOpen(true);}}>Generate video from text…</button><button disabled={busy||exporting} onClick={()=>importRef.current?.click()}>Import files to Media Pool…</button><button disabled={busy||exporting} onClick={()=>folderRef.current?.click()}>Import folder to Media Pool…</button><button disabled={!selected||busy||exporting} onClick={()=>audioImportRef.current?.click()}>Import audio to selected scene…</button><button onClick={()=>{setMenu('');openSettings('providers');}}>Provider settings…</button></>}
       {name==='Edit'&&<><button disabled={!history.length||busy||dirty||exporting} onClick={()=>{setMenu('');void undoTimeline();}}>Undo {history[history.length-1]?.label||'timeline edit'}</button><button disabled={!future.length||busy||dirty||exporting} onClick={()=>{setMenu('');void redoTimeline();}}>Redo {future[future.length-1]?.label||'timeline edit'}</button><button disabled={!selected||busy||exporting} onClick={()=>{setMenu('');if(selected)void deleteScene(selected.id);}}>Delete selected scene…</button></>}
       {name==='View'&&<><button onClick={()=>{setSidebar(!sidebar);setMenu('');}}>Toggle scene library</button><button onClick={()=>{document.querySelector('.studio-shell')?.classList.toggle('inspector-hidden');setMenu('');}}>Toggle inspector</button><button onClick={()=>{setExportPanel(!exportPanel);setMenu('');}}>Show / hide export result</button><button onClick={()=>{setMenu('');if(document.fullscreenElement)void document.exitFullscreen();else void document.documentElement.requestFullscreen();}}>Fullscreen / restore</button></>}
       {name==='Help'&&<button onClick={()=>{setMenu('');setInfoPanel({panel:'about'});}}>About SceneForge</button>}
      </div>}</div>)}<span className="menu-help">Import audio into A1 · Scissors: choose a cut position · Render complex scenes before cutting</span>
    </div>
    <input hidden ref={importRef} type="file" accept="image/*,video/*,audio/*" multiple onChange={e=>{void importMedia(e.target.files);e.target.value='';}}/>
    <input hidden ref={folderRef} type="file" multiple {...{webkitdirectory:''} as any} onChange={e=>{void importMedia(e.target.files);e.target.value='';}}/>
    <input hidden ref={audioImportRef} type="file" accept="audio/*" onChange={e=>{void importAudio(e.target.files?.[0]);e.target.value='';}}/>
    {exportPanel&&exportJob?.status==='succeeded'&&exportJob.artifact_asset_id&&<section className="export-result" aria-label="Export result"><header><CheckCircle2 size={16}/><span>Last export ready · Export again after edits</span><a href={api.assetDownloadUrl(exportJob.artifact_asset_id)} download>Download MP4</a><button className="text-btn" onClick={()=>setShareOpen(true)}>Share…</button><button aria-label={exportExpanded?'Minimize export result':'Expand export result'} onClick={()=>setExportExpanded(!exportExpanded)}>{exportExpanded?'−':'+'}</button><button aria-label="Close export result" onClick={()=>setExportPanel(false)}><X size={14}/></button></header>{exportExpanded&&<video controls src={api.assetStreamUrl(exportJob.artifact_asset_id)}/>}</section>}
    <div className={`workspace ${sidebar ? "" : "sidebar-collapsed"}`}>
      <nav className="scene-sidebar" aria-label="Scenes"><div className="sidebar-header"><h2><Layers size={16}/> Scenes <span className="count-badge">{project.scenes.length}</span></h2><button className="icon-btn" aria-label={sidebar?"Collapse scene list":"Expand scene list"} title={sidebar?"Collapse scene list":"Expand scene list"} onClick={()=>setSidebar(!sidebar)}>{sidebar?<PanelLeftClose size={16}/>:<PanelLeftOpen size={16}/>}</button></div>
      {sidebar&&<><div className="library-tabs" aria-label="Asset library">{(['Scenes','Media Pool','Transitions'] as const).map(t=><button key={t} aria-pressed={libraryTab===t} onClick={()=>setLibraryTab(t)}>{t}</button>)}</div>
      <div className="library-content">
      {libraryTab==='Media Pool'&&<>{importStatus&&<p className="hint" aria-live="polite">{importStatus}</p>}<MediaPool projectId={project.id} version={mediaVersion} disabled={busy||exporting} onImport={()=>importRef.current?.click()} onFolder={()=>folderRef.current?.click()} onAdd={addPoolAssets} onUse={usePoolAsset} canUse={!!selected}/></>}

      {libraryTab==='Scenes'&&<><p className="sidebar-hint">PROJECT BIN · Select a part to edit</p><div className="scene-list">{project.scenes.map((s,i)=><button key={s.id} className={`scene-nav ${selected?.id===s.id?"selected":""}`} aria-label={`Select scene ${i+1}: ${s.title}`} aria-current={selected?.id===s.id?"true":undefined} onClick={()=>setSelectedId(s.id)}><div className="scene-thumb">{s.shots[0]?<Thumb assetId={s.shots[0].asset_id} type={s.shots[0].asset?.type}/>:<Film size={22}/>}<span>{String(i+1).padStart(2,"0")}</span></div><div className="scene-nav-meta"><strong>{s.title}</strong><span>{durationLabel(s)} · {s.shots.length} media</span></div></button>)}</div><button className="btn add-scene" disabled={busy||exporting} onClick={()=>setTitleCard(true)}><Type size={16}/> Add title card</button><button className="btn add-scene" disabled={busy} onClick={addPart}><Plus size={16}/> Add scene</button></>}
      {libraryTab==='Transitions'&&<><p className="sidebar-hint">INCOMING TO · {selected?.title||'Select a part'}</p><div className="library-presets transition-presets">{TRANSITIONS.map(([key,label])=><button key={key} onMouseEnter={()=>setHoverTx(key)} onMouseLeave={()=>setHoverTx(null)} onFocus={()=>setHoverTx(key)} onBlur={()=>setHoverTx(null)} aria-pressed={selected?.transition_in_json.type===key} disabled={!selected?.shots.length||selected.id===project.scenes.find(s=>s.shots.length)?.id||busy||exporting} onClick={()=>selected&&record('transition',()=>api.updateScene(selected.id,{transition_in:selected.transition_in_json}),()=>api.updateScene(selected.id,{transition_in:{type:key,duration_ms:key==='cut'?0:(selected.transition_in_json.duration_ms||500)}}))}><div aria-hidden="true" className={`transition-sample sample-${key}`}><span>A</span><span>B</span></div><span>{label}</span></button>)}</div><p className="hint">Select the incoming part, then a transition. Adjust its duration above the tracks.</p></>}
      </div><div className="sidebar-bottom"><span className="status-dot"/> Local workspace<span>Scene editor</span></div></>}
      </nav>
      <main className="editing-area">
        {project.scenes.map((scene,i)=><PartRow key={`${scene.id}-${editorEpoch}`} scene={scene} project={project} index={i} total={project.scenes.length} active={selected?.id===scene.id} txPreview={hoverTx&&selected&&project.scenes.indexOf(selected)>0?{key:hoverTx,from:project.scenes[project.scenes.indexOf(selected)-1]?.shots[0]?.asset_id||null,to:selected.shots[0]?.asset_id||null}:null} refresh={refresh} onMove={dir=>moveScene(scene.id,dir)} onDelete={()=>deleteScene(scene.id)} onOpenSettings={()=>openSettings('providers')} onSaveState={(id,state)=>setStates(prev=>({...prev,[id]:state}))} onRecord={record} removeNarration={removeNarration}/>)}
        {!project.scenes.length&&<div className="empty-project"><Film size={40}/><h2>Your story starts here</h2><button className="btn btn-primary" disabled={busy} onClick={addPart}><Plus size={16}/> Add your first scene</button></div>}
        <div id="sequence-viewer"/>
      </main>
    </div>
    <ProjectTimeline notice={importStatus} onDropFiles={(id,files,insert)=>void dropFilesOnTimeline(id,files,insert)} onDropAssets={(id,assets,insert)=>void dropAssetsOnTimeline(id,assets,insert)} onDuration={resizeDuration} onTrimShot={(sceneId,shotId,sourceIn,sourceOut)=>{const shot=project.scenes.find(s=>s.id===sceneId)?.shots.find(x=>x.id===shotId);if(shot){const before={source_in_ms:shot.source_in_ms,source_out_ms:shot.source_out_ms};void record("trim video clip",()=>api.updateShot(shotId,before),()=>api.updateShot(shotId,{source_in_ms:sourceIn,source_out_ms:sourceOut}));}}} onRender={()=>void renderFullVideo()} exportScenes={exportScenes} exportAsset={exportJob?.status==="succeeded"?exportJob.artifact_asset_id:null} project={project} selectedId={selected?.id||""} disabled={busy||exporting} onSelect={setSelectedId} onAdd={addPart} multi={multi} onMulti={(id,mode)=>{if(!project)return;setMulti(m=>{if(mode==='clear')return [];const base=m.length?m:(selected?[selected.id]:[]);if(mode==='toggle')return base.includes(id)?base.filter(x=>x!==id):[...base,id];const ids=project.scenes.map(x=>x.id),a=ids.indexOf(selected?.id||id),b=ids.indexOf(id);return ids.slice(Math.min(a,b),Math.max(a,b)+1);});}} clipboard={clip} onClipboard={c=>{setClip(c);setImportStatus(c.kind==='scene'?`Copied scene “${c.label}”. Select a scene and press Ctrl+V (or right-click → Paste) to paste it after that scene.`:`Copied ${c.label}. Select another scene's narration and press Ctrl+V to paste.`);}} onDuplicate={id=>void duplicateScene(id)} onPaste={id=>void pasteClip(id)} onReorder={ids=>record('scene order',()=>api.reorderScenes(project.id,project.scenes.map(s=>s.id)),()=>api.reorderScenes(project.id,ids))} onUpdate={(id,patch)=>record('transition',()=>api.updateScene(id,{transition_in:project.scenes.find(s=>s.id===id)!.transition_in_json}),()=>api.updateScene(id,patch))} onDelete={()=>selected&&void deleteScene(selected.id)} onAudio={()=>audioImportRef.current?.click()} onRemoveAudio={()=>selected&&void removeNarration(selected)} onRemoveSceneAudio={id=>{const s=project.scenes.find(x=>x.id===id);if(s)void removeNarration(s);}} onUndo={undoTimeline} onRedo={redoTimeline} canUndo={!!history.length} canRedo={!!future.length} onSplit={(at,baked)=>{if(!selected)return;const snapshot=selected;let rightId="";void record("split scene",async()=>{if(rightId)await api.deleteScene(rightId);await api.restoreScene(snapshot.id,snapshot);setEditorEpoch(v=>v+1);setSelectedId(snapshot.id);},async()=>{const right=await api.splitScene(snapshot.id,at,baked);rightId=right.id;setEditorEpoch(v=>v+1);setSelectedId(right.id);});}}/>
    {settingsOpen&&<SettingsPanel key={settingsInitialTab} priority={videoGenOpen} initialTab={settingsInitialTab} onClose={()=>setSettingsOpen(false)} preferences={preferences} onPreferencesChange={updatePreferences} project={project} onProjectSetupChange={updateProjectPageSetup} disabled={busy||exporting}/>}

    {infoPanel?.panel==='ai'&&<AIEnginesPanel section={infoPanel.section} onClose={()=>setInfoPanel(null)} onOpenSettings={()=>{setInfoPanel(null);openSettings('providers');}}/>}
    {infoPanel?.panel==='about'&&<AboutPanel onClose={()=>setInfoPanel(null)}/>}
    {shareOpen&&exportJob?.status==='succeeded'&&exportJob.artifact_asset_id&&<ShareDialog assetId={exportJob.artifact_asset_id} fileName={`${project.title||'SceneForge'}-export.mp4`} onClose={()=>setShareOpen(false)} onReveal={(window as any).sceneforgeDesktop?.revealExport?id=>(window as any).sceneforgeDesktop.revealExport(id):undefined}/>}
  </div>;
}
