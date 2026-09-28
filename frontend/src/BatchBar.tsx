import React, {useEffect, useState} from 'react';
import {Layers, X, Sparkles, Check} from 'lucide-react';
import {api, type Scene} from './api';

const PARTS: [string, string][] = [['effects', 'Look & effects'], ['captions', 'Caption style'], ['titles', 'Text overlays'], ['transition', 'Transition']];

/** Several parts selected on the timeline (Ctrl/Shift-click): copy the current scene's
 *  settings to all of them, or make captions from speech for all of them. */
export function BatchBar({source, scenes, onClear, onDone}: {source: Scene; scenes: Scene[]; onClear: () => void; onDone: () => void}) {
  const [parts, setParts] = useState<string[]>(['effects', 'captions']);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [collapsed, setCollapsed] = useState(false);
  const clearRef = React.useRef(onClear);
  useEffect(() => {clearRef.current = onClear;}, [onClear]);
  useEffect(() => {if (!msg || busy) return; const timer = window.setTimeout(() => clearRef.current(), 3500); return () => window.clearTimeout(timer);}, [msg, busy]);
  const targets = scenes.filter(s => s.id !== source.id);
  async function apply() {
    setBusy(true); setMsg('');
    try {const r = await api.applyToScenes(source.id, targets.map(t => t.id), parts); setMsg(`Applied to ${r.changed} part${r.changed === 1 ? '' : 's'}.`); onDone();}
    catch (e: any) {setMsg(e.message || String(e));} finally {setBusy(false);}
  }
  async function captionsForAll() {
    setBusy(true); let ok = 0; const failed: string[] = [];
    for (const [i, s] of scenes.entries()) {
      setMsg(`Captions from speech: ${i + 1} of ${scenes.length} (“${s.title}”)…`);
      try {await api.autoCaptions(s.id, {}); ok++;} catch {failed.push(s.title);}
    }
    setMsg(`Captions made for ${ok} of ${scenes.length} parts.${failed.length ? ` No speech found in: ${failed.join(', ')}.` : ''}`);
    setBusy(false); onDone();
  }
  return <div className={`batch-bar ${collapsed?'collapsed':''}`} role="region" aria-label="Selected parts">
    <span className="bb-count"><Layers size={15}/> {scenes.length} parts selected</span>
    <button className="icon-reset" aria-label={collapsed?'Expand batch actions':'Minimize batch actions'} title={collapsed?'Expand':'Minimize'} onClick={()=>setCollapsed(v=>!v)}>{collapsed?'＋':'−'}</button>
    {!collapsed && <>
    <span className="bb-from">Copy from <b>{source.title}</b>:</span>
    <div className="bb-parts" role="group" aria-label="What to copy">
      {PARTS.map(([k, l]) => <label key={k} className={`bb-chip ${parts.includes(k) ? 'on' : ''}`}><input type="checkbox" checked={parts.includes(k)} onChange={e => setParts(p => e.target.checked ? [...p, k] : p.filter(x => x !== k))}/>{parts.includes(k) && <Check size={11}/>}{l}</label>)}
    </div>
    <button className="btn btn-primary" disabled={busy || !parts.length || !targets.length} onClick={() => void apply()}>Apply to {targets.length} other part{targets.length === 1 ? '' : 's'}</button>
    <button className="btn" disabled={busy} onClick={() => void captionsForAll()}><Sparkles size={13}/> Captions from speech for all</button>
    {msg && <span className="bb-msg" aria-live="polite">{msg}</span>}
    </>}
    <button className="icon-reset" aria-label="Clear selection" title="Clear selection" onClick={onClear}><X size={15}/></button>
  </div>;
}
