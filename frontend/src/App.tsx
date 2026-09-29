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
function SettingsPanel({ onClose, priority = false }: { onClose: () => void; priority?: boolean }) {
  const drawerRef = useDrawerFocus(onClose);
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
    <h3>Settings — Providers</h3><p className="hint">Connect the image or video provider you want to use. Cloud API keys are protected by your operating system's credential store and are used only for your requests.</p><p className="hint">Local video generation uses ComfyUI and model files installed on this computer. Local narration engines are managed separately under Audio → Local voice engines.</p>
    <div className="provider-list">{providers.filter(p=>PROVIDER_OPTIONS.some(o=>o.name===p.name)).map(p=><article className="provider-card" key={p.id}><strong>{PROVIDER_OPTIONS.find(o=>o.name===p.name)?.label||p.name}</strong><small>{p.capability} · {p.model} · {p.masked_key||"No key required"}</small><div className="button-row"><button className="text-btn" disabled={busy} onClick={()=>select(p.name)}>Edit</button><button className="text-btn" disabled={busy} onClick={async()=>{try{await api.deleteProviderProfile(p.id);await refresh();window.dispatchEvent(new Event("sceneforge:providers-changed"));}catch(e:any){setMessage(e.message);}}}>Remove</button></div></article>)}</div>
    <fieldset disabled={busy} className="provider-form"><label className="control-label">Provider<select aria-label="Provider" value={name} onChange={e=>select(e.target.value)}>{PROVIDER_OPTIONS.map(o=><option value={o.name} key={o.name}>{o.label}</option>)}</select></label>
    <p className="hint">{PROVIDER_NOTES[name]}</p>
    {(name==="cloudflare"||name==="local_sd"||name==="elevenlabs"||name==="local_comfy")&&<label className="control-label">{name==="cloudflare"?"Cloudflare account ID":name==="elevenlabs"?"ElevenLabs API URL":"Local engine URL"}<input aria-label="Provider connection" value={url} onChange={e=>setUrl(e.target.value)}/></label>}
    <label className="control-label">Model<input disabled={name==="cloudflare"||choice.capability==="video"} aria-label="Provider model" value={model} onChange={e=>setModel(e.target.value)}/></label>

    {name!=="local_sd"&&name!=="local_comfy"&&<label className="control-label">{choice.capability==="image"?"API key (re-enter to save)":"Service token"}<input aria-label="Provider API key" type="password" autoComplete="off" value={key} onChange={e=>setKey(e.target.value)}/></label>}
    <button className="btn btn-primary" disabled={busy||(name!=="local_sd"&&name!=="local_comfy"&&!key.trim())} onClick={save}>{busy?"Saving…":"Save provider"}</button></fieldset>
    {message&&<p role="status">{message}</p>}<button className="btn" onClick={onClose}>Close</button>
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
    </div>
  );
}

function TextLayers({scene,onChange,focusLayer}:{scene:Scene;onChange:(layers:NonNullable<Scene["font_json"]["layers"]>)=>void;focusLayer?:string|null}) {
  const [layers,setLayers]=useState(scene.font_json.layers||[]);
  const latest=useRef(layers);
  const change=(next:typeof layers)=>{latest.current=next;setLayers(next);onChange(next);};
  const patch=(id:string,values:object)=>change(latest.current.map(l=>l.id===id?{...l,...values}:l));
  useEffect(()=>{if(focusLayer){const card=[...document.querySelectorAll<HTMLElement>('[data-text-layer-id]')].find(el=>el.dataset.textLayerId===focusLayer);card?.scrollIntoView?.({block:'center'});card?.querySelector<HTMLTextAreaElement>('textarea')?.focus();}},[focusLayer]);
  const addLayer=(kind:'text'|'text_box'|'text_plus')=>change([...latest.current,{id:crypto.randomUUID(),kind,text:kind==='text_plus'?'Text+ title':kind==='text_box'?'Type your paragraph…':'Your title',x:50,y:25,size:64,color:'#FFFFFF',start_ms:0,end_ms:0,bold:kind!=='text',box_width:80,animation:kind==='text_plus'?'letters-pop':'none',animation_ms:800,exit_ms:0,spacing:0}]);
  return <section className="text-layers"><div className="section-heading"><h3>Text overlays</h3><span>{layers.length}/12</span><FeatureHelp compact title="Text, Text Box and Text+" description="Each title is its own timed overlay on the T1 timeline. Text is a quick title; Text Box wraps paragraph text; Text+ includes advanced styling and animation controls inspired by DaVinci Resolve Fusion." steps="Click a text block on T1 to select and edit it here. Change its wording, set its start/end time, and render the scene to review it."/></div><p className="hint">Titles and labels are separate from captions. Start/end control when each title appears; end 0 means scene end.</p>
    {layers.map((l,i)=><article className={`layer-card kind-${l.kind||'text_plus'}`} key={l.id} data-text-layer-id={l.id}><div className="section-heading"><strong>{l.kind==='text_box'?'Text Box':l.kind==='text_plus'?'Text+':'Text'} · Layer {i+1}</strong><button className="text-btn" onClick={()=>change(latest.current.filter(v=>v.id!==l.id))}>Remove</button></div>
    <textarea aria-label={`Layer ${i+1} text`} dir="auto" value={l.text} onChange={e=>patch(l.id,{text:e.target.value})}/>
    <label className="control-label">Text tool<select aria-label={`Layer ${i+1} text tool`} value={l.kind||'text_plus'} onChange={e=>patch(l.id,{kind:e.target.value})}><option value="text">Text · simple title</option><option value="text_box">Text Box · wrapped paragraph</option><option value="text_plus">Text+ · advanced</option></select></label>
    {l.kind==='text_box'&&<label className="control-label">Text box width · {l.box_width||80}%<input aria-label={`Layer ${i+1} text box width`} type="range" min={20} max={100} value={l.box_width||80} onChange={e=>patch(l.id,{box_width:+e.target.value})}/></label>}
    <div className="layer-fields">{[{key:"x",label:"X position",max:100,step:1},{key:"y",label:"Y position",max:100,step:1},{key:"size",label:"Font size",max:200,step:1},{key:"start_ms",label:"Start (ms)",max:3600000,step:100},{key:"end_ms",label:"End (ms)",max:3600000,step:100}].map(field=>{const min=field.key==="size"?12:0;const value=Number(l[field.key as keyof typeof l])||0;return <label className="control-label slider-field" key={field.key}>{field.label}<span className="slider-value">{value}</span><input type="range" min={min} max={field.max} step={field.step} value={value} onChange={e=>patch(l.id,{[field.key]:Number(e.target.value)})}/></label>})}
    <label className="control-label">Font<select value={l.family||'Noto Naskh Arabic'} onChange={e=>patch(l.id,{family:e.target.value})}>{['Noto Sans','Poppins','Bebas Neue','Anton','Pacifico','Noto Naskh Arabic','Noto Sans Arabic','Amiri','Tajawal','Lalezar'].map(v=><option key={v}>{v}</option>)}</select></label><label className="control-label">Alignment<select value={l.align||'center'} onChange={e=>patch(l.id,{align:e.target.value})}>{['left','center','right'].map(v=><option key={v}>{v}</option>)}</select></label>{(['outline_width','shadow','exit_ms'] as const).map(k=><label key={k} className="control-label">{k==='exit_ms'?'Exit fade (ms)':k==='shadow'?'Shadow':'Outline'}<input type="number" min={0} max={k==='exit_ms'?10000:10} value={l[k]||0} onChange={e=>patch(l.id,{[k]:Math.max(0,Math.min(k==='exit_ms'?10000:10,+e.target.value))})}/></label>)}<label className="control-label">Style<select aria-label={`Layer ${i+1} style`} value="" onChange={e=>{const st=TEXT_STYLES.find(x=>x.name===e.target.value);if(st)patch(l.id,st.values);}}><option value="">Apply a style…</option>{TEXT_STYLES.map(st=><option key={st.name} value={st.name}>{st.name}</option>)}</select></label><label className="control-label">Animation<select aria-label={`Layer ${i+1} animation`} value={l.animation||'none'} onChange={e=>patch(l.id,{animation:e.target.value})}>{ANIMATIONS.map(v=><option key={v} value={v}>{ANIMATION_LABELS[v]||v}</option>)}</select></label><label className="control-label">Letter spacing<input type="number" aria-label={`Layer ${i+1} letter spacing`} min={-5} max={40} step={1} value={l.spacing||0} onChange={e=>patch(l.id,{spacing:Math.max(-5,Math.min(40,+e.target.value||0))})}/></label>{['shine','neon'].includes(l.animation||'')&&<label className="control-label">{l.animation==='neon'?'Glow colour':'Shine colour'}<input type="color" aria-label={`Layer ${i+1} highlight colour`} value={l.highlight||'#FFD84D'} onChange={e=>patch(l.id,{highlight:e.target.value})}/></label>}<label className="control-label">Animation ms<input type="number" min={100} max={10000} defaultValue={l.animation_ms||800} onBlur={e=>patch(l.id,{animation_ms:Math.max(100,Math.min(10000,Number(e.target.value)||800))})}/></label><label className="control-label">Color<input type="color" value={l.color} onChange={e=>patch(l.id,{color:e.target.value})}/></label></div><label className="check-label"><input type="checkbox" checked={l.bold} onChange={e=>patch(l.id,{bold:e.target.checked})}/>Bold</label></article>)}
    <div className="text-add-actions"><button className="btn" disabled={layers.length>=12} onClick={()=>addLayer('text')}><Plus size={14}/> Add Text</button><button className="btn" disabled={layers.length>=12} onClick={()=>addLayer('text_box')}><Plus size={14}/> Add Text Box</button><button className="btn" disabled={layers.length>=12} onClick={()=>addLayer('text_plus')}><Plus size={14}/> Add Text+</button></div>
  </section>;
}

