import React, {useEffect, useRef, useState} from 'react';
import {X, Sparkles, Cloud, Cpu, Mic, CheckCircle2, AlertCircle, ExternalLink, FolderOpen, Play, RefreshCw, Code2, Bug, FileText, LifeBuoy} from 'lucide-react';
import {api, ProviderProfile} from './api';

type Desktop = {
  info(): Promise<{version: string; electron: string; chrome: string; platform: string; arch: string; packaged: boolean; beta: boolean; workspace: string}>;
  checkForUpdates(): Promise<{status: string; version?: string; message: string}>;
  setBeta(on: boolean): Promise<{beta: boolean; message: string}>;
  chooseSdFolder(): Promise<string | null>;
  openExternal(url: string): Promise<boolean>;
  openLogs(): Promise<unknown>;
  collectDiagnostics(): Promise<boolean>;
};
const desktop = (): Desktop | undefined => (window as any).sceneforgeDesktop;
const REPO = 'https://github.com/EzioDEVio/SceneForge';
const openLink = (url: string) => desktop() ? desktop()!.openExternal(url) : window.open(url, '_blank', 'noopener');
const CLOUD: {name: string; match: RegExp; what: string; url: string}[] = [
  {name: 'ElevenLabs', match: /elevenlabs/i, what: 'Natural voices in many languages, with exact word timing for captions.', url: 'https://elevenlabs.io'},
  {name: 'OpenAI', match: /openai/i, what: 'Image generation.', url: 'https://platform.openai.com/api-keys'},
  {name: 'Google Gemini', match: /gemini/i, what: 'Image generation.', url: 'https://aistudio.google.com/app/apikey'},
  {name: 'Together AI', match: /together/i, what: 'Voices.', url: 'https://api.together.ai'},
  {name: 'Cloudflare Workers AI', match: /cloudflare/i, what: 'Image generation with a free daily allowance.', url: 'https://dash.cloudflare.com'},
  {name: 'Hugging Face', match: /hugging/i, what: 'Image generation with free models.', url: 'https://huggingface.co/settings/tokens'},
];

function Modal({title, icon, onClose, children, wide}: {title: string; icon: React.ReactNode; onClose: () => void; children: React.ReactNode; wide?: boolean}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {ref.current?.focus(); const esc = (e: KeyboardEvent) => e.key === 'Escape' && onClose(); window.addEventListener('keydown', esc); return () => window.removeEventListener('keydown', esc);}, [onClose]);
  return <div className="info-backdrop" onMouseDown={e => e.target === e.currentTarget && onClose()}>
    <div ref={ref} tabIndex={-1} className={`info-panel ${wide ? 'wide' : ''}`} role="dialog" aria-modal="true" aria-label={title}>
      <header><span className="info-title">{icon}{title}</span><button className="icon-reset info-close" aria-label="Close" onClick={onClose}><X size={16}/></button></header>
      <div className="info-body">{children}</div>
    </div>
  </div>;
}
const Steps = ({items}: {items: React.ReactNode[]}) => <ol className="info-steps">{items.map((it, i) => <li key={i}><span className="step-no">{i + 1}</span><div>{it}</div></li>)}</ol>;
const Badge = ({ok, children}: {ok: boolean; children: React.ReactNode}) => <span className={`info-badge ${ok ? 'ok' : 'off'}`}>{ok ? <CheckCircle2 size={12}/> : <AlertCircle size={12}/>}{children}</span>;

