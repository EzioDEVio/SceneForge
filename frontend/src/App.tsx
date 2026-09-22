import {TitleDesigner,TitleDesign,ANIMATIONS} from './TitleDesigner';
import React, { useEffect, useRef, useState } from "react";
import {
  ZoomIn, ZoomOut, Crosshair, MoreHorizontal,
  ArrowLeft, ArrowRight, ArrowUp, ArrowDown,
  Download, Play, Loader2, Trash2, X, Plus, Upload, Sparkles, Volume2,
  FileText, ImageIcon, Clock, Palette, Type, Wand2, Film, Settings, Key, Check,
  ChevronRight, Layers, Copy, PanelLeftClose, PanelLeftOpen, Search, CheckCircle2,
} from "lucide-react";
import { api, subscribeJob, Project, Scene, Shot, Job, VoiceTake, ProviderProfile, Asset } from "./api";

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
  { key: "old_film", label: "Old film", swatch: "sepia(0.5) contrast(1.1) brightness(0.85) saturate(0.7)" },
];

// Arabic-shaping-correct fonts (bundled, always render identically to
// preview): Noto Naskh/Sans Arabic. The rest are common Windows system
// fonts — they render fine for Latin text, but are NOT guaranteed to
// shape Arabic script correctly (no bundled guarantee), so Arabic
// projects should stick to the Noto options.
const FONT_FAMILIES = [
  "Noto Naskh Arabic",
  "Noto Sans Arabic",
  "Arial",
  "Calibri",
  "Segoe UI",
  "Tahoma",
  "Times New Roman",
  "Georgia",
  "Verdana",
  "Trebuchet MS",
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
  const [sd,setSd]=useState({family:'sd15',steps:30,cfg_scale:7,seed:-1,negative_prompt:'blurry, low quality, distorted, watermark, text',hires:false});
  const [history,setHistory] = useState<{id:string;prompt:string;provider:string}[]>([]);
  useEffect(()=>{api.imageHistory(scene.id).then(setHistory).catch(()=>{});},[scene.id]);
  const [generated, setGenerated] = useState<{ id: string } | null>(null);

  useEffect(() => {
    api.listProviders().then(setProviders).catch(() => setProviders([]));
  }, []);

  const imageProvider = providers?.find((p) => p.capability === "image" && (!providerId || p.id===providerId));
  const configured = !!imageProvider;
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
    setGenerated(null);
    try {
      const asset = await api.generateImage(scene.id, prompt, size, imageProvider?.id, imageProvider?.name==='local_sd'?sd:undefined);
      setGenerated({ id: asset.id });
      setHistory(await api.imageHistory(scene.id));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function useImage() {
    if (!generated) return;
    setBusy(true);setError(null);
    try {await api.addShot(scene.id, generated.id);onImageAttached();onClose();}
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
        {imageProvider?.name==='local_sd'&&<fieldset className="provider-form"><legend>Local image quality</legend><div className="engine-actions"><button className="btn" disabled={startingEngine} onClick={()=>void engineAction('start')}>Start / retry engine</button><button className="btn" onClick={()=>void engineAction('log')}>View startup log</button></div>{engineLog!==null&&<div><button className="text-btn" onClick={()=>setEngineLog(null)}>Close log</button><pre className="engine-log">{engineLog}</pre></div>}<button type="button" onClick={()=>void checkEngine()}>Check engine</button><p role="status" className="hint">{engineStatus}</p>
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
          placeholder="e.g. Bell Labs, 1947, black-and-white archival photo style, wide shot of a workbench..."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <button className="btn btn-primary" onClick={generate} disabled={!configured || busy || !prompt.trim()}>
            {busy ? <><Loader2 size={14} className="spin" /> Generating…</> : <><Wand2 size={14} /> Generate image</>}
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

        {generated && (
          <div style={{ marginTop: 14 }}>
            <img src={api.assetStreamUrl(generated.id)} alt="" style={{ width: "100%", borderRadius: 8 }} />
            <button className="btn btn-primary" style={{ marginTop: 8 }} disabled={busy} onClick={useImage}>
              <Check size={14} /> Use this image
            </button>
          </div>
        )}

        {!!history.length&&<section><h4>Recent generations</h4><div className="generation-history">{history.map(h=><button key={h.id} title={h.prompt} onClick={()=>{setGenerated({id:h.id});setPrompt(h.prompt);}}><img src={api.assetStreamUrl(h.id)} alt={h.prompt}/><span>{h.provider}</span></button>)}</div></section>}
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
  local_sd:"Runs on your computer. Install AUTOMATIC1111 and an image checkpoint, then start it with --api. No API key or Docker required. GPU memory limits apply; model downloads are separate. Use current to keep the loaded model.",
};
const PROVIDER_OPTIONS = [
  {name:"cloudflare", label:"Cloudflare · Free allowance", capability:"image", model:"@cf/black-forest-labs/flux-1-schnell", url:""},
  {name:"huggingface", label:"Hugging Face · Limited credits", capability:"image", model:"black-forest-labs/FLUX.1-schnell", url:""},
  {name:"local_sd", label:"Local · Stable Diffusion", capability:"image", model:"current", url:"http://127.0.0.1:7860"},
  {name:"openai", label:"OpenAI · Images", capability:"image", model:"gpt-image-1", url:""},
  {name:"gemini", label:"Google Gemini · Images", capability:"image", model:"gemini-3.1-flash-image", url:""},
];
function SettingsPanel({ onClose }: { onClose: () => void }) {
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
    try {await api.upsertProvider(choice.capability,name,key,model,url);setKey("");await refresh();setMessage("Provider saved.");}
    catch(e:any){setMessage(e.message);}finally{setBusy(false);}
  }
  return <div className="drawer-backdrop" onClick={onClose}><div className="drawer provider-studio" ref={drawerRef} role="dialog" aria-modal="true" aria-label="Editor panel" tabIndex={-1} onClick={e=>e.stopPropagation()}>
    <button className="icon-btn drawer-close" aria-label="Close panel" onClick={onClose}><X size={16}/></button>
    <h3>Settings — Providers</h3><p className="hint">Anthropic Claude analyzes images and writes prompts, but does not provide a photo-generation API. Choose an image engine below.</p><p className="hint">Connect image-generation services. Local narration engines are managed separately under Audio → Local voice engines.</p>
    <div className="provider-list">{providers.filter(p=>p.capability==="image").map(p=><article className="provider-card" key={p.id}><strong>{PROVIDER_OPTIONS.find(o=>o.name===p.name)?.label||p.name}</strong><small>{p.model} · {p.masked_key||"No key required"}</small><div className="button-row"><button className="text-btn" disabled={busy} onClick={()=>select(p.name)}>Edit</button><button className="text-btn" disabled={busy} onClick={async()=>{try{await api.deleteProviderProfile(p.id);await refresh();}catch(e:any){setMessage(e.message);}}}>Remove</button></div></article>)}</div>
    <fieldset disabled={busy} className="provider-form"><label className="control-label">Provider<select aria-label="Provider" value={name} onChange={e=>select(e.target.value)}>{PROVIDER_OPTIONS.map(o=><option value={o.name} key={o.name}>{o.label}</option>)}</select></label>
    <p className="hint">{PROVIDER_NOTES[name]}</p>
    {(name==="cloudflare"||name==="local_sd")&&<label className="control-label">{name==="cloudflare"?"Cloudflare account ID":"Local engine URL"}<input aria-label="Provider connection" value={url} onChange={e=>setUrl(e.target.value)}/></label>}
    <label className="control-label">Model<input disabled={name==="cloudflare"} aria-label="Provider model" value={model} onChange={e=>setModel(e.target.value)}/></label>

    {name!=="local_sd"&&<label className="control-label">{choice.capability==="image"?"API key (re-enter to save)":"Service token (optional)"}<input aria-label="Provider API key" type="password" autoComplete="off" value={key} onChange={e=>setKey(e.target.value)}/></label>}
    <button className="btn btn-primary" disabled={busy||(name!=="local_sd"&&!key.trim())} onClick={save}>{busy?"Saving…":"Save provider"}</button></fieldset>
    {message&&<p role="status">{message}</p>}<button className="btn" onClick={onClose}>Close</button>
  </div></div>;
}

function VoicePanel({ scene, onChanged }: { scene: Scene; onChanged: () => void }) {
  const [providers,setProviders]=useState<ProviderProfile[]>([]);
  const [providerId,setProviderId]=useState("unselected");
  const [voices,setVoices]=useState<string[]>([]);
  const [voice,setVoice]=useState("af_heart");
  const [language,setLanguage]=useState(/[\u0600-\u06ff]/.test(scene.spoken_text)?"ar":"en");
  const [speed,setSpeed]=useState(1);
  const [localStatus,setLocalStatus]=useState("");
  async function connectEngine(engine:string) {
    setBusy(true);setErr(null);setLocalStatus("Checking local engine…");
    try {
      const result=await api.connectLocalSpeech(engine);
      setProviders(old=>[...old.filter(p=>p.id!==result.profile.id),result.profile]);
      setProviderId(result.profile.id);setVoices(result.voices);setVoice(result.voices[0]);
      if(engine==="chatterbox"&&/[\u0600-\u06ff]/.test(scene.spoken_text))setLanguage("ar");
      if(engine==="kokoro"&&!['en','es','fr','hi','it','ja','pt','zh'].includes(language))setLanguage("en");
      setLocalStatus(result.message);
    } catch(e:any){setErr(e.message);setLocalStatus("Engine unavailable. No fallback voice was selected.");}
    finally{setBusy(false);}
  }
  const selectedEngine=providers.find(p=>p.id===providerId)?.name;
  const voicePrefix:Record<string,string>={en:"ab",es:"e",fr:"f",hi:"h",it:"i",ja:"j",pt:"p",zh:"z"};
  const availableVoices=selectedEngine==="kokoro"?voices.filter(v=>(voicePrefix[language]||"").includes(v[0])):voices;
  useEffect(()=>{if(availableVoices.length&&!availableVoices.includes(voice))setVoice(availableVoices[0]);},[language,voices,providerId]);
  useEffect(()=>{api.listProviders().then(p=>setProviders(p.filter(v=>v.capability==="speech"))).catch(()=>{});},[]);
  async function connect(id:string){
    setProviderId(id);setVoices([]);setErr(null);if(providers.find(p=>p.id===id)?.name==="kokoro"&&!voicePrefix[language])setLanguage("en");
    if(!id)return;
    setBusy(true);
    try{const result=await api.providerVoices(id);setVoices(result.voices);setVoice(result.voices[0]||"default");}
    catch(e:any){setErr(e.message);}finally{setBusy(false);}
  }
  const [open, setOpen] = useState(true);
  const [busy, setBusy] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function audition() {
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
        <strong style={{ display: "flex", alignItems: "center", gap: 6 }}><Volume2 size={14} /> Voice</strong>
        <button className="btn" onClick={() => setOpen((o) => !o)}>{open ? "Hide" : "Settings / Audition"}</button>
      </div>
      {open && (
        <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
          <section className="local-voice-component"><h3>Local voice engines</h3><p className="hint">Natural speech runs on this computer after the engine and model are installed. No AI provider key is required.</p><div className="button-row"><button className="btn" disabled={busy} onClick={()=>connectEngine("chatterbox")}>Connect Chatterbox · Arabic + multilingual</button><button className="btn" disabled={busy} onClick={()=>connectEngine("kokoro")}>Connect Kokoro</button></div><p className="hint">First-time setup: run START_CHATTERBOX_VOICE.bat or START_KOKORO_VOICE.bat from your app folder. The launcher installs/starts the local component using Docker Desktop.</p>{localStatus&&<p role="status">{localStatus}</p>}</section>
          <fieldset disabled={busy} className="provider-form"><label className="control-label">Narration engine<select aria-label="Narration engine" value={providerId} onChange={e=>connect(e.target.value)}><option value="unselected">Select a local engine…</option><option value="">Diagnostic voice — robotic (espeak)</option>{providers.map(p=><option value={p.id} key={p.id}>{p.name}</option>)}</select></label>
          <label className="control-label">Language<select aria-label="Narration language" value={language} onChange={e=>setLanguage(e.target.value)}>{(selectedEngine==="kokoro"?["en","fr","es","it","pt","ja","zh","hi"]:["en","ar","fr","es","de","it","pt","ja","zh","hi","ko","ru","tr"]).map(v=><option value={v} key={v}>{{en:"English",ar:"Arabic",fr:"French",es:"Spanish",de:"German",it:"Italian",pt:"Portuguese",ja:"Japanese",zh:"Chinese",hi:"Hindi",ko:"Korean",ru:"Russian",tr:"Turkish"}[v]}</option>)}</select></label>
          {providerId&&<><label className="control-label">Voice<select aria-label="Narration voice" value={voice} onChange={e=>setVoice(e.target.value)}>{availableVoices.map(v=><option key={v}>{v}</option>)}</select></label><button className="text-btn" onClick={()=>connect(providerId)}>Refresh voices / test connection</button><label className="control-label">Speaking speed · {speed.toFixed(2)}×<input aria-label="Speaking speed" type="range" min={.5} max={2} step={.05} value={speed} onChange={e=>setSpeed(Number(e.target.value))}/></label></>}
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
            <button className="btn" disabled={busy || !scene.voice_takes.some(t => t.accepted)} onClick={async () => {setBusy(true); setErr(null); try {await api.clearNarration(scene.id); onChanged();} catch(e:any) {setErr(e.message);} finally {setBusy(false);}}}>Use no narration</button>
            <input ref={fileRef} type="file" accept="audio/*" style={{ display: "none" }}
              onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadTake(f); }} />
          </div>
          <small className="hint">
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
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function FontPanel({ scene, onChange }: { scene: Scene; onChange: (f: Partial<Scene["font_json"]>) => void }) {
  const f = scene.font_json;
  return (
    <div className="font-panel">
      <label>Family
        <select value={f.family} onChange={(e) => onChange({ family: e.target.value })}>
          {FONT_FAMILIES.map((x) => <option key={x} value={x}>{x}</option>)}
        </select>
      </label>
      <label>Size <input type="number" min={16} max={96} key={f.size} defaultValue={f.size} onBlur={(e) => {const size = Math.max(16, Math.min(96, Number(e.target.value) || f.size)); e.target.value = String(size); if (size !== f.size) onChange({size});}} /></label>
      <label>Color <input type="color" value={f.color} onChange={(e) => onChange({ color: e.target.value })} /></label>
      <label>Outline color <input type="color" value={f.outline_color} onChange={(e) => onChange({ outline_color: e.target.value })} /></label>
      <label>Outline width <input type="number" min={0} max={8} key={f.outline_width} defaultValue={f.outline_width} onBlur={(e) => {const outline_width = Math.max(0, Math.min(8, Number(e.target.value) || 0)); e.target.value = String(outline_width); if (outline_width !== f.outline_width) onChange({outline_width});}} /></label>
      <label>Background
        <select value={f.background} onChange={(e) => onChange({ background: e.target.value })}>
          <option value="none">None</option>
          <option value="box">Box</option>
        </select>
      </label>
      <label>Position
        <select value={f.position} onChange={(e) => onChange({ position: e.target.value })}>
          <option value="bottom">Bottom</option>
          <option value="top">Top</option>
          <option value="middle">Middle</option>
        </select>
      </label>
      <label style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
        <input type="checkbox" checked={f.captions_enabled} onChange={(e) => onChange({ captions_enabled: e.target.checked })} />
        Captions enabled
      </label>
      <label style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
        <input type="checkbox" checked={!!f.typewriter} onChange={(e) => onChange({ typewriter: e.target.checked })} />
        Typewriter reveal
      </label>
      {!f.captions_enabled && (
        <small className="hint">Font changes have no visible effect while captions are disabled.</small>
      )}
      
    </div>
  );
}

function TextLayers({scene,onChange}:{scene:Scene;onChange:(layers:NonNullable<Scene["font_json"]["layers"]>)=>void}) {
  const layers=scene.font_json.layers||[];
  const patch=(id:string,values:object)=>onChange(layers.map(l=>l.id===id?{...l,...values}:l));
  return <section className="text-layers"><div className="section-heading"><h3>Text overlays</h3><span>{layers.length}/12</span></div><p className="hint">Add titles and labels independently of captions. Coordinates are percentages; end 0 means scene end. Preview shows all layers; render applies timing.</p>
    {layers.map((l,i)=><article className="layer-card" key={l.id}><div className="section-heading"><strong>Layer {i+1}</strong><button className="text-btn" onClick={()=>onChange(layers.filter(v=>v.id!==l.id))}>Remove</button></div>
    <textarea aria-label={`Layer ${i+1} text`} dir="auto" key={l.text} defaultValue={l.text} onBlur={e=>{if(e.target.value!==l.text)patch(l.id,{text:e.target.value});}}/>
    <div className="layer-fields">{[{key:"x",label:"X (%)",max:100},{key:"y",label:"Y (%)",max:100},{key:"size",label:"Size",max:200},{key:"start_ms",label:"Start (ms)",max:3600000},{key:"end_ms",label:"End (ms)",max:3600000}].map(field=><label className="control-label" key={field.key}>{field.label}<input type="number" min={field.key==="size"?12:0} max={field.max} key={String(l[field.key as keyof typeof l])} defaultValue={Number(l[field.key as keyof typeof l])} onBlur={e=>{const n=Math.min(field.max,Math.max(field.key==="size"?12:0,Number(e.target.value)||0));if(n!==l[field.key as keyof typeof l])patch(l.id,{[field.key]:n});}}/></label>)}
    <label className="control-label">Font<select value={l.family||'Noto Naskh Arabic'} onChange={e=>patch(l.id,{family:e.target.value})}><option>Noto Naskh Arabic</option><option>Noto Sans Arabic</option></select></label><label className="control-label">Alignment<select value={l.align||'center'} onChange={e=>patch(l.id,{align:e.target.value})}>{['left','center','right'].map(v=><option key={v}>{v}</option>)}</select></label>{(['outline_width','shadow','exit_ms'] as const).map(k=><label key={k} className="control-label">{k==='exit_ms'?'Exit fade (ms)':k==='shadow'?'Shadow':'Outline'}<input type="number" min={0} max={k==='exit_ms'?10000:10} value={l[k]||0} onChange={e=>patch(l.id,{[k]:Math.max(0,Math.min(k==='exit_ms'?10000:10,+e.target.value))})}/></label>)}<label className="control-label">Animation<select aria-label={`Layer ${i+1} animation`} value={l.animation||'none'} onChange={e=>patch(l.id,{animation:e.target.value})}>{ANIMATIONS.map(v=><option key={v}>{v}</option>)}</select></label><label className="control-label">Animation ms<input type="number" min={100} max={10000} defaultValue={l.animation_ms||800} onBlur={e=>patch(l.id,{animation_ms:Math.max(100,Math.min(10000,Number(e.target.value)||800))})}/></label><label className="control-label">Color<input type="color" value={l.color} onChange={e=>patch(l.id,{color:e.target.value})}/></label></div><label className="check-label"><input type="checkbox" checked={l.bold} onChange={e=>patch(l.id,{bold:e.target.checked})}/>Bold</label></article>)}
    <button className="btn" disabled={layers.length>=12} onClick={()=>onChange([...layers,{id:crypto.randomUUID(),text:"Your title",x:50,y:25,size:64,color:"#FFFFFF",start_ms:0,end_ms:0,bold:true}])}><Plus size={14}/> Add text overlay</button>
  </section>;
}

type InspectorTab = "Media" | "Motion" | "Effects" | "Text" | "Audio";
const INSPECTOR_TABS: {name: InspectorTab; Icon: typeof Film}[] = [
  {name: "Media", Icon: ImageIcon}, {name: "Motion", Icon: Film},
  {name: "Effects", Icon: Palette}, {name: "Text", Icon: Type}, {name: "Audio", Icon: Volume2},
];

function durationLabel(scene: Scene) {
  const ms = scene.timing_mode === "fixed" ? scene.requested_duration_ms : scene.measured_duration_ms;
  return ms ? `${(ms / 1000).toFixed(1)}s` : "Auto";
}

// Each scene stays mounted while navigating, preserving its draft and render subscription.
// All writes for a scene run sequentially, so an older response cannot overwrite a newer edit.
function PartRow({scene, project, index, total, active, refresh, onMove, onDelete, onOpenSettings, onSaveState}: {
  scene: Scene; project: Project; index: number; total: number; active: boolean;
  refresh: () => Promise<void>; onMove: (dir: -1 | 1) => void; onDelete: () => void;
  onOpenSettings: () => void; onSaveState: (id: string, state: string) => void;
}) {
  const [tab, setTab] = useState<InspectorTab>("Media");
  const [chatOpen, setChatOpen] = useState(false);
  const [text, setText] = useState(scene.spoken_text || scene.original_text);
  const [captions, setCaptions] = useState(scene.subtitle_text);
  const [search, setSearch] = useState("");
  const soundRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [previewMode, setPreviewMode] = useState<"source" | "render">(scene.rendered_asset_id ? "render" : "source");
  const [selectedShotId, setSelectedShotId] = useState(scene.shots[0]?.id || "");
  const [zoom, setZoom] = useState(100);
  const fileRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const editorRef = useRef<HTMLElement>(null);
  const pending = useRef<Record<string, unknown>>({});
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const queue = useRef<Promise<boolean>>(Promise.resolve(true));
  const writes = useRef(0);
  const alive = useRef(true);
  const job = useJobProgress(jobId);
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
    pending.current = {...pending.current, ...patch};
    onSaveState(scene.id, "Unsaved changes");
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => { void flush(); }, 500);
  }
  async function update(patch: Record<string, unknown>) {
    if (await flush()) await run(() => api.updateScene(scene.id, patch));
  }
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
    if (!scene.voice_takes.some(t => t.accepted) && !(scene.font_json.typewriter_sound && scene.font_json.typewriter && scene.font_json.captions_enabled && captions.trim()) && !confirm("No narration take is selected. Render this scene without narration?")) return;
    try { setJobId((await api.renderPart(scene.id)).job_id); }
    catch (e: any) { setError(e.message); }
  }
  const activeMotion = shot?.motion_json?.type || "static";
  const selectedEffect = EFFECTS.find(f => f.key === scene.effect_preset) || EFFECTS[0];
  const strength = scene.effect_intensity / 100;
  const previewFilter = selectedEffect.swatch.replace(/([a-z-]+)\(([-.\d]+)([^)]*)\)/g,(_,fn,n,unit)=>{
    const base=["contrast","brightness","saturate"].includes(fn)?1:0;
    return `${fn}(${base+(Number(n)-base)*strength}${unit})`;
  });
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
          <div className="preview-toolbar">
            <div className="segmented" aria-label="Preview mode">
              <button aria-pressed={previewMode === "source"} onClick={() => setPreviewMode("source")}>Preview</button>
              <button aria-pressed={previewMode === "render"} disabled={!rendered} onClick={() => setPreviewMode("render")}>Rendered scene</button>
            </div>
            <span className="aspect-badge">{project.aspect}</span>
          </div>
          <div className="canvas-viewport">
            <div className="preview-canvas" style={{aspectRatio: project.aspect.replace(":", "/"), width: `min(${zoom}%, calc((var(--stage-height) - 40px) * ${canvasRatio * zoom / 100}))`}}>
              {previewMode === "render" && rendered ? <video ref={videoRef} className="canvas-media" controls preload="metadata" src={api.assetStreamUrl(rendered)}/> :
                shot ? shot.asset?.type === "image" ? (shot.crop_json?<svg className="canvas-media" role="img" aria-label={`Cropped source for ${scene.title}`} viewBox={`${shot.crop_json.x*(shot.asset.width||1)} ${shot.crop_json.y*(shot.asset.height||1)} ${shot.crop_json.width*(shot.asset.width||1)} ${shot.crop_json.height*(shot.asset.height||1)}`} preserveAspectRatio={shot.fit==='cover'?'xMidYMid slice':'xMidYMid meet'} style={{filter:previewFilter}}><image href={api.assetStreamUrl(shot.asset_id)} width={shot.asset.width||1} height={shot.asset.height||1}/></svg>:<img className="canvas-media" src={api.assetStreamUrl(shot.asset_id)} alt={`Source media for ${scene.title}`} style={{objectFit: shot.fit === "cover" ? "cover" : "contain", filter:previewFilter}}/>) :
                  <video ref={videoRef} className="canvas-media" controls preload="metadata" src={api.assetStreamUrl(shot.asset_id)} style={{objectFit:shot.fit === "cover" ? "cover" : "contain",filter:previewFilter}}/> :
                  <div className="canvas-empty"><div className="empty-icon"><ImageIcon size={30}/></div><h3>Start with a visual</h3><p>Add an image or video to bring this scene to life.</p><button className="btn btn-primary" onClick={() => fileRef.current?.click()}><Plus size={15}/> Add media</button><button className="text-btn" onClick={() => setChatOpen(true)}><Sparkles size={14}/> Or generate an image</button></div>}
              {previewMode==="source"&&shot?.asset?.type==="image"&&scene.effect_preset==="glitch"&&strength>0&&<img aria-hidden="true" className="canvas-media glitch-slice glitch-full" src={api.assetStreamUrl(shot.asset_id)} alt="" style={{objectFit:shot.fit==="cover"?"cover":"contain",opacity:strength}}/>}
              {previewMode==="source"&&shot&&(scene.font_json.layers||[]).map(l=><div className="canvas-text-layer" key={l.id} dir="auto" style={{left:`${l.x}%`,top:`${l.y}%`,fontSize:`${l.size/project.width*100}cqw`,color:l.color,fontFamily:l.family||scene.font_json.family,fontWeight:l.bold?700:400,textAlign:(l.align||"center") as any,transform:`translate(${l.align==="left"?0:l.align==="right"?-100:-50}%,-50%)`,WebkitTextStroke:`${(l.outline_width||0)/project.width*100}cqw black`,textShadow:l.shadow?`${l.shadow/project.width*100}cqw ${l.shadow/project.width*100}cqw black`:"none"}}>{l.text}</div>)}
            </div>
          </div>
          <footer className="preview-footer">
            <span>{previewMode === "source" ? "Editing preview • Effects approximate; render for motion, captions & sound" : scene.is_stale ? "Previous render • Changes need a new render" : "Rendered scene"}</span>
            <label className="zoom-control">View <select aria-label="Canvas view size" value={zoom} onChange={e => setZoom(Number(e.target.value))}><option value={100}>Fit</option><option value={75}>75%</option><option value={50}>50%</option></select></label>
          </footer>
        </div>
        <div className="render-bar">
          <span className={`render-status ${scene.is_stale && rendered ? "needs-render" : ""}`}><span className="status-dot"/>{isGenerating ? `${job?.stage || "Rendering"} · ${Math.round(job?.progress || 0)}%` : !shot ? "Add media to render" : scene.is_stale && rendered ? "Changes since last render" : rendered ? "Scene ready" : "Ready for first render"}</span>
          <div className="button-row">
            {rendered && <a className="icon-btn" title="Download scene" aria-label="Download scene" href={api.assetDownloadUrl(rendered)} download><Download size={17}/></a>}
            {isGenerating ? <button className="btn" onClick={() => run(() => api.cancelJob(jobId!))}>Cancel render</button> : <button className="btn btn-primary" onClick={render} disabled={!shot}><Play size={15}/> Render scene</button>}
          </div>
        </div>
        {isGenerating && <progress aria-label="Scene rendering progress" max={100} value={job?.progress || 0}/>}
        {(error || job?.status === "failed") && <div role="alert" className="error-box"><details><summary>Render/save failed — show details</summary><pre>{error || job?.error}</pre></details><button className="text-btn" onClick={()=>{setError(null);setJobId(null);}}>Dismiss</button>{error && <button className="text-btn" onClick={async () => { setError(null); await flush(); }}>Retry text save / dismiss</button>}</div>}
        <section className="script-card">
          <div className="section-heading"><h3><FileText size={16}/> Narration script</h3><span className="subtle">{text.trim() ? text.trim().split(/\s+/).length : 0} words</span></div>
          <textarea aria-label="Narration script" dir="auto" className="script-box" value={text} onChange={e => {setText(e.target.value); draft({original_text: e.target.value, spoken_text: e.target.value});}} onBlur={() => void flush()} placeholder="Tell your story. Paste or write the narration for this scene…"/>
          <div className="script-footer"><span>Changes save automatically. Captions are edited in Text.</span><button className="text-btn" onClick={async () => {if (await flush()) setTab("Audio");}}><Volume2 size={14}/> Voice & narration <ChevronRight size={14}/></button></div>
        </section>
      </div>
      <aside className="inspector" aria-label="Scene inspector">
        <div className="inspector-heading"><span className="eyebrow">SCENE SETTINGS</span><span className="subtle">{durationLabel(scene)}</span></div>
        <div className="inspector-tabs" role="tablist" aria-label="Scene tools">
          {INSPECTOR_TABS.map(({name, Icon}) => <button key={name} role="tab" id={`${scene.id}-${name}-tab`} aria-controls={`${scene.id}-panel`} aria-selected={tab === name} onClick={() => setTab(name)} onKeyDown={e => {
            const offset = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
            if (offset) {e.preventDefault(); const next = INSPECTOR_TABS[(INSPECTOR_TABS.findIndex(t => t.name === name) + offset + INSPECTOR_TABS.length) % INSPECTOR_TABS.length].name; setTab(next); document.getElementById(`${scene.id}-${next}-tab`)?.focus();}
          }} tabIndex={tab === name ? 0 : -1}><Icon size={18}/><span>{name}</span></button>)}
        </div>
        <div className="inspector-body" role="tabpanel" id={`${scene.id}-panel`} aria-labelledby={`${scene.id}-${tab}-tab`}>
          {tab === "Media" && <>
            <div className="section-heading"><h3>Scene media</h3><span className="count-badge">{scene.shots.length}</span></div>
            <p className="hint">Images and clips play in the order shown.</p>
            <div className="media-grid">{scene.shots.map((s,i) => <div className={`media-item ${s.id === shot?.id ? "selected" : ""}`} key={s.id}>
              <button className="media-select" aria-label={`Select media ${i+1}`} aria-pressed={s.id === shot?.id} onClick={() => {setSelectedShotId(s.id); setPreviewMode("source");}}>{s.asset?.type === "image" ? <img src={api.assetStreamUrl(s.asset_id)} alt=""/> : <video preload="metadata" muted src={api.assetStreamUrl(s.asset_id)}/>}<span>{String(i+1).padStart(2,"0")}</span></button>
              <button className="remove-media" aria-label={`Remove media ${i+1}`} disabled={saving} onClick={() => run(() => api.deleteShot(s.id))}><X size={12}/></button>
            </div>)}</div>
            <button className="btn upload-btn" disabled={saving} onClick={() => fileRef.current?.click()}><Upload size={16}/> Upload image or video</button>
            <button className="btn ai-btn" onClick={() => setChatOpen(true)}><Sparkles size={16}/> Generate image</button>
            {shot && <label className="control-label">Frame fit<select aria-label="Frame fit" value={shot.fit} disabled={saving} onChange={e => {const fit = e.currentTarget.value; setPreviewMode("source"); void run(() => api.updateShot(shot.id, {fit}));}}><option value="cover">Fill frame (crop)</option><option value="contain">Fit inside frame (show entire image)</option></select><span className="hint">Fit preserves the whole image with bars where needed. Fill crops the edges to cover the frame.</span></label>}
          </>}
          {tab === "Motion" && <>{shot&&<FramingControls key={shot.id} shot={shot} save={run}/>}<h3>Camera movement</h3><p className="hint">Applied to {shot ? `media ${scene.shots.indexOf(shot)+1}` : "selected media"}. {shot?.fit !== "cover" ? "Motion requires Fill frame; Fit inside frame keeps the entire image still." : "Render to preview the movement."}</p><div className="motion-box">{MOTIONS.map(({key,label,Icon}) => <button key={key} className={`motion-btn ${activeMotion === key ? "selected" : ""}`} aria-pressed={activeMotion === key} disabled={!shot || saving || shot.fit !== "cover"} onClick={() => run(() => api.updateShot(shot.id,{motion:{type:key}}))}><Icon size={19}/><span>{label}</span></button>)}</div></>}
          {tab === "Effects" && <><h3>Image looks</h3><p className="hint">Choose a look for the whole scene.</p><label className="search-control"><Search size={15}/><input aria-label="Search effects" placeholder="Search effects…" value={search} onChange={e => setSearch(e.target.value)}/></label><div className="effects-grid">{EFFECTS.filter(f => f.label.toLowerCase().includes(search.toLowerCase())).map(fx => <button key={fx.key} className={`effect-tile ${scene.effect_preset === fx.key ? "selected" : ""}`} aria-pressed={scene.effect_preset === fx.key} disabled={saving} onClick={() => {setPreviewMode("source"); void update({effect_preset:fx.key});}}>
            <div className="effect-image">{shot?.asset?.type === "image" ? <img src={api.assetStreamUrl(shot.asset_id)} alt="" style={{filter:fx.swatch}}/> : <div className="effect-swatch" style={{filter:fx.swatch}}/>}{scene.effect_preset === fx.key && <CheckCircle2 size={17}/>}</div><span>{fx.label}</span></button>)}</div>{!EFFECTS.some(f => f.label.toLowerCase().includes(search.toLowerCase())) && <p className="hint">No matching effects.</p>}<p className="hint">Thumbnails are approximate. Glitch adds full-frame RGB separation and tearing across the top, middle and bottom. Render to check the exact result.</p><button className="btn" disabled={!shot||saving||isGenerating} onClick={render}><Play size={14}/> Render effect preview</button><label className="control-label">Effect strength · {scene.effect_intensity}%<input aria-label="Effect strength" type="range" min={0} max={100} step={5} disabled={saving||scene.effect_preset==="original"} key={scene.effect_intensity} defaultValue={scene.effect_intensity} onChange={e=>draft({effect_intensity:Number(e.target.value)})} onBlur={()=>void flush()}/></label><button className="text-btn" disabled={saving || scene.effect_preset === "original"} onClick={() => {setPreviewMode("source"); void update({effect_preset:"original"});}}>Reset to original</button></>}
          {tab === "Text" && <><h3>On-screen captions</h3><p className="hint">Caption text is independent of narration.</p><textarea aria-label="On-screen captions" dir="auto" className="caption-box" value={captions} onChange={e => {setCaptions(e.target.value); draft({subtitle_text:e.target.value});}} onBlur={() => void flush()} placeholder="Write the text to appear on your video…"/><button className="text-btn" onClick={() => {setCaptions(text); draft({subtitle_text:text});}}><Copy size={13}/> Copy narration to captions</button><fieldset disabled={saving}><FontPanel scene={scene} onChange={f => update({font:f})}/><TextLayers scene={scene} onChange={layers=>update({font:{layers}})}/></fieldset><section className="typewriter-controls"><h3>Typewriter timing & sound</h3>
            <p className="hint">Enable Captions and Typewriter reveal above. Sound follows each reveal, not the original recording’s rhythm.</p>
            <label className="check-label"><input type="checkbox" checked={!!scene.font_json.typewriter_sound} disabled={saving} onChange={e=>update({font:{typewriter_sound:e.target.checked}})}/> Synchronized keystrokes</label>
            <div className="button-row">{[{label:"Slow",ms:220},{label:"Natural",ms:160},{label:"Fast",ms:80}].map(p=><button className="btn" disabled={saving} key={p.label} onClick={()=>update({font:{typewriter_duration_ms:Math.min(120000,Math.max(100,(Array.from(captions).length-1)*p.ms))}})}>{p.label}</button>)}</div><button className="text-btn" disabled={saving} onClick={()=>update({timing_mode:"fixed",requested_duration_ms:Math.max(scene.requested_duration_ms||4000,(scene.font_json.typewriter_delay_ms||0)+(scene.font_json.typewriter_duration_ms||Math.max(200,(Array.from(captions).length-1)*160))+1000)})}>Extend scene to fit typing + 1s hold</button>
            <div className="timing-inputs"><label className="control-label">Start delay (seconds)<input aria-label="Typing start delay" type="number" min={0} max={120} step={.1} key={scene.font_json.typewriter_delay_ms} defaultValue={(scene.font_json.typewriter_delay_ms||0)/1000} onBlur={e=>{const v=Math.min(120,Math.max(0,Number(e.target.value)||0))*1000;if(v!==(scene.font_json.typewriter_delay_ms||0))void update({font:{typewriter_delay_ms:v}});}}/></label>
            <label className="control-label">Reveal time (seconds)<input aria-label="Typing reveal time" type="number" min={.1} max={120} step={.1} key={scene.font_json.typewriter_duration_ms} defaultValue={scene.font_json.typewriter_duration_ms ? scene.font_json.typewriter_duration_ms/1000 : ''} placeholder="Auto" onBlur={e=>{if(e.target.value){const v=Math.min(120,Math.max(.1,Number(e.target.value)||3))*1000;void update({font:{typewriter_duration_ms:v}});}}}/></label></div>
            <p className="hint">Short scenes compress the reveal and make typing faster. Choose Slow, then Extend scene to preserve the slower speed. This switches duration to Fixed; narration may be trimmed to that duration.</p>
            <label className="control-label">Keystroke volume (%)<input aria-label="Keystroke volume" type="number" min={0} max={100} key={scene.font_json.typewriter_volume} defaultValue={scene.font_json.typewriter_volume??50} onBlur={e=>{const v=Math.min(100,Math.max(0,Number(e.target.value)||0));if(v!==(scene.font_json.typewriter_volume??50))void update({font:{typewriter_volume:v}});}}/></label>
            <p className="hint">{scene.font_json.typewriter_sound_asset_id ? 'Sound: uploaded recording (a short keystroke is extracted).' : 'Sound: keystroke extracted from your supplied typewriter MP3.'}</p>
            <button className="btn upload-btn" disabled={saving} onClick={()=>soundRef.current?.click()}><Upload size={14}/> Upload typewriter sound</button>
            {scene.font_json.typewriter_sound_asset_id && <button className="text-btn" disabled={saving} onClick={()=>update({font:{typewriter_sound_asset_id:null}})}>Use included keystroke</button>}
            <p className="hint">If this recording was previously uploaded as narration, choose Audio → Use no narration to avoid hearing it twice.</p>
          </section><p className="hint">Render the scene to preview captions and synchronized sound together.</p></>}
          {tab === "Audio" && <><h3>Voice & narration</h3><p className="hint">Connect a local speech component or upload a recording. Select a take before rendering.</p><VoicePanel scene={scene} onChanged={refresh}/></>}
          <section className="timing-section"><h3><Clock size={15}/> Scene duration</h3><label className="control-label">Timing mode<select aria-label="Timing mode" value={scene.timing_mode} disabled={saving} onChange={e => update({timing_mode:e.target.value})}><option value="audio_driven">Match narration</option><option value="fixed">Fixed duration</option></select></label>
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
  useEffect(()=>{api.health().then(h=>{if(h.build!=="workspace-2.5")setMessage("Backend update required: this interface is connected to a different backend version. Stop the existing server, install the Workspace 2.5 release into that installation, restart scripts/start.bat, then Ctrl+F5.");}).catch(()=>setMessage("Cannot verify backend version. Check that the SceneForge server is running."));},[]);
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
  const [importStatus,setImportStatus]=useState('');
  const [menu,setMenu]=useState('');
  const importRef=useRef<HTMLInputElement>(null),audioImportRef=useRef<HTMLInputElement>(null),folderRef=useRef<HTMLInputElement>(null);
  const [history,setHistory]=useState<{undo:()=>Promise<unknown>;redo:()=>Promise<unknown>;label:string}[]>([]);
  const [future,setFuture]=useState<typeof history>([]);
  async function record(label:string,undo:()=>Promise<unknown>,redo:()=>Promise<unknown>){
    if(await action(async()=>{await redo();await refresh();})){setHistory(h=>[...h.slice(-29),{undo,redo,label}]);setFuture([]);}
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
  async function addPoolAssets(assets:Asset[]){if(!project)return;await action(async()=>{for(const asset of assets){if(asset.type==='audio')continue;const scene=await api.addScene(project.id);await api.updateScene(scene.id,{title:asset.original_filename,timing_mode:'fixed',requested_duration_ms:asset.type==='video'?(asset.duration_ms||4000):4000});await api.addShot(scene.id,asset.id);setSelectedId(scene.id);}setHistory([]);setFuture([]);await refresh();});}
  async function usePoolAsset(asset:Asset){if(!selected)return;await action(async()=>{if(asset.type==='audio')await api.useAudioAsset(selected.id,asset.id);else await api.addShot(selected.id,asset.id);await refresh();});}

  async function importAudio(file:File|undefined){
    if(!selected||!file)return;setMenu('');
    await action(async()=>{const take=await api.uploadVoiceTake(selected.id,file);await api.selectTake(take.id);await refresh();});
  }
  useEffect(()=>{const close=(e:MouseEvent)=>{if(!(e.target as Element).closest('.editor-menu'))setMenu('');};const escape=(e:KeyboardEvent)=>{if(e.key==='Escape')setMenu('');};document.addEventListener('click',close);document.addEventListener('keydown',escape);return()=>{document.removeEventListener('click',close);document.removeEventListener('keydown',escape);};},[]);
  const [exportScenes,setExportScenes] = useState<Scene[]>([]);
  const [exportJobId, setExportJobId] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebar, setSidebar] = useState(true);
  const [libraryTab,setLibraryTab] = useState<'Scenes'|'Media Pool'|'Effects'|'Transitions'>('Scenes');
  const [states, setStates] = useState<Record<string,string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const exportJob = useJobProgress(exportJobId);
  const exporting = !!exportJob && ["queued", "running", "cancelling"].includes(exportJob.status);
  const dirty = Object.values(states).some(s => s !== "Saved");
  const failed = Object.values(states).some(s => s === "Save failed");
  const status = failed ? "Save failed" : dirty ? "Saving changes…" : "All changes saved";
  const selected = project?.scenes.find(s => s.id === selectedId) || project?.scenes[0];
  projectRef.current = project;
  useEffect(() => {api.listProjects().then(setProjects).catch(e => setError(e.message)).finally(() => setLoading(false));}, []);
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {if(dirty) {e.preventDefault(); e.returnValue="";}};
    window.addEventListener("beforeunload",warn); return () => window.removeEventListener("beforeunload",warn);
  }, [dirty]);
  useEffect(() => {
    if(exportJob && ["succeeded","failed","cancelled"].includes(exportJob.status)) void refresh().catch(e => setError(e.message));
  },[exportJob?.status]);
  async function renderFullVideo(){
    if(!project||busy||dirty||exporting)return;
    await action(async()=>{const empty=project.scenes.filter(s=>!s.shots.length);
      if(!project.scenes.some(s=>s.shots.length))return;
      if(empty.length&&!confirm(`Skip ${empty.length} empty scene(s) and render all scenes with media?`))return;
      setExportPanel(true);setExportExpanded(false);setExportScenes(structuredClone(project.scenes));
      setExportJobId((await api.exportProject(project.id,empty.length>0)).job_id);
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
    if(!confirm(`Delete “${p.title}” and its scenes? This cannot be undone. Original and cached media files are retained on disk.`))return;
    await action(async()=>{await api.deleteProject(p.id);setProjects(old=>old.filter(x=>x.id!==p.id));});
  }
  async function createProject() {
    await action(async () => {const p=await api.createProject(newTitle.trim()||"Untitled documentary",newAspect); await openProject(p.id); setProjects(await api.listProjects());});
  }
  async function resizeDuration(id:string,ms:number){
    const scene=project?.scenes.find(s=>s.id===id);if(!scene)return;
    const take=scene.voice_takes.find(t=>t.accepted);
    if(take&&ms<(take.measured_duration_ms||0)+(scene.lead_ms||0)+(scene.trail_ms||0)&&!confirm('This duration may cut narration short. Switch to fixed timing?'))return;
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
      const scene=await api.addScene(project.id);
      await api.addShot(scene.id,asset.id);
      await api.updateScene(scene.id,{title:'Title · '+design.text.slice(0,40),timing_mode:'fixed',requested_duration_ms:Math.round(design.duration*1000),font:{captions_enabled:false,layers:[{...design.layer,id:crypto.randomUUID(),text:design.text}]}});
      setHistory([]);setFuture([]);setTitleCard(false);setLibraryTab('Scenes');await refresh();setSelectedId(scene.id);
    });
  }
  async function addPart() {
    if(!project) return;
    await action(async () => {const s=await api.addScene(project.id);setHistory([]);setFuture([]); await refresh(); setSelectedId(s.id);});
  }
  async function moveScene(id:string,dir:-1|1) {
    if(!project) return;
    const ids=project.scenes.map(s=>s.id), i=ids.indexOf(id), j=i+dir;
    if(i<0||j<0||j>=ids.length) return;
    await action(async () => {[ids[i],ids[j]]=[ids[j],ids[i]]; await api.reorderScenes(project.id,ids); await refresh();});
  }
  async function deleteScene(id:string) {
    if(!confirm("Delete this scene and its media references?")) return;
    await action(async () => {await api.deleteScene(id); setStates(prev => {const next={...prev}; delete next[id]; return next;});setHistory([]);setFuture([]); await refresh();});
  }
  async function saveTitle() {
    if(!project) return;
    if(titleDraft===project.title) {setStates(prev=>({...prev,title:"Saved"})); return;}
    const title=titleDraft.trim()||"Untitled documentary";
    const ok=await action(async () => {await api.updateProject(project.id,{title}); await refresh();});
    if(ok) setTitleDraft(title);
    setStates(prev=>({...prev,title:ok?"Saved":"Save failed"}));
  }
  if(!project) return <main className="project-home"><BuildNotice/>
    <div className="brand"><span className="brand-mark"><Film size={22}/></span> SceneForge <span className="version-chip">STUDIO</span></div>
    <section className="home-intro"><span className="eyebrow">YOUR STORY, FRAME BY FRAME</span><h1>Make room for<br/>your next story.</h1><p>Turn scripts, images, and narration into a video.<br/>One scene at a time.</p></section>
    {error && <div role="alert" className="error-box">{error}</div>}
    <section className="new-project"><div><h2>Create a project</h2><p className="hint">Start with three scenes. Add more as your story grows.</p></div><div className="create-form"><label className="control-label">Project name<input aria-label="New project name" value={newTitle} onChange={e=>setNewTitle(e.target.value)}/></label><label className="control-label">Format<select aria-label="New project aspect ratio" value={newAspect} onChange={e=>setNewAspect(e.target.value)}>{ASPECTS.map(a=><option key={a}>{a}</option>)}</select></label><button className="btn btn-primary" disabled={busy} onClick={createProject}><Plus size={16}/> Create project</button></div></section>
    <div className="section-heading"><h2>Your projects</h2><span className="subtle">{projects.length} projects</span></div>
    <label className="search-control"><Search size={16}/><input aria-label="Search projects" placeholder="Find a project…" value={projectSearch} onChange={e=>setProjectSearch(e.target.value)}/></label>
    {loading ? <p role="status">Loading projects…</p> : <div className="project-grid">{projects.filter(p=>p.title.toLowerCase().includes(projectSearch.toLowerCase())).map(p=><article className="project-tile" key={p.id}><button className="project-open-button" disabled={busy} onClick={()=>openProject(p.id)}><div className="project-cover"><Film size={30}/><span>{p.aspect}</span></div><strong>{p.title}</strong><span className="project-open">Open project <ArrowRight size={15}/></span></button><button className="text-btn project-delete" aria-label={`Delete project ${p.title}`} disabled={busy} onClick={()=>removeProject(p)}><Trash2 size={14}/> Delete</button></article>)}{!projects.filter(p=>p.title.toLowerCase().includes(projectSearch.toLowerCase())).length&&<p className="hint">{projects.length?"No matching projects.":"Your saved projects will appear here."}</p>}</div>}
  </main>;
  return <div className="studio-shell"><BuildNotice/>
    <header className="studio-toolbar">
      <button className="brand brand-button" title="Back to projects" disabled={dirty||busy||exporting} onClick={()=>action(async()=>{setProjects(await api.listProjects()); projectRef.current=null; setProject(null);})}><span className="brand-mark"><Film size={19}/></span><span>SceneForge</span></button>
      <span className="toolbar-divider"/>
      <div className="project-identity"><input aria-label="Project name" value={titleDraft} onChange={e=>{setTitleDraft(e.target.value); setStates(prev=>({...prev,title:"Unsaved changes"}));}} onBlur={()=>void saveTitle()}/><span role="status" className={`save-status ${failed ? "save-error" : ""}`}>{busy ? "Saving…" : status}</span></div>
      <div className="toolbar-end"><select aria-label="Project aspect ratio" value={project.aspect} disabled={busy||dirty||exporting} onChange={e=>action(async()=>{await api.updateProject(project.id,{aspect:e.target.value}); await refresh();})}>{ASPECTS.map(a=><option key={a}>{a}</option>)}</select><button className="icon-btn" title="Provider settings" aria-label="Provider settings" onClick={()=>setSettingsOpen(true)}><Settings size={18}/></button><button className="btn btn-primary" disabled={exporting||dirty||busy||!project.scenes.length} onClick={()=>void renderFullVideo()}><Upload size={15}/>{exporting ? `Exporting ${Math.round(exportJob?.progress||0)}%` : "Export video"}</button></div>
    </header>
    {titleCard&&<TitleDesigner width={project.width} height={project.height} busy={busy} onClose={()=>setTitleCard(false)} onCreate={d=>void addTitleCard(d)}/>}
    {(error||exportJob?.status==="failed")&&<div role="alert" className="error-box"><details><summary>Operation failed — show details</summary><pre>{error||exportJob?.error}</pre></details><button className="text-btn" onClick={()=>{setError(null);if(exportJob?.status==='failed')setExportJobId(null);}}>Dismiss</button></div>}
    <div className="editor-menubar">
      {['File','Edit','View'].map(name=><div className="editor-menu" key={name}><button aria-expanded={menu===name} onClick={()=>setMenu(menu===name?'':name)}>{name}</button>{menu===name&&<div className="editor-menu-items">
       {name==='File'&&<><button disabled={dirty||busy||exporting} onClick={()=>{setMenu('');void action(async()=>{setProjects(await api.listProjects());projectRef.current=null;setProject(null);});}}>New / open project…</button><button disabled={busy||exporting} onClick={()=>{setMenu('');void addPart();}}>New scene</button><button disabled={busy||exporting} onClick={()=>importRef.current?.click()}>Import files to Media Pool…</button><button disabled={busy||exporting} onClick={()=>folderRef.current?.click()}>Import folder to Media Pool…</button><button disabled={!selected||busy||exporting} onClick={()=>audioImportRef.current?.click()}>Import audio to selected scene…</button><button onClick={()=>{setMenu('');setSettingsOpen(true);}}>Provider settings…</button></>}
       {name==='Edit'&&<><button disabled={!history.length||busy||dirty||exporting} onClick={()=>{setMenu('');void undoTimeline();}}>Undo {history[history.length-1]?.label||'timeline edit'}</button><button disabled={!future.length||busy||dirty||exporting} onClick={()=>{setMenu('');void redoTimeline();}}>Redo {future[future.length-1]?.label||'timeline edit'}</button><button disabled={!selected||busy||exporting} onClick={()=>{setMenu('');if(selected)void deleteScene(selected.id);}}>Delete selected scene…</button></>}
       {name==='View'&&<><button onClick={()=>{setSidebar(!sidebar);setMenu('');}}>Toggle scene library</button><button onClick={()=>{document.querySelector('.studio-shell')?.classList.toggle('inspector-hidden');setMenu('');}}>Toggle inspector</button><button onClick={()=>{setExportPanel(!exportPanel);setMenu('');}}>Show / hide export result</button><button onClick={()=>{setMenu('');if(document.fullscreenElement)void document.exitFullscreen();else void document.documentElement.requestFullscreen();}}>Fullscreen / restore</button></>}
      </div>}</div>)}<span className="menu-help">Import audio into A1 · Scissors: choose a cut position · Render complex scenes before cutting</span>
    </div>
    <input hidden ref={importRef} type="file" accept="image/*,video/*,audio/*" multiple onChange={e=>{void importMedia(e.target.files);e.target.value='';}}/>
    <input hidden ref={folderRef} type="file" multiple {...{webkitdirectory:''} as any} onChange={e=>{void importMedia(e.target.files);e.target.value='';}}/>
    <input hidden ref={audioImportRef} type="file" accept="audio/*" onChange={e=>{void importAudio(e.target.files?.[0]);e.target.value='';}}/>
    {exportPanel&&exportJob?.status==='succeeded'&&exportJob.artifact_asset_id&&<section className="export-result" aria-label="Export result"><header><CheckCircle2 size={16}/><span>Last export ready · Export again after edits</span><a href={api.assetDownloadUrl(exportJob.artifact_asset_id)} download>Download MP4</a><button aria-label={exportExpanded?'Minimize export result':'Expand export result'} onClick={()=>setExportExpanded(!exportExpanded)}>{exportExpanded?'−':'+'}</button><button aria-label="Close export result" onClick={()=>setExportPanel(false)}><X size={14}/></button></header>{exportExpanded&&<video controls src={api.assetStreamUrl(exportJob.artifact_asset_id)}/>}</section>}
    <div className={`workspace ${sidebar ? "" : "sidebar-collapsed"}`}>
      <nav className="scene-sidebar" aria-label="Scenes"><div className="sidebar-header"><h2><Layers size={16}/> Scenes <span className="count-badge">{project.scenes.length}</span></h2><button className="icon-btn" aria-label={sidebar?"Collapse scene list":"Expand scene list"} title={sidebar?"Collapse scene list":"Expand scene list"} onClick={()=>setSidebar(!sidebar)}>{sidebar?<PanelLeftClose size={16}/>:<PanelLeftOpen size={16}/>}</button></div>
      {sidebar&&<><div className="library-tabs" aria-label="Asset library">{(['Scenes','Media Pool','Effects','Transitions'] as const).map(t=><button key={t} aria-pressed={libraryTab===t} onClick={()=>setLibraryTab(t)}>{t}</button>)}</div>
      <div className="library-content">
      {libraryTab==='Media Pool'&&<>{importStatus&&<p className="hint" aria-live="polite">{importStatus}</p>}<MediaPool projectId={project.id} version={mediaVersion} disabled={busy||dirty||exporting} onImport={()=>importRef.current?.click()} onFolder={()=>folderRef.current?.click()} onAdd={addPoolAssets} onUse={usePoolAsset} canUse={!!selected}/></>}

      {libraryTab==='Scenes'&&<><p className="sidebar-hint">PROJECT BIN · Select a part to edit</p><div className="scene-list">{project.scenes.map((s,i)=><button key={s.id} className={`scene-nav ${selected?.id===s.id?"selected":""}`} aria-label={`Select scene ${i+1}: ${s.title}`} aria-current={selected?.id===s.id?"true":undefined} onClick={()=>setSelectedId(s.id)}><div className="scene-thumb">{s.shots[0]?.asset?.type==="image"?<img src={api.assetStreamUrl(s.shots[0].asset_id)} alt=""/>:<Film size={22}/>}<span>{String(i+1).padStart(2,"0")}</span></div><div className="scene-nav-meta"><strong>{s.title}</strong><span>{durationLabel(s)} · {s.shots.length} media</span></div></button>)}</div><button className="btn add-scene" disabled={busy||dirty||exporting} onClick={()=>setTitleCard(true)}><Type size={16}/> Add title card</button><button className="btn add-scene" disabled={busy} onClick={addPart}><Plus size={16}/> Add scene</button></>}
      {libraryTab==='Effects'&&<><p className="sidebar-hint">APPLY TO · {selected?.title||'Select a part'}</p><div className="library-presets">{EFFECTS.map(fx=><button key={fx.key} aria-pressed={selected?.effect_preset===fx.key} disabled={!selected?.shots.length||busy||dirty||exporting} onClick={()=>selected&&action(async()=>{await api.updateScene(selected.id,{effect_preset:fx.key});await refresh();})}><div className="preset-sample" style={{filter:fx.swatch}}>{selected?.shots[0]?.asset?.type==='image'?<img src={api.assetStreamUrl(selected.shots[0].asset_id)} alt=""/>:<Palette size={24}/>}</div><span>{fx.label}</span></button>)}</div></>}
      {libraryTab==='Transitions'&&<><p className="sidebar-hint">INCOMING TO · {selected?.title||'Select a part'}</p><div className="library-presets transition-presets">{TRANSITIONS.map(([key,label])=><button key={key} aria-pressed={selected?.transition_in_json.type===key} disabled={!selected?.shots.length||selected.id===project.scenes.find(s=>s.shots.length)?.id||busy||dirty||exporting} onClick={()=>selected&&record('transition',()=>api.updateScene(selected.id,{transition_in:selected.transition_in_json}),()=>api.updateScene(selected.id,{transition_in:{type:key,duration_ms:key==='cut'?0:(selected.transition_in_json.duration_ms||500)}}))}><div aria-hidden="true" className={`transition-sample sample-${key}`}><span>A</span><span>B</span></div><span>{label}</span></button>)}</div><p className="hint">Select the incoming part, then a transition. Adjust its duration above the tracks.</p></>}
      </div><div className="sidebar-bottom"><span className="status-dot"/> Local workspace<span>Workspace 2.5 · Scene editor</span></div></>}
      </nav>
      <main className="editing-area">
        {project.scenes.map((scene,i)=><PartRow key={`${scene.id}-${editorEpoch}`} scene={scene} project={project} index={i} total={project.scenes.length} active={selected?.id===scene.id} refresh={refresh} onMove={dir=>moveScene(scene.id,dir)} onDelete={()=>deleteScene(scene.id)} onOpenSettings={()=>setSettingsOpen(true)} onSaveState={(id,state)=>setStates(prev=>({...prev,[id]:state}))}/>)}
        {!project.scenes.length&&<div className="empty-project"><Film size={40}/><h2>Your story starts here</h2><button className="btn btn-primary" disabled={busy} onClick={addPart}><Plus size={16}/> Add your first scene</button></div>}
        <div id="sequence-viewer"/>
      </main>
    </div>
    <ProjectTimeline onDuration={resizeDuration} onRender={()=>void renderFullVideo()} exportScenes={exportScenes} exportAsset={exportJob?.status==="succeeded"?exportJob.artifact_asset_id:null} project={project} selectedId={selected?.id||""} disabled={busy||dirty||exporting} onSelect={setSelectedId} onAdd={addPart} onReorder={ids=>record('scene order',()=>api.reorderScenes(project.id,project.scenes.map(s=>s.id)),()=>api.reorderScenes(project.id,ids))} onUpdate={(id,patch)=>record('transition',()=>api.updateScene(id,{transition_in:project.scenes.find(s=>s.id===id)!.transition_in_json}),()=>api.updateScene(id,patch))} onDelete={()=>selected&&void deleteScene(selected.id)} onAudio={()=>audioImportRef.current?.click()} onRemoveAudio={()=>selected&&void action(async()=>{await api.clearNarration(selected.id);await refresh();})} onUndo={undoTimeline} onRedo={redoTimeline} canUndo={!!history.length} canRedo={!!future.length} onSplit={(at,baked)=>selected&&void action(async()=>{const right=await api.splitScene(selected.id,at,baked);setEditorEpoch(v=>v+1);setHistory([]);setFuture([]);await refresh();setSelectedId(right.id);})}/>
    {settingsOpen&&<SettingsPanel onClose={()=>setSettingsOpen(false)}/>}
  </div>;
}
