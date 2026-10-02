import React, {useCallback, useEffect, useLayoutEffect, useRef, useState} from 'react';
import {Clipboard, Cpu, Download, FolderOpen, Keyboard, RefreshCw, Trash2} from 'lucide-react';
import {Modal} from './InfoPanels';
import {askConfirm} from './dialogs';
import {api, ManagedModel, ModelListing} from './api';
import {TOOL_KEYS, TOOL_LABELS} from './timeline/timeline.types';

// ------------------------------------------------------------------ keyboard shortcut sheet
type Shortcut = {keys: string[]; action: string};
/** Every shortcut here has a real handler: ProjectTimeline's editor shortcuts (playback,
 *  tools, edit), App's Ctrl+N / Ctrl+O and "?" handlers, the preview's Ctrl+wheel zoom and
 *  Space-drag pan, the inspector tab bar's arrow keys, and the desktop app's menu accelerators. */
const TOOL_ROWS: Shortcut[] = Object.entries(TOOL_KEYS).map(([key, tool]) => ({keys: [key.toUpperCase()], action: `${TOOL_LABELS[tool][0]} tool`}));
export const SHORTCUT_GROUPS: {title: string; note?: string; items: Shortcut[]}[] = [
  {title: 'Playback', items: [
    {keys: ['Space'], action: 'Play or pause the timeline live from the scene renders (Preview last export plays the exported movie)'},
    {keys: ['J', 'K', 'L'], action: 'Timeline playback: back 5 s, pause, play (press L again for 2× and 4×)'},
    {keys: ['←', '→'], action: 'Previous / next frame'},
    {keys: ['Shift+←', 'Shift+→'], action: 'Previous / next scene'},
    {keys: ['Home', 'End'], action: 'Go to the timeline start / end'},
    {keys: ['Ctrl+wheel'], action: 'Zoom the timeline (over the tracks) or the preview (over the picture)'},
    {keys: ['Space+drag'], action: 'Pan a zoomed-in preview (middle-button drag also works)'},
  ]},
  {title: 'Timeline tools', note: 'Tools act on timeline audio clips (A3–A8).', items: [
    ...TOOL_ROWS,
    {keys: ['Shift+C'], action: 'Razor All: cut every unlocked timeline audio track at the playhead'},
  ]},
  {title: 'Edit', items: [
    {keys: ['Ctrl+Z'], action: 'Undo timeline edit'},
    {keys: ['Ctrl+Shift+Z', 'Ctrl+Y'], action: 'Redo timeline edit'},
    {keys: ['Ctrl+C'], action: 'Copy the selected scene, focused narration, or selected timeline audio clips'},
    {keys: ['Ctrl+X'], action: 'Cut the selected timeline audio clips'},
    {keys: ['Ctrl+V'], action: 'Paste (scene, narration audio, or audio clips at the playhead)'},
    {keys: ['Ctrl+D'], action: 'Duplicate the selected scene or timeline audio clips'},
    {keys: ['Ctrl+G'], action: 'Group the selected timeline audio clips'},
    {keys: ['Ctrl+Shift+G'], action: 'Ungroup'},
    {keys: ['Delete'], action: 'Delete focused audio clips or narration; ripple-delete the selected scene'},
    {keys: ['Shift+Delete'], action: 'Ripple-delete the selected timeline audio clips'},
  ]},
  {title: 'Projects and app', items: [
    {keys: ['Ctrl+N'], action: 'New project'},
    {keys: ['Ctrl+O'], action: 'Open project'},
    {keys: ['Ctrl+,'], action: 'Preferences (desktop app menu)'},
    {keys: ['Ctrl+Shift+A'], action: 'AI engines & providers (desktop app menu)'},
    {keys: ['?'], action: 'Show this list of shortcuts'},
    {keys: ['Esc'], action: 'Close a dialog or menu'},
    {keys: ['←', '→', 'Home', 'End'], action: 'Move between Scene settings tabs (when a tab has focus)'},
  ]},
];

export function ShortcutSheet({onClose}: {onClose: () => void}) {
  return <Modal title="Keyboard shortcuts" icon={<Keyboard size={18}/>} onClose={onClose} wide>
    <p className="info-lead">Shortcuts work while you are not typing in a text field. On macOS, use ⌘ instead of Ctrl.</p>
    <div className="shortcut-groups">{SHORTCUT_GROUPS.map(g => <section key={g.title} className="shortcut-group" aria-label={g.title}>
      <h3>{g.title}</h3>{g.note && <p className="hint">{g.note}</p>}
      <dl>{g.items.map(item => <div key={item.keys.join() + item.action} className="shortcut-row">
        <dt>{item.keys.map((k, i) => <React.Fragment key={k}>{i > 0 && <span className="kbd-sep">/</span>}<kbd>{k}</kbd></React.Fragment>)}</dt>
        <dd>{item.action}</dd></div>)}</dl>
    </section>)}</div>
  </Modal>;
}