export function AIEnginesPanel({section, onClose, onOpenSettings}: {section?: string; onClose: () => void; onOpenSettings: () => void}) {
  const [providers, setProviders] = useState<ProviderProfile[] | null>(null);
  const [sd, setSd] = useState<{folder?: string; autostart?: boolean} | null>(null);
  const [sdState, setSdState] = useState('');
  const [busy, setBusy] = useState(false);
  const refs = {start: useRef<HTMLElement>(null), cloud: useRef<HTMLElement>(null), sd: useRef<HTMLElement>(null), voices: useRef<HTMLElement>(null)};
  useEffect(() => {
    api.listProviders().then(setProviders).catch(() => setProviders([]));
    fetch('/api/local-image-settings').then(r => r.json()).then(setSd).catch(() => setSd({}));
  }, []);
  useEffect(() => {const el = section && (refs as any)[section]?.current; if (el) setTimeout(() => el.scrollIntoView({block: 'start', behavior: 'smooth'}), 60);}, [section]);
  const configured = (p: {match: RegExp}) => (providers || []).find(x => x.configured && (p.match.test(x.name) || p.match.test(x.base_url || '')));
  async function saveSd(patch: {folder?: string; autostart?: boolean}) {
    setBusy(true); setSdState('');
    try {
      const r = await fetch('/api/local-image-settings', {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({folder: patch.folder ?? sd?.folder, autostart: patch.autostart ?? !!sd?.autostart})});
      const v = await r.json(); if (!r.ok) throw Error(v.detail || 'Could not save'); setSd(v);
    } catch (e: any) {setSdState(e.message || String(e));} finally {setBusy(false);}
  }
  async function startSd() {
    setBusy(true); setSdState('Starting… this can take a few minutes the first time.');
    try {const r = await fetch('/api/local-image-start', {method: 'POST'}); const v = await r.json(); if (!r.ok) throw Error(v.detail || 'Could not start'); setSdState(v.ready ? `Ready${v.model ? ` · model ${v.model}` : ''}` : (v.message || 'Starting… check again in a minute.'));}
    catch (e: any) {setSdState(e.message || String(e));} finally {setBusy(false);}
  }
  const count = CLOUD.filter(configured).length;
  return <Modal title="AI engines & providers" icon={<Sparkles size={18}/>} onClose={onClose} wide>
    <section ref={refs.start as any} className="info-card intro">
      <h3>Getting started with AI</h3>
      <p><strong>AI is optional.</strong> You can make a whole video from your own photos, clips and recordings. AI helps you <em>generate images</em> (Media tab → <b>Generate image</b>) and <em>narration voices</em> (Audio tab → <b>Voice & narration</b>).</p>
      <div className="info-two">
        <div className="info-choice"><Cloud size={20}/><div><b>Cloud services</b><p>Fast and high quality. Paid, or with free allowances. You need an account and an API key.</p></div></div>
        <div className="info-choice"><Cpu size={20}/><div><b>Local engines</b><p>Free and private, running on your computer. Installed separately; need a capable PC.</p></div></div>
      </div>
    </section>
    <section ref={refs.cloud as any} className="info-card">
      <div className="info-card-head"><h3><Cloud size={16}/> Cloud providers</h3><Badge ok={count > 0}>{providers === null ? 'Checking…' : `${count} connected`}</Badge></div>
      <div className="provider-grid">
        {CLOUD.map(p => {const c = configured(p); return <div key={p.name} className={`provider-card ${c ? 'connected' : ''}`}>
          <div className="provider-top"><b>{p.name}</b>{c ? <Badge ok>Connected</Badge> : <span className="info-badge off">Not set up</span>}</div>
          <p>{p.what}</p>{c && <p className="muted">Key {c.masked_key}</p>}
          <button className="text-btn" onClick={() => openLink(p.url)}><ExternalLink size={12}/> {c ? 'Account' : 'Get a key'}</button>
        </div>;})}
      </div>
      <Steps items={[<>Create an account on the provider's website and copy your <b>API key</b>.</>, <>Open <b>Settings</b> and paste the key under the provider. It is stored in your system's credential store, never in project files.</>, <>Pick the provider when generating an image or voice.</>]}/>
      <button className="btn primary" onClick={onOpenSettings}>Open Settings to add or change keys</button>
    </section>
    <section ref={refs.sd as any} className="info-card">
      <div className="info-card-head"><h3><Cpu size={16}/> Stable Diffusion: free local images</h3><Badge ok={!!sd?.folder}>{sd?.folder ? 'Folder set' : 'Not set up'}</Badge></div>
      <p>Uses <b>AUTOMATIC1111 Stable Diffusion WebUI</b> installed on this PC. Needs a graphics card with at least 4 GB of memory; starting takes a few minutes and uses a lot of memory while running.</p>
      <Steps items={[<>Install AUTOMATIC1111 and make sure it runs on its own. <button className="text-btn inline" onClick={() => openLink('https://github.com/AUTOMATIC1111/stable-diffusion-webui')}><ExternalLink size={12}/> Installation guide</button></>,
        <>In its <code>webui-user.bat</code>, add <code>--api</code> to <code>COMMANDLINE_ARGS</code>.</>,
        <>Choose its folder here, then <b>Start</b>. In a scene: Media → Generate image → pick <b>Local Stable Diffusion</b>.</>]}/>
      <div className="sd-row">
        <span className="sd-folder" title={sd?.folder || ''}>{sd?.folder || 'No folder chosen'}</span>
        <button className="btn" disabled={busy || !desktop()} title={desktop() ? '' : 'Available in the desktop app'} onClick={async () => {const f = await desktop()?.chooseSdFolder(); if (f) await saveSd({folder: f, autostart: false});}}><FolderOpen size={14}/> Choose folder</button>
        <button className="btn primary" disabled={busy || !sd?.folder} onClick={() => void startSd()}><Play size={14}/> Start now</button>
      </div>
      <label className="switch-label finishing-toggle"><input type="checkbox" checked={!!sd?.autostart} disabled={busy || !sd?.folder} onChange={e => void saveSd({autostart: e.target.checked})}/> Start automatically with SceneForge <span className="muted">(makes SceneForge slower to open)</span></label>
      {sdState && <p className="info-status" role="status">{sdState}</p>}
    </section>
    <section ref={refs.voices as any} className="info-card">
      <div className="info-card-head"><h3><Mic size={16}/> Local voices: Chatterbox and Kokoro</h3></div>
      <p><b>Chatterbox</b> speaks many languages including Arabic; <b>Kokoro</b> is a fast English voice. Both are free and need no account.</p>
      <Steps items={[<>Install <b>Docker Desktop</b> and start it. <button className="text-btn inline" onClick={() => openLink('https://www.docker.com/products/docker-desktop/')}><ExternalLink size={12}/> Download</button></>,
        <>In a scene, open <b>Audio → Voice & narration</b> and click <b>Connect Chatterbox</b> or <b>Connect Kokoro</b>.</>,
        <>Pick the engine, a voice and a language, then <b>Generate</b>. The first start downloads the voice model.</>]}/>
      <p className="muted">Coming in the next version: built-in free voices (Piper) and captions (Whisper) with no Docker needed.</p>
    </section>
  </Modal>;
}