type InspectorTab = "Media" | "Motion" | "Effects" | "Overlays" | "Text" | "Audio" | "Clip Audio";
const INSPECTOR_GUIDE:Record<InspectorTab,{description:string;steps:string}>={
  Media:{description:'Import and arrange still images and video clips for the selected scene. The Media Pool keeps source files available across scenes.',steps:'Import or generate media, select a thumbnail to choose it, then drag it onto the timeline or use the scene controls. Choose Fill to cover the frame or Fit to preserve the whole image.'},
  Motion:{description:'Set framing and camera movement for the selected image or video. Still-image movement is rendered as a pan or zoom; video speed controls affect playback.',steps:'Choose the media thumbnail first. Set Fill framing if movement is disabled, choose a motion preset, adjust its timing or speed, then render the scene to review it.'},
  Effects:{description:'Apply a scene look, color treatment, and effects such as film damage, spotlight, blur, annotations, or split screen.',steps:'Search the look tiles and hover to preview. Click a look to apply it, then use the effect cards below for detailed settings. Render the scene to check the final result.'},
  Overlays:{description:'Place extra image, video, emoji, or sticker layers over the scene without replacing its main media.',steps:'Choose or add an overlay. Select its row or click it in the preview to move, resize, rotate, animate, reorder, or remove it.'},
  Text:{description:'Create timed title layers and edit on-screen captions. Text appears on the T1 timeline lane as selectable text clips.',steps:'Use Add Text for a simple title, Add Text Box for wrapped paragraph text, or Add Text+ for advanced styling and animation. Click a T1 text clip to select its editor, change its text and timing, then render the scene.'},
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
function PartRow({scene, project, index, total, active, refresh, onMove, onDelete, onOpenSettings, onSaveState, onRecord, removeNarration, txPreview}: {
  scene: Scene; project: Project; index: number; total: number; active: boolean; txPreview?: {key: string; from: string | null; to: string | null} | null;
  refresh: () => Promise<void>; onMove: (dir: -1 | 1) => void; onDelete: () => void;
  onOpenSettings: () => void; onSaveState: (id: string, state: string) => void; onRecord:(label:string,undo:()=>Promise<unknown>,redo:()=>Promise<unknown>)=>void; removeNarration:(scene:Scene)=>Promise<void>;
}) {
  const [tab, setTab] = useState<InspectorTab>("Media");
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
  const acceptedTake = scene.voice_takes.find(t => t.accepted);
  const [scriptOpen, setScriptOpen] = useState(() => {try {return localStorage.getItem("sceneforge.scriptOpen") === "1";} catch {return false;}});
  useEffect(() => {try {localStorage.setItem("sceneforge.scriptOpen", scriptOpen ? "1" : "0");} catch {/* storage unavailable */}}, [scriptOpen]);
  // Overlays are edited live (canvas drag + panel); the draft is saved with the scene.
  const [ovDraft, setOvDraft] = useState<Overlay[] | null>(null);
  const [ovSelected, setOvSelected] = useState(0);
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
      refresh().catch(e => setError(e.message));
      if (job.status === "succeeded") setPreviewMode("render");
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
        onSaveState(scene.id, !ok ? "Save failed" : writes.current || Object.keys(pending.current).length ? "Saving…" : "Saved");
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
    const ok = await run(() => api.updateScene(scene.id, patch));
    if (!ok) pending.current = {...patch, ...pending.current};
    return ok;
  }
  function draft(patch: Record<string, unknown>) {
    pending.current = {...pending.current, ...patch,
      ...((pending.current.font||patch.font)?{font:{...(pending.current.font as object||{}),...(patch.font as object||{})}}:{}),
      ...((pending.current.look||patch.look)?{look:{...(pending.current.look as object||{}),...(patch.look as object||{})}}:{})};
    setPreviewMode("source");
    onSaveState(scene.id, "Unsaved changes");
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => { void flush(); }, 500);
  }
  function changeCaptionSegments(next:CaptionSegment[]) {
    setCaptionSegments(next);
    const text=next.map(segment=>segment.text.trim()).filter(Boolean).join(' ');
    setCaptions(text);
    draft({subtitle_text:text,font:{caption_segments:next}});
  }
  async function update(patch: Record<string, unknown>) {
    setPreviewMode("source");
    if (await flush()) await run(() => api.updateScene(scene.id, patch));
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
  const presetFilter = previewFilter === "none" ? "" : previewFilter;
  const mediaFilter = [presetFilter, gradedSrc ? "" : adjustPreviewFilter(liveAdjust, wbFilterId), filmToneFilter(liveFilm)].filter(Boolean).join(' ') || undefined;
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
          <div className={`canvas-viewport ${mag > 1 ? 'magnified' : ''}`}
            onWheel={e => {if (!e.ctrlKey) return; e.preventDefault(); const r = e.currentTarget.getBoundingClientRect(); setMagAt(mag * (e.deltaY < 0 ? 1.15 : 0.87), (e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height);}}
            onPointerDown={e => {if (mag <= 1 || !(e.button === 1 || (e.button === 0 && spaceDown.current))) return; e.preventDefault();
              const sx = e.clientX, sy = e.clientY, p0 = pan, r = e.currentTarget.getBoundingClientRect();
              const move = (ev: PointerEvent) => setPan({x: p0.x + (ev.clientX - sx) / r.width * 100 / mag, y: p0.y + (ev.clientY - sy) / r.height * 100 / mag});
              const up = () => {window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up);};
              window.addEventListener('pointermove', move); window.addEventListener('pointerup', up);}}>
            <div className="preview-canvas" style={{transform: mag > 1 ? `scale(${mag}) translate(${pan.x}%, ${pan.y}%)` : undefined, transformOrigin: "center", aspectRatio: project.aspect.replace(":", "/"), width: `min(${zoom}%, calc((var(--stage-height) - 40px) * ${canvasRatio * zoom / 100}))`}}><WhiteBalanceFilter id={wbFilterId} adjust={liveAdjust}/>{previewMode !== "render" && shot && <PreviewFinish adjust={liveAdjust}/>}{previewMode !== "render" && shot && hoverFx && hoverFx !== scene.effect_preset && <div className="hover-preview-chip" role="status">Previewing <b>{selectedEffect.label}</b> · click to apply</div>}{previewMode !== "render" && shot && liveFilm && <FilmPreview film={liveFilm}/>}{previewMode !== "render" && shot && <SceneFxPreview look={{...(scene.look_json || {}), ...((pending.current.look as any) || {})}} shots={scene.shots} filter={mediaFilter} aspect={project.width / project.height}/>}{previewMode !== "render" && shot && tab === "Effects" && !routeEditing && liveAnnots.length > 0 && <AnnotationCanvas annots={liveAnnots} onChange={a => draft({look: {annotations: a}})}/>}{previewMode !== "render" && shot && routeEditing && liveRoute && <RouteCanvas route={liveRoute} onChange={r => draft({look: {route: r}})}/>}{previewMode !== "render" && shot && overlays.length > 0 && <OverlayCanvas overlays={overlays} frameAspect={project.width / project.height} selected={ovSelected} onSelect={i => {setOvSelected(i); setTab("Overlays");}} onChange={(i, patch, commit) => {const next = ovRef.current.map((x, k) => k === i ? {...x, ...patch} : x); ovRef.current = next; changeOverlays(next, !!commit);}} onCommit={() => draft({overlays: ovRef.current})}/>}
              {previewMode === "render" && rendered ? <video ref={videoRef} className="canvas-media" controls preload="metadata" src={api.assetStreamUrl(rendered)}/> :
                shot ? shot.asset?.type === "image" ? (shot.crop_json?<svg className="canvas-media" role="img" aria-label={`Cropped source for ${scene.title}`} viewBox={`${shot.crop_json.x*(shot.asset.width||1)} ${shot.crop_json.y*(shot.asset.height||1)} ${shot.crop_json.width*(shot.asset.width||1)} ${shot.crop_json.height*(shot.asset.height||1)}`} preserveAspectRatio={shot.fit==='cover'?'xMidYMid slice':'xMidYMid meet'} style={{filter:mediaFilter}}><image href={gradedSrc||api.assetStreamUrl(shot.asset_id)} width={shot.asset.width||1} height={shot.asset.height||1}/></svg>:<>{shot.fit === "contain_blur" && <img className="canvas-media canvas-blur-bg" aria-hidden="true" alt="" src={gradedSrc||api.assetStreamUrl(shot.asset_id)} style={{objectFit: "cover", filter: `${mediaFilter === "none" ? "" : mediaFilter} blur(14px) brightness(0.9)`}}/>}<img className="canvas-media" src={gradedSrc||api.assetStreamUrl(shot.asset_id)} alt={`Source media for ${scene.title}`} style={{objectFit: shot.fit === "cover" ? "cover" : "contain", filter:mediaFilter}}/></>) :
                  <>{shot.fit === "contain_blur" && <img className="canvas-media canvas-blur-bg" aria-hidden="true" alt="" src={gradedSrc||api.assetThumbUrl(shot.asset_id, 480)} style={{objectFit: "cover", filter: `${mediaFilter === "none" ? "" : mediaFilter} blur(14px) brightness(0.9)`}}/>}<video ref={videoRef} className="canvas-media canvas-fg" controls preload="metadata" poster={gradedSrc||undefined} src={api.assetStreamUrl(shot.asset_id)} style={{objectFit:shot.fit === "cover" ? "cover" : "contain",filter:mediaFilter}}/></> :
                  <div className="canvas-empty"><div className="empty-icon"><ImageIcon size={30}/></div><h3>Start with a visual</h3><p>Add an image or video to bring this scene to life.</p><button className="btn btn-primary" onClick={() => fileRef.current?.click()}><Plus size={15}/> Add media</button><button className="text-btn" onClick={() => setChatOpen(true)}><Sparkles size={14}/> Or generate an image</button></div>}
              {previewMode==="source"&&shot?.asset?.type==="image"&&scene.effect_preset==="glitch"&&strength>0&&<img aria-hidden="true" className="canvas-media glitch-slice glitch-full" src={api.assetStreamUrl(shot.asset_id)} alt="" style={{objectFit:shot.fit==="cover"?"cover":"contain",opacity:strength}}/>}
              {active&&txPreview&&<div className={`tx-live transition-sample sample-${txPreview.key} tx-on-canvas`} aria-hidden="true"><span>{txPreview.from?<img src={api.assetThumbUrl(txPreview.from,640)} alt=""/>:"A"}</span><span>{txPreview.to?<img src={api.assetThumbUrl(txPreview.to,640)} alt=""/>:"B"}</span><em className="tx-on-canvas-label">Previewing transition · click to apply</em></div>}{safeZones&&project.height>project.width*1.2&&<div className="safe-zones" aria-hidden="true"><span className="sz-top">Top bar</span><span className="sz-bottom">Caption & username · keep text above</span><span className="sz-right">Buttons</span></div>}{previewMode==="source"&&shot&&<CaptionPreview font={scene.font_json as any} text={captions} projectW={project.width} projectH={project.height}/>}{previewMode==="source"&&shot&&(scene.font_json.layers||[]).map(l=><div className={`canvas-text-layer kind-${l.kind||'text_plus'}`} key={l.id} dir="auto" style={{left:`${l.x}%`,top:`${l.y}%`,fontSize:`${l.size/project.width*100}cqw`,color:l.color,fontFamily:previewFontFamily(l.family||scene.font_json.family),fontWeight:l.bold?700:400,textAlign:(l.align||"center") as any,whiteSpace:'pre-wrap',overflowWrap:'anywhere',maxWidth:l.kind==='text_box'?`${l.box_width||80}%`:'95%',transform:`translate(${l.align==="left"?0:l.align==="right"?-100:-50}%,-50%)`,WebkitTextStroke:`${(l.outline_width||0)/project.width*100}cqw black`,textShadow:l.shadow?`${l.shadow/project.width*100}cqw ${l.shadow/project.width*100}cqw black`:"none"}}>{l.text}</div>)}
            </div>
          </div>
          <footer className="preview-footer">
            <span>{previewMode === "source" ? "Editing preview • Effects approximate; render for motion, captions & sound" : scene.is_stale ? "Previous render • Changes need a new render" : "Rendered scene"}</span>
            {project.height>project.width*1.2&&<label className="safe-toggle" title="Shade the areas TikTok, Reels and Shorts cover with their buttons and caption"><input type="checkbox" aria-label="Show safe zones" checked={safeZones} onChange={e=>setSafeZones(e.target.checked)}/> Safe zones</label>}<span className="inspect-zoom" role="group" aria-label="Preview zoom"><button className="icon-reset" aria-label="Zoom out of the preview" disabled={mag <= 1} onClick={() => setMagAt(mag * 0.8)}>−</button><button className="text-btn" aria-label="Fit preview" title="Fit (Ctrl + mouse wheel zooms, middle-drag or Space + drag pans)" onClick={() => {setMag(1); setPan({x: 0, y: 0});}}>{Math.round(mag * 100)}%</button><button className="icon-reset" aria-label="Zoom into the preview" disabled={mag >= 4} onClick={() => setMagAt(mag * 1.25)}>+</button></span><label className="zoom-control">View <select aria-label="Canvas view size" value={zoom} onChange={e => setZoom(Number(e.target.value))}><option value={100}>Fit</option><option value={75}>75%</option><option value={50}>50%</option></select></label>
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
      <aside className="inspector" aria-label="Scene inspector">
        <InspectorResizer/>
        <div className="inspector-heading"><span className="eyebrow">SCENE SETTINGS · {tab.toUpperCase()}</span><span className="subtle">{durationLabel(scene)}</span><FeatureHelp title={tab} description={INSPECTOR_GUIDE[tab].description} steps={INSPECTOR_GUIDE[tab].steps}/></div>
        <div className="inspector-tabs" role="tablist" aria-label="Scene tools">
          {INSPECTOR_TABS.filter(({name})=>name!=="Clip Audio"||shot?.asset?.type==="video").map(({name, Icon}) => <button key={name} role="tab" id={`${scene.id}-${name}-tab`} aria-controls={`${scene.id}-panel`} aria-selected={tab === name} onClick={() => setTab(name)} onKeyDown={e => {
            const offset = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
            if (offset) {e.preventDefault(); const next = INSPECTOR_TABS[(INSPECTOR_TABS.findIndex(t => t.name === name) + offset + INSPECTOR_TABS.length) % INSPECTOR_TABS.length].name; setTab(next); document.getElementById(`${scene.id}-${next}-tab`)?.focus();}
          }} tabIndex={tab === name ? 0 : -1}><Icon size={18}/><span>{name}</span></button>)}
        </div>
        <div className="inspector-body" role="tabpanel" id={`${scene.id}-panel`} aria-labelledby={`${scene.id}-${tab}-tab`}>
          {tab === "Media" && <>
            <div className="section-heading"><h3>Scene media</h3><span className="count-badge">{scene.shots.length}</span></div>
            <p className="hint">Images and clips play in the order shown.</p>
            <div className="media-grid">{scene.shots.map((s,i) => <div className={`media-item ${s.id === shot?.id ? "selected" : ""}`} key={s.id}>
              <button className="media-select" aria-label={`Select media ${i+1}`} aria-pressed={s.id === shot?.id} onClick={() => {setSelectedShotId(s.id); setPreviewMode("source");}}><Thumb assetId={s.asset_id} type={s.asset?.type}/><span>{String(i+1).padStart(2,"0")}</span></button>
              <button className="remove-media" aria-label={`Remove media ${i+1}`} disabled={false} onClick={() => run(() => api.deleteShot(s.id))}><X size={12}/></button>
            </div>)}</div>
            <button className="btn upload-btn" disabled={false} onClick={() => fileRef.current?.click()}><Upload size={16}/> Upload image or video</button>
            <button className="btn ai-btn" onClick={() => setChatOpen(true)}><Sparkles size={16}/> Generate image</button>{shot?.asset?.type==="image"&&<button className="btn" disabled={false} title="Make a cleaned-up copy: less noise, dust and scratches removed, better contrast, sharper and larger" onClick={()=>{setRestoreNote("Restoring… this can take a few seconds for large scans.");void run(async()=>{try{const restored=await api.restoreAsset(shot.asset_id);await api.addShot(scene.id,restored.id);await api.deleteShot(shot.id);setRestoreNote(`Done: “${restored.original_filename}” is now in this scene. The original is still in the Media Pool.`);window.dispatchEvent(new Event("sceneforge-media-changed"));}catch(e){setRestoreNote("");throw e;}});}}><Wand2 size={16}/> Restore old photo</button>}{restoreNote&&<p className="hint restore-note" role="status" aria-live="polite">{restoreNote}</p>}
            {shot && <label className="control-label">Frame fit<select aria-label="Frame fit" value={shot.fit} disabled={false} onChange={e => {const fit = e.currentTarget.value; setPreviewMode("source"); void run(() => api.updateShot(shot.id, {fit}));}}><option value="cover">Fill frame (crop)</option><option value="contain">Fit inside frame (show entire image)</option></select><span className="hint">Fit preserves the whole image with bars where needed. Fill crops the edges to cover the frame.</span></label>}
          </>}
          {tab === "Motion" && <>{shot&&<FramingControls key={shot.id} shot={shot} save={run}/>}<h3>Camera movement</h3><p className="hint">Applied to {shot ? `media ${scene.shots.indexOf(shot)+1}` : "selected media"}. {shot?.fit !== "cover" ? "Motion requires Fill frame; Fit inside frame keeps the entire image still." : "Render to preview the movement."}</p><div className="motion-box">{MOTIONS.map(({key,label,Icon}) => <button key={key} className={`motion-btn ${activeMotion === key ? "selected" : ""}`} aria-pressed={activeMotion === key} disabled={!shot || shot.fit !== "cover"} onClick={() => run(() => api.updateShot(shot.id,{motion:{type:key,easing:(shot.motion_json as any)?.easing||"ease_in_out"}}))}><Icon size={19}/><span>{label}</span></button>)}</div>{shot&&shot.asset?.type==="video"&&<SpeedControls key={"sp"+shot.id} shot={shot} disabled={false} save={speed=>run(()=>api.updateShot(shot.id,{speed}))}/ >}{shot&&<label className="control-label">Speed curve<select aria-label="Motion speed curve" value={(shot.motion_json as any)?.easing||"ease_in_out"} disabled={shot.fit!=="cover"} onChange={e=>{const easing=e.target.value; /* read now: the controlled select resets before the queued save runs */ void run(()=>api.updateShot(shot.id,{motion:{...(shot.motion_json||{type:"static"}),easing}}));}}><option value="ease_in_out">Smooth (ease in and out)</option><option value="ease_in">Ease in (starts slow)</option><option value="ease_out">Ease out (ends slow)</option><option value="linear">Constant speed</option></select></label>}</>}
          {tab === "Effects" && <><h3>Image looks</h3><p className="hint">Choose a look for the whole scene.</p><label className="search-control"><Search size={15}/><input aria-label="Search effects" placeholder="Search effects…" value={search} onChange={e => setSearch(e.target.value)}/></label><p className="hint looks-hint">Hover a look to preview it on the picture · click to apply</p><div className="effects-grid">{EFFECTS.filter(f => f.label.toLowerCase().includes(search.toLowerCase())).map(fx => <button key={fx.key} className={`effect-tile ${scene.effect_preset === fx.key ? "selected" : ""}`} aria-pressed={scene.effect_preset === fx.key} disabled={false} onMouseEnter={() => {setPreviewMode("source"); setHoverFx(fx.key);}} onMouseLeave={() => setHoverFx(null)} onFocus={() => setHoverFx(fx.key)} onBlur={() => setHoverFx(null)} onClick={() => {setHoverFx(null);setPreviewMode("source"); void update({effect_preset:fx.key});}}>
            <div className="effect-image">{shot?.asset && shot.asset.type !== "audio" ? <img src={api.assetThumbUrl(shot.asset_id)} alt="" style={{filter:fx.swatch}}/> : <div className="effect-swatch" style={{filter:fx.swatch}}/>}{scene.effect_preset === fx.key && <CheckCircle2 size={17}/>}</div><span>{fx.label}</span></button>)}</div>{!EFFECTS.some(f => f.label.toLowerCase().includes(search.toLowerCase())) && <p className="hint">No matching effects.</p>}<p className="hint">Thumbnails are approximate. Glitch tears the whole frame in bursts; choose its speed and block size below. Render to check the exact result.</p><button className="btn" disabled={!shot||isGenerating} onClick={render}><Play size={14}/> Render effect preview</button><label className="control-label">Effect strength · {scene.effect_intensity}%<input aria-label="Effect strength" type="range" min={0} max={100} step={5} disabled={scene.effect_preset==="original"} key={scene.effect_intensity} defaultValue={scene.effect_intensity} onChange={e=>draft({effect_intensity:Number(e.target.value)})} onBlur={()=>void flush()}/></label><button className="text-btn" disabled={scene.effect_preset === "original"} onClick={() => {setPreviewMode("source"); void update({effect_preset:"original"});}}>Reset to original</button><LookPanel scene={scene} disabled={false} onDraft={look=>draft({look})} onSaveNow={async look=>{setPreviewMode("source");
  // Save pending edits first, but do not let an earlier failed save block this independent LUT change.
  await flush();await run(async()=>{const saved:any=await api.updateScene(scene.id,{look});
  // An old backend ignores "look" without an error; say so instead of silently doing nothing.
  if(look.lut&&saved?.look_json?.lut?.asset_id!==look.lut.asset_id)throw new Error("The LUT was not saved because this SceneForge backend is out of date. Close every SceneForge and start.bat window, run setup.bat in the newest folder, then start it again.");});}}/><SceneEffectsPanel scene={scene} disabled={false} onDraft={look=>draft({look})} liveRoute={liveRoute} routeEditing={routeEditing} onRouteEditing={setRouteEditing} liveAnnotations={liveAnnots} vertical={project.height>project.width*1.2} onAddMedia={() => fileRef.current?.click()}/></>}
          {tab === "Text" && <><AutoCaptions scene={scene} onDone={sc => {setCaptions(sc.subtitle_text);setCaptionSegments(sc.font_json.caption_segments||[]);void refresh();}} onStyle={f => update({font: f})}/><div className="text-quick"><span className="hint">Add a title as a timed clip on the T1 text lane.</span><button className="btn" disabled={draftLayers.length >= 12} onClick={() => {const next=[...draftLayers,{id:crypto.randomUUID(),kind:'text' as const,text:'Your title',x:50,y:22,size:64,color:'#FFFFFF',bold:false,start_ms:0,end_ms:0,family:'Noto Sans',align:'center'}];setDraftLayers(next);draft({font:{layers:next}});}}>Add Text</button><button className="btn" disabled={draftLayers.length >= 12} onClick={() => {const next=[...draftLayers,{id:crypto.randomUUID(),kind:'text_box' as const,text:'Type your paragraph…',x:50,y:50,size:48,color:'#FFFFFF',bold:false,start_ms:0,end_ms:0,family:'Noto Sans',align:'center',box_width:80}];setDraftLayers(next);draft({font:{layers:next}});}}>Add Text Box</button><button className="btn btn-primary" disabled={draftLayers.length >= 12} onClick={() => {const next=[...draftLayers,{id:crypto.randomUUID(),kind:'text_plus' as const,text:'Text+ title',x:50,y:22,size:72,color:'#FFE14D',bold:true,start_ms:0,end_ms:0,family:'Noto Sans',align:'center',outline_width:4,shadow:0,animation:'letters-pop',animation_ms:900,exit_ms:400,spacing:0}];setDraftLayers(next);draft({font:{layers:next}});}}>Add Text+</button></div>{captionSegments.length>0?<><CaptionSegmentsEditor segments={captionSegments} onChange={changeCaptionSegments} direction={(scene.font_json.caption_direction||'auto') as CaptionDirection} onDirectionChange={direction=>void update({font:{caption_direction:direction}})} activeSegmentId={textFocus?.startsWith('caption:')?textFocus.slice(8):null} onFocusSegment={id=>setTextFocus(`caption:${id}`)}/><button className="text-btn" onClick={()=>{setCaptionSegments([]);setCaptions(text);draft({subtitle_text:text,font:{caption_segments:[]}});}}><Copy size={13}/> Copy narration to captions</button></>:<><div className="caption-manual-heading"><h3>On-screen captions</h3><label className="caption-direction-control">Direction<select aria-label="Caption text direction" value={scene.font_json.caption_direction||'auto'} onChange={e=>void update({font:{caption_direction:e.target.value}})}><option value="auto">Auto</option><option value="rtl">Right to left</option><option value="ltr">Left to right</option></select></label></div><p className="hint">Caption text is independent of narration. Add a caption here or generate timed clips above.</p><textarea aria-label="On-screen captions" dir={(scene.font_json.caption_direction||'auto') as CaptionDirection} className="caption-box" value={captions} onChange={e => {setCaptions(e.target.value); draft({subtitle_text:e.target.value,font:{caption_segments:[]}});}} onBlur={() => void flush()} placeholder="Write the text to appear on your video…"/><button className="text-btn" onClick={() => {setCaptions(text); draft({subtitle_text:text,font:{caption_segments:[]}});}}><Copy size={13}/> Copy narration to captions</button></>}<fieldset><CaptionStylePanel scene={scene} onChange={f => {if(f.typewriter&&!captions.trim()&&text.trim()){setCaptions(text);draft({subtitle_text:text});}void update({font:f});}}/><TextLayers key={`tl-${draftLayers.length}`} scene={{...scene,font_json:{...scene.font_json,layers:draftLayers}}} onChange={layers=>{setDraftLayers(layers);draft({font:{layers}});}} focusLayer={textFocus}/></fieldset><button className="btn btn-primary" disabled={!shot||isGenerating} onClick={render}>Render text preview</button><p className="hint">Caption typewriter applies to On-screen captions. For a title, choose typewriter under its Text overlay Animation. Render text preview to see the result.</p><section className="typewriter-controls"><h3>Typewriter timing & sound</h3>
            <p className="hint">Enable Captions and Typewriter reveal above. Sound follows each reveal, not the original recording’s rhythm.</p>
            <label className="check-label"><input type="checkbox" checked={!!scene.font_json.typewriter_sound} disabled={false} onChange={e=>update({font:{typewriter_sound:e.target.checked}})}/> Synchronized keystrokes</label>
            <div className="button-row">{[{label:"Slow",ms:220},{label:"Natural",ms:160},{label:"Fast",ms:80}].map(p=><button className="btn" disabled={false} key={p.label} onClick={()=>update({font:{typewriter_duration_ms:Math.min(120000,Math.max(100,(Array.from(captions).length-1)*p.ms))}})}>{p.label}</button>)}</div><button className="text-btn" disabled={false} onClick={()=>update({timing_mode:"fixed",requested_duration_ms:Math.max(scene.requested_duration_ms||4000,(scene.font_json.typewriter_delay_ms||0)+(scene.font_json.typewriter_duration_ms||Math.max(200,(Array.from(captions).length-1)*160))+1000)})}>Extend scene to fit typing + 1s hold</button>
            <div className="timing-inputs"><label className="control-label">Start delay (seconds)<input aria-label="Typing start delay" type="number" min={0} max={120} step={.1} key={scene.font_json.typewriter_delay_ms} defaultValue={(scene.font_json.typewriter_delay_ms||0)/1000} onBlur={e=>{const v=Math.min(120,Math.max(0,Number(e.target.value)||0))*1000;if(v!==(scene.font_json.typewriter_delay_ms||0))void update({font:{typewriter_delay_ms:v}});}}/></label>
            <label className="control-label">Reveal time (seconds)<input aria-label="Typing reveal time" type="number" min={.1} max={120} step={.1} key={scene.font_json.typewriter_duration_ms} defaultValue={scene.font_json.typewriter_duration_ms ? scene.font_json.typewriter_duration_ms/1000 : ''} placeholder="Auto" onBlur={e=>{if(e.target.value){const v=Math.min(120,Math.max(.1,Number(e.target.value)||3))*1000;void update({font:{typewriter_duration_ms:v}});}}}/></label></div>
            <p className="hint">Short scenes compress the reveal and make typing faster. Choose Slow, then Extend scene to preserve the slower speed. This switches duration to Fixed; narration may be trimmed to that duration.</p>
            <label className="control-label">Keystroke volume (%)<input aria-label="Keystroke volume" type="number" min={0} max={100} key={scene.font_json.typewriter_volume} defaultValue={scene.font_json.typewriter_volume??50} onBlur={e=>{const v=Math.min(100,Math.max(0,Number(e.target.value)||0));if(v!==(scene.font_json.typewriter_volume??50))void update({font:{typewriter_volume:v}});}}/></label>
            <p className="hint">{scene.font_json.typewriter_sound_asset_id ? 'Sound: uploaded recording (a short keystroke is extracted).' : 'Sound: included keystroke.'}</p>
            <button className="btn upload-btn" disabled={false} onClick={()=>soundRef.current?.click()}><Upload size={14}/> Upload typewriter sound</button>
            {scene.font_json.typewriter_sound_asset_id && <button className="text-btn" disabled={false} onClick={()=>update({font:{typewriter_sound_asset_id:null}})}>Use included keystroke</button>}
            <p className="hint">If this recording was previously uploaded as narration, choose Audio → Use no narration to avoid hearing it twice.</p>
          </section><p className="hint">Render the scene to preview captions and synchronized sound together.</p></>}
          {tab === "Clip Audio" && shot?.asset?.type === "video" && <><ClipSoundControls key={"cs"+shot.id} shot={shot} save={audio=>{const before=shot.audio_json||{volume:100,mute:false,duck:true};void onRecord("clip sound",()=>api.updateShot(shot.id,{audio:before}),()=>api.updateShot(shot.id,{audio}));}}/><p className="hint">These controls affect the selected video's embedded audio track. Narration and music remain under Audio.</p></>}
          {tab === "Overlays" && <OverlayPanel scene={scene} overlays={overlays} selected={ovSelected} onSelect={setOvSelected} onChange={changeOverlays} disabled={false}/>}{tab === "Audio" && <>{acceptedTake?.audio_asset && <AudioClipEditor key={acceptedTake.id} scene={scene} take={acceptedTake} disabled={false} onChanged={refresh} onRemove={()=>void removeNarration(scene)}/>}<FinishingPanel project={project} disabled={false} onChanged={refresh}/><h3>Voice & narration</h3><p className="hint">Connect a local speech component or upload a recording. Select a take before rendering.</p><VoicePanel scene={{...scene,spoken_text:text}} onChanged={refresh} beforeGenerate={flush}/></>}
          <section className="timing-section"><h3><Clock size={15}/> Scene duration</h3><label className="control-label">Timing mode<select aria-label="Timing mode" value={scene.timing_mode} disabled={false} onChange={e => update({timing_mode:e.target.value})}><option value="audio_driven">Match narration</option><option value="fixed">Fixed duration</option></select></label>
          {scene.timing_mode === "fixed" && <label className="control-label">Seconds<input aria-label="Scene duration in seconds" type="number" min={1} max={120} step={0.5} defaultValue={(scene.requested_duration_ms || 5000)/1000} key={scene.requested_duration_ms} onBlur={e => {const v=Math.max(1,Math.min(120,Number(e.target.value)||5)); if (v*1000 !== scene.requested_duration_ms) void update({requested_duration_ms:Math.round(v*1000)});}}/></label>}
          <p className="hint">{scene.timing_mode === "fixed" ? "Narration is trimmed or padded to fit this length." : "Uses the selected narration take, including lead and trail padding."}</p></section>
        </div>
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
export default function App() {
  const [editorEpoch,setEditorEpoch]=useState(0);
  const [project, setProject] = useState<Project | null>(null);
  const projectRef = useRef<Project | null>(null);
  const refreshVersion = useRef(0);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectSearch,setProjectSearch]=useState("");
  const [selectedId, setSelectedId] = useState("");
  const [newTitle, setNewTitle] = useState("Untitled documentary");
  const [newAspect, setNewAspect] = useState("16:9");
  const [titleDraft, setTitleDraft] = useState("");
  const [exportPanel,setExportPanel]=useState(true);
  const [exportExpanded,setExportExpanded]=useState(false);
  const [mediaVersion,setMediaVersion]=useState(0);
  useEffect(()=>{const bump=()=>setMediaVersion(v=>v+1);window.addEventListener('sceneforge-media-changed',bump);return()=>window.removeEventListener('sceneforge-media-changed',bump);},[]);
  const [importStatus,setImportStatus]=useState('');
  const [menu,setMenu]=useState('');
  const importRef=useRef<HTMLInputElement>(null),audioImportRef=useRef<HTMLInputElement>(null),folderRef=useRef<HTMLInputElement>(null);
  const [history,setHistory]=useState<{undo:()=>Promise<unknown>;redo:()=>Promise<unknown>;label:string}[]>([]);
  const [future,setFuture]=useState<typeof history>([]);
  async function record(label:string,undo:()=>Promise<unknown>,redo:()=>Promise<unknown>){
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
  const [infoPanel, setInfoPanel] = useState<{panel:string;section?:string}|null>(null);
  useEffect(()=>{const open=(e:Event)=>setInfoPanel((e as CustomEvent).detail||null);window.addEventListener('sceneforge-open-panel',open);return()=>window.removeEventListener('sceneforge-open-panel',open);},[]);
  useEffect(()=>{const open=()=>setSettingsOpen(true);window.addEventListener('sceneforge-open-settings',open);return()=>window.removeEventListener('sceneforge-open-settings',open);},[]);
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
  const closeRef=useRef<()=>Promise<boolean>>(async()=>false);
  closeRef.current=async()=>{
    if(busy||exporting)return false;
    if(!(await saveBeforeClose()))return false;
    if(!(await saveTitle())||hasActiveWrites())return false;
    return (await api.closeStatus()).ready;
  };
  useEffect(()=>{
    const target=window as Window & {__sceneForgePrepareClose?:()=>Promise<boolean>};
    target.__sceneForgePrepareClose=()=>closeRef.current();
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
    await action(async () => {const p=await api.createProject(newTitle.trim()||"Untitled documentary",newAspect); await openProject(p.id); setProjects(await api.listProjects());});
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
    <div className="brand"><span className="brand-mark"><Film size={22}/></span> SceneForge <span className="version-chip">STUDIO</span></div>
    <section className="home-intro"><span className="eyebrow">YOUR STORY, FRAME BY FRAME</span><h1>Make room for<br/>your next story.</h1><p>Turn scripts, images, and narration into a video.<br/>One scene at a time.</p></section>
    {error && <div role="alert" className="error-box">{error}</div>}
    <section className="new-project"><div><h2>Create a project</h2><p className="hint">Start with three scenes. Add more as your story grows.</p></div><div className="create-form"><label className="control-label">Project name<input autoFocus={projectMode==='new'} aria-label="New project name" value={newTitle} onChange={e=>setNewTitle(e.target.value)}/></label><label className="control-label">Format<select aria-label="New project aspect ratio" value={newAspect} onChange={e=>setNewAspect(e.target.value)}>{ASPECTS.map(a=><option key={a}>{a}</option>)}</select></label><button className="btn btn-primary" disabled={busy} onClick={createProject}><Plus size={16}/> Create project</button></div></section>
    <div className="section-heading"><h2>Your projects</h2><span className="subtle">{projects.length} projects</span></div>
    <label className="search-control"><Search size={16}/><input aria-label="Search projects" placeholder="Find a project…" value={projectSearch} onChange={e=>setProjectSearch(e.target.value)}/></label>
    {loading ? <p role="status">Loading projects…</p> : <div className="project-grid">{projects.filter(p=>p.title.toLowerCase().includes(projectSearch.toLowerCase())).map(p=><article className="project-tile" key={p.id}><button className="project-open-button" disabled={busy} onClick={()=>openProject(p.id)}><div className="project-cover"><Film size={30}/><span>{p.aspect}</span></div><strong>{p.title}</strong><span className="project-open">Open project <ArrowRight size={15}/></span></button><button className="text-btn project-delete" aria-label={`Delete project ${p.title}`} disabled={busy} onClick={()=>removeProject(p)}><Trash2 size={14}/> Delete</button></article>)}{!projects.filter(p=>p.title.toLowerCase().includes(projectSearch.toLowerCase())).length&&<p className="hint">{projects.length?"No matching projects.":"Your saved projects will appear here."}</p>}</div>}
  </main>;
  return <div className="studio-shell"><BuildNotice/>
    <header className="studio-toolbar">
      <button className="brand brand-button" title="Back to projects" disabled={dirty||busy||exporting} onClick={()=>action(async()=>{setProjects(await api.listProjects()); projectRef.current=null; setProject(null);})}><span className="brand-mark"><Film size={19}/></span><span>SceneForge</span></button>
      <span className="toolbar-divider"/>
      <div className="project-identity"><input aria-label="Project name" value={titleDraft} onChange={e=>{setTitleDraft(e.target.value); setStates(prev=>({...prev,title:"Unsaved changes"}));}} onBlur={()=>void saveTitle()}/><span role="status" className={`save-status ${failed ? "save-error" : ""}`}>{busy ? "Saving…" : status}</span></div>
      <div className="toolbar-end"><select aria-label="Project aspect ratio" value={project.aspect} disabled={busy||exporting} onChange={e=>action(async()=>{await api.updateProject(project.id,{aspect:e.target.value}); await refresh();})}>{ASPECTS.map(a=><option key={a}>{a}</option>)}</select><button className="icon-btn" title="Provider settings" aria-label="Provider settings" onClick={()=>setSettingsOpen(true)}><Settings size={18}/></button><button className="btn video-gen-launch" disabled={busy||exporting} onClick={()=>setVideoGenOpen(true)}><Clapperboard size={15}/>Generate video</button><button className="btn btn-primary" disabled={exporting||dirty||busy||!project.scenes.length} onClick={()=>setExportOpen(true)}><Upload size={15}/>{exporting ? `Exporting ${Math.round(exportJob?.progress||0)}%` : "Export video"}</button></div>
    </header>
    {titleCard&&<TitleDesigner width={project.width} height={project.height} busy={busy} onClose={()=>setTitleCard(false)} onCreate={d=>void addTitleCard(d)}/>}
    {project&&multi.length>1&&selected&&<BatchBar source={selected} scenes={project.scenes.filter(x=>multi.includes(x.id))} onClear={()=>setMulti([])} onDone={()=>void refresh()}/>}
    {exportOpen&&project&&<ExportDialog project={project} onClose={()=>setExportOpen(false)} onExport={settings=>{setExportOpen(false);void renderFullVideo(settings);}}/>}
    {videoGenOpen&&project&&<VideoGenerationPanel project={project} selectedSceneId={selected?.id||null} onClose={()=>setVideoGenOpen(false)} onOpenSettings={()=>setSettingsOpen(true)} onAdd={addGeneratedVideoToTimeline} onCaptions={captionGeneratedScene}/>}
    {exporting&&exportJob&&<ProgressCard floating title="Exporting video" stage={exportJob.stage} progress={exportJob.progress||0} status={exportJob.status} onCancel={()=>void api.cancelJob(exportJob.id).catch(()=>{})}/>}
    {(error||exportJob?.status==="failed")&&<div role="alert" className="error-box"><details><summary>Operation failed — show details</summary><pre>{error||exportJob?.error}</pre></details><button className="text-btn" onClick={()=>{setError(null);if(exportJob?.status==='failed')setExportJobId(null);}}>Dismiss</button></div>}
    <div className="editor-menubar">
      {['File','AI Engines','Edit','View','Help'].map(name=><div className="editor-menu" key={name}><button aria-expanded={menu===name} onClick={()=>{if(name==='AI Engines'){setInfoPanel({panel:'ai'});setMenu('');}else setMenu(menu===name?'':name);}}>{name}</button>{menu===name&&<div className="editor-menu-items">
       {name==='File'&&<><button disabled={busy||exporting} onClick={()=>{setMenu('');void goToProjects('new');}}>New project… <kbd>Ctrl+N</kbd></button><button disabled={busy||exporting} onClick={()=>{setMenu('');void goToProjects('open');}}>Open project… <kbd>Ctrl+O</kbd></button><button disabled={busy||exporting} onClick={()=>{setMenu('');void addPart();}}>New scene</button><button disabled={busy||exporting} onClick={()=>{setMenu('');setVideoGenOpen(true);}}>Generate video from text…</button><button disabled={busy||exporting} onClick={()=>importRef.current?.click()}>Import files to Media Pool…</button><button disabled={busy||exporting} onClick={()=>folderRef.current?.click()}>Import folder to Media Pool…</button><button disabled={!selected||busy||exporting} onClick={()=>audioImportRef.current?.click()}>Import audio to selected scene…</button><button onClick={()=>{setMenu('');setSettingsOpen(true);}}>Provider settings…</button></>}
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
        {project.scenes.map((scene,i)=><PartRow key={`${scene.id}-${editorEpoch}`} scene={scene} project={project} index={i} total={project.scenes.length} active={selected?.id===scene.id} txPreview={hoverTx&&selected&&project.scenes.indexOf(selected)>0?{key:hoverTx,from:project.scenes[project.scenes.indexOf(selected)-1]?.shots[0]?.asset_id||null,to:selected.shots[0]?.asset_id||null}:null} refresh={refresh} onMove={dir=>moveScene(scene.id,dir)} onDelete={()=>deleteScene(scene.id)} onOpenSettings={()=>setSettingsOpen(true)} onSaveState={(id,state)=>setStates(prev=>({...prev,[id]:state}))} onRecord={record} removeNarration={removeNarration}/>)}
        {!project.scenes.length&&<div className="empty-project"><Film size={40}/><h2>Your story starts here</h2><button className="btn btn-primary" disabled={busy} onClick={addPart}><Plus size={16}/> Add your first scene</button></div>}
        <div id="sequence-viewer"/>
      </main>
    </div>
    <ProjectTimeline notice={importStatus} onDropFiles={(id,files,insert)=>void dropFilesOnTimeline(id,files,insert)} onDropAssets={(id,assets,insert)=>void dropAssetsOnTimeline(id,assets,insert)} onDuration={resizeDuration} onTrimShot={(sceneId,shotId,sourceIn,sourceOut)=>{const shot=project.scenes.find(s=>s.id===sceneId)?.shots.find(x=>x.id===shotId);if(shot){const before={source_in_ms:shot.source_in_ms,source_out_ms:shot.source_out_ms};void record("trim video clip",()=>api.updateShot(shotId,before),()=>api.updateShot(shotId,{source_in_ms:sourceIn,source_out_ms:sourceOut}));}}} onRender={()=>void renderFullVideo()} exportScenes={exportScenes} exportAsset={exportJob?.status==="succeeded"?exportJob.artifact_asset_id:null} project={project} selectedId={selected?.id||""} disabled={busy||exporting} onSelect={setSelectedId} onAdd={addPart} multi={multi} onMulti={(id,mode)=>{if(!project)return;setMulti(m=>{if(mode==='clear')return [];const base=m.length?m:(selected?[selected.id]:[]);if(mode==='toggle')return base.includes(id)?base.filter(x=>x!==id):[...base,id];const ids=project.scenes.map(x=>x.id),a=ids.indexOf(selected?.id||id),b=ids.indexOf(id);return ids.slice(Math.min(a,b),Math.max(a,b)+1);});}} clipboard={clip} onClipboard={c=>{setClip(c);setImportStatus(c.kind==='scene'?`Copied scene “${c.label}”. Select a scene and press Ctrl+V (or right-click → Paste) to paste it after that scene.`:`Copied ${c.label}. Select another scene's narration and press Ctrl+V to paste.`);}} onDuplicate={id=>void duplicateScene(id)} onPaste={id=>void pasteClip(id)} onReorder={ids=>record('scene order',()=>api.reorderScenes(project.id,project.scenes.map(s=>s.id)),()=>api.reorderScenes(project.id,ids))} onUpdate={(id,patch)=>record('transition',()=>api.updateScene(id,{transition_in:project.scenes.find(s=>s.id===id)!.transition_in_json}),()=>api.updateScene(id,patch))} onDelete={()=>selected&&void deleteScene(selected.id)} onAudio={()=>audioImportRef.current?.click()} onRemoveAudio={()=>selected&&void removeNarration(selected)} onRemoveSceneAudio={id=>{const s=project.scenes.find(x=>x.id===id);if(s)void removeNarration(s);}} onUndo={undoTimeline} onRedo={redoTimeline} canUndo={!!history.length} canRedo={!!future.length} onSplit={(at,baked)=>{if(!selected)return;const snapshot=selected;let rightId="";void record("split scene",async()=>{if(rightId)await api.deleteScene(rightId);await api.restoreScene(snapshot.id,snapshot);setEditorEpoch(v=>v+1);setSelectedId(snapshot.id);},async()=>{const right=await api.splitScene(snapshot.id,at,baked);rightId=right.id;setEditorEpoch(v=>v+1);setSelectedId(right.id);});}}/>
    {settingsOpen&&<SettingsPanel priority={videoGenOpen} onClose={()=>setSettingsOpen(false)}/>}

    {infoPanel?.panel==='ai'&&<AIEnginesPanel section={infoPanel.section} onClose={()=>setInfoPanel(null)} onOpenSettings={()=>{setInfoPanel(null);setSettingsOpen(true);}}/>}
    {infoPanel?.panel==='about'&&<AboutPanel onClose={()=>setInfoPanel(null)}/>}
    {shareOpen&&exportJob?.status==='succeeded'&&exportJob.artifact_asset_id&&<ShareDialog assetId={exportJob.artifact_asset_id} fileName={`${project.title||'SceneForge'}-export.mp4`} onClose={()=>setShareOpen(false)} onReveal={(window as any).sceneforgeDesktop?.revealExport?id=>(window as any).sceneforgeDesktop.revealExport(id):undefined}/>}
  </div>;
}