// ------------------------------------------------------------------ AI model manager
export const formatBytes = (n: number) => n >= 1e9 ? `${(n / 1e9).toFixed(2)} GB` : n >= 1e6 ? `${(n / 1e6).toFixed(1)} MB` : n >= 1e3 ? `${Math.round(n / 1e3)} KB` : `${n} B`;
const KIND_LABEL: Record<ManagedModel['kind'], string> = {whisper: 'Captions (speech to text)', cutout: 'Background removal', voice: 'Voice isolation'};

export function ModelManager({onClose}: {onClose: () => void}) {
  const [data, setData] = useState<ModelListing | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState('');
  const [copied, setCopied] = useState('');
  const desktop = (window as any).sceneforgeDesktop;
  const load = useCallback(async () => {
    try {setData(await api.listModels()); setError('');} catch (e: any) {setError(e?.message || String(e));}
  }, []);
  useEffect(() => {void load();}, [load]);
  const downloading = !!data?.models.some(m => m.download?.status === 'running');
  useEffect(() => {if (!downloading) return; const t = setInterval(() => void load(), 1000); return () => clearInterval(t);}, [downloading, load]);
  async function remove(m: ManagedModel) {
    if (!(await askConfirm(`Delete ${m.name} (${formatBytes(m.bytes)})? It downloads again the next time ${KIND_LABEL[m.kind].toLowerCase()} needs it.`))) return;
    setBusy(m.kind + m.id); setMessage('');
    try {const r = await api.deleteModel(m.kind, m.id); setMessage(r.message);} catch (e: any) {setError(e?.message || String(e));}
    finally {setBusy(''); void load();}
  }
  async function download(m: ManagedModel) {
    setBusy(m.kind + m.id); setMessage('');
    try {const r = await api.downloadModel(m.kind, m.id); if (r.message) setMessage(r.message);} catch (e: any) {setError(e?.message || String(e));}
    finally {setBusy(''); void load();}
  }
  async function copy(path: string) {
    try {await navigator.clipboard?.writeText(path); setCopied(path); setTimeout(() => setCopied(''), 2000);} catch {setError('Copying is not available here. Select the folder path and copy it.');}
  }
  return <Modal title="AI models" icon={<Cpu size={18}/>} onClose={onClose} wide>
    <p className="info-lead">Local models SceneForge downloads on first use. Delete one to free disk space; it downloads again when a feature needs it. Bundled models ship with the app and cannot be deleted.</p>
    <div className="model-summary" role="status" aria-live="polite">
      {data ? <>Total disk used: <strong>{formatBytes(data.total_bytes)}</strong>{data.total_bytes !== data.downloaded_bytes && <> · downloaded (removable): {formatBytes(data.downloaded_bytes)}</>}</> : !error && 'Loading models…'}
      <button className="text-btn" onClick={() => void load()} aria-label="Refresh model list"><RefreshCw size={13}/> Refresh</button>
    </div>
    {error && <p role="alert" className="error-box">{error}</p>}
    {message && <p className="hint">{message}</p>}
    {data && <ul className="model-list" aria-label="AI models">{data.models.map(m => {
      const dl = m.download, running = dl?.status === 'running', pct = running && dl!.total ? Math.min(100, Math.round(dl!.done / dl!.total * 100)) : 0;
      return <li key={m.kind + m.id} className="model-row" aria-label={m.name}>
        <div className="model-main">
          <strong>{m.name}</strong><span className="model-kind">{KIND_LABEL[m.kind]}</span>
          <p className="hint">{m.purpose}</p>
          <span className="model-folder" title={m.folder}><code>{m.folder}</code></span>
          {dl?.status === 'error' && <p role="alert" className="model-error">{dl.error}</p>}
        </div>
        <div className="model-state">
          <span className={`info-badge ${m.downloaded ? 'ok' : 'off'}`}>{running ? `Downloading ${pct}%` : m.bundled ? 'Bundled' : m.downloaded ? 'Downloaded' : 'Not downloaded'}</span>
          <span className="model-size">{m.downloaded || m.bytes ? formatBytes(m.bytes) : `≈ ${m.approx_mb} MB`}</span>
          {running && <progress max={100} value={pct} aria-label={`${m.name} download progress`}/>}
        </div>
        <div className="model-actions">
          {!m.downloaded && <button className="btn" disabled={running || busy === m.kind + m.id} onClick={() => void download(m)} aria-label={`Download ${m.name}`}><Download size={13}/> Download</button>}
          {m.downloaded && !m.bundled && <button className="btn" disabled={m.in_use || running || busy === m.kind + m.id} title={m.in_use ? 'In use by a running job' : 'Delete the downloaded files'} onClick={() => void remove(m)} aria-label={`Delete ${m.name}`}><Trash2 size={13}/> Delete</button>}
          {desktop?.openModelFolder
            ? <button className="btn" onClick={() => void desktop.openModelFolder(m.kind, m.id).catch((e: any) => setError(e?.message || String(e)))} aria-label={`Open folder for ${m.name}`}><FolderOpen size={13}/> Open folder</button>
            : <button className="btn" onClick={() => void copy(m.folder)} aria-label={`Copy folder path for ${m.name}`}><Clipboard size={13}/> {copied === m.folder ? 'Copied' : 'Copy path'}</button>}
        </div>
      </li>;})}</ul>}
  </Modal>;
}