export function AboutPanel({onClose}: {onClose: () => void}) {
  const [info, setInfo] = useState<Awaited<ReturnType<Desktop['info']>> | null>(null);
  const [build, setBuild] = useState('');
  const [upd, setUpd] = useState<{status: string; message: string} | null>(null);
  const [checking, setChecking] = useState(false);
  const [betaMsg, setBetaMsg] = useState('');
  useEffect(() => {desktop()?.info().then(setInfo).catch(() => {}); api.health().then(h => setBuild(h.build || "")).catch(() => {});}, []);
  async function check() {setChecking(true); setUpd(null); try {setUpd(await desktop()!.checkForUpdates());} catch (e: any) {setUpd({status: 'error', message: e.message || String(e)});} finally {setChecking(false);}}
  return <Modal title="About SceneForge Studio" icon={<img src="/logo.png" alt="" className="about-icon-sm"/>} onClose={onClose}>
    <div className="about-hero">
      <img src="/logo.png" alt="" className="about-logo"/>
      <div><h2>SceneForge Studio</h2><p className="muted">{info?.version ? `Version ${info.version}` : 'Running from source in a browser'}{info?.beta ? ' · beta updates on' : ''}</p><p>Free, open-source editor for narrated documentary videos.</p></div>
    </div>
    {desktop() && info?.packaged && <section className="info-card">
      <div className="info-card-head"><h3><RefreshCw size={16}/> Updates</h3>{upd && <Badge ok={upd.status !== 'error'}>{upd.status === 'up-to-date' ? 'Up to date' : upd.status === 'available' ? 'Update found' : 'Could not check'}</Badge>}</div>
      <div className="button-row"><button className="btn primary" disabled={checking} onClick={() => void check()}>{checking ? 'Checking…' : 'Check for updates'}</button>
        <label className="switch-label"><input type="checkbox" checked={!!info?.beta} onChange={async e => {const r = await desktop()!.setBeta(e.target.checked); setInfo({...info!, beta: r.beta}); setBetaMsg(r.message);}}/> Receive beta updates</label></div>
      {upd && <p className="info-status" role="status">{upd.message}</p>}
      {betaMsg && <p className="info-status" role="status">{betaMsg}</p>}
    </section>}
    <section className="info-card">
      <h3>License</h3>
      <p>SceneForge Studio is free software under the <b>GNU General Public License v3.0 or later</b>: you may use, study, share and change it. It comes with <b>no warranty</b>. Bundled components (FFmpeg, Electron, Python libraries, Noto fonts) keep their own licenses.</p>
      <div className="button-row">
        <button className="text-btn" onClick={() => openLink(`${REPO}/blob/main/LICENSE`)}><FileText size={12}/> License</button>
        <button className="text-btn" onClick={() => openLink(`${REPO}/blob/main/desktop/THIRD_PARTY.md`)}><FileText size={12}/> Third-party notices</button>
      </div>
    </section>
    <section className="info-card">
      <h3>Help and feedback</h3>
      <div className="button-row">
        <button className="btn" onClick={() => openLink(REPO)}><Code2 size={14}/> GitHub</button>
        <button className="btn" onClick={() => openLink(`${REPO}/issues/new`)}><Bug size={14}/> Report a problem</button>
        {desktop() && <button className="btn" onClick={() => void desktop()!.collectDiagnostics()}><LifeBuoy size={14}/> Collect diagnostics</button>}
        {desktop() && <button className="btn" onClick={() => void desktop()!.openLogs()}><FolderOpen size={14}/> Open logs</button>}
      </div>
    </section>
    <p className="muted about-tech">{info ? `Electron ${info.electron} · Chromium ${info.chrome} · ${info.platform} ${info.arch}` : 'Running in a browser'}{build ? ` · backend ${build}` : ''}</p>
    <p className="muted about-tech">© 2026 EzioDEVio and SceneForge contributors</p>
  </Modal>;
}