// ------------------------------------------------------------------ first-run tour
export const TOUR_KEY = 'sceneforge.tour.v1';
export const tourSeen = () => {try {return localStorage.getItem(TOUR_KEY) === 'done';} catch {return true;}};
const markTourSeen = () => {try {localStorage.setItem(TOUR_KEY, 'done');} catch {/* storage unavailable */}};
const TOUR_STEPS = [
  {target: 'nav.scene-sidebar', title: 'Scenes bin', text: 'Every scene in your project lives here. Select one to edit it. Media Pool holds your imported files, Transitions sets how scenes change.'},
  {target: '.scene-editor:not([hidden]) .preview-card', title: 'Preview', text: 'See the selected scene. Switch between the source media and the last render, zoom with Ctrl + mouse wheel, and drag overlays into place.'},
  {target: '.scene-editor:not([hidden]) .inspector-tabbar', title: 'Scene settings', text: 'These tabs hold the controls for the selected scene: media, motion, effects, overlays, text and audio. When the panel is narrow, extra tabs appear under More.'},
  {target: '.timeline-tools', title: 'Timeline tools', text: 'Edit tools for timeline audio clips: V select, A track select, B ripple, N roll, Y slip, U slide, C blade. Press ? at any time for every shortcut.'},
  {target: '.export-launch', title: 'Export', text: 'When the story is ready, export the full video. You can preview, download and share the result afterwards.'},
];

export function FirstRunTour({onClose}: {onClose: () => void}) {
  const [step, setStep] = useState(0);
  const [rect, setRect] = useState<{top: number; left: number; width: number; height: number} | null>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const finish = useCallback(() => {markTourSeen(); onClose();}, [onClose]);
  const s = TOUR_STEPS[step];
  const place = useCallback(() => {
    const el = document.querySelector<HTMLElement>(s.target);
    const r = el?.getBoundingClientRect();
    setRect(r && (r.width || r.height) ? {top: r.top, left: r.left, width: r.width, height: r.height} : null);
  }, [s.target]);
  useLayoutEffect(() => {place();}, [place]);
  useEffect(() => {window.addEventListener('resize', place); return () => window.removeEventListener('resize', place);}, [place]);
  useEffect(() => {cardRef.current?.querySelector<HTMLElement>('.tour-next')?.focus();}, [step]);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const key = (e: KeyboardEvent) => {
      const card = cardRef.current;
      if (!card) return;
      if (e.key === 'Escape') {e.preventDefault(); e.stopPropagation(); finish(); return;}
      if (e.key === 'Tab') {
        const controls = Array.from(card.querySelectorAll<HTMLElement>('button:not(:disabled)'));
        const first = controls[0], last = controls[controls.length - 1];
        if (!card.contains(document.activeElement)) {e.preventDefault(); first?.focus();}
        else if (e.shiftKey && document.activeElement === first) {e.preventDefault(); last.focus();}
        else if (!e.shiftKey && document.activeElement === last) {e.preventDefault(); first.focus();}
      }
    };
    document.addEventListener('keydown', key, true);
    return () => {document.removeEventListener('keydown', key, true); previous?.focus?.();};
  }, [finish]);
  const vw = window.innerWidth, vh = window.innerHeight, cardW = Math.min(340, vw - 24);
  const below = rect ? rect.top + rect.height + 12 : 0;
  const cardStyle: React.CSSProperties = rect
    ? {width: cardW, left: Math.max(12, Math.min(vw - cardW - 12, rect.left + rect.width / 2 - cardW / 2)),
       ...(below + 190 < vh ? {top: below} : {bottom: Math.max(12, vh - rect.top + 12)})}
    : {width: cardW, left: Math.max(12, vw / 2 - cardW / 2), top: Math.max(12, vh / 3)};
  return <div className="tour-overlay">
    {rect ? <div className="tour-spot" aria-hidden="true" style={{top: rect.top - 4, left: rect.left - 4, width: rect.width + 8, height: rect.height + 8}}/> : <div className="tour-dim" aria-hidden="true"/>}
    <div ref={cardRef} className="tour-card" role="dialog" aria-modal="true" aria-labelledby="tour-title" aria-describedby="tour-text" style={cardStyle}>
      <span className="tour-count">Step {step + 1} of {TOUR_STEPS.length}</span>
      <h2 id="tour-title">{s.title}</h2>
      <p id="tour-text">{s.text}</p>
      <div className="tour-dots" aria-hidden="true">{TOUR_STEPS.map((_, i) => <i key={i} className={i === step ? 'on' : ''}/>)}</div>
      <footer>
        <button className="text-btn tour-skip" onClick={finish}>Skip tour</button>
        <span/>
        <button className="btn" disabled={step === 0} onClick={() => setStep(step - 1)}>Back</button>
        <button className="btn btn-primary tour-next" onClick={() => step === TOUR_STEPS.length - 1 ? finish() : setStep(step + 1)}>{step === TOUR_STEPS.length - 1 ? 'Finish' : 'Next'}</button>
      </footer>
    </div>
  </div>;
}
