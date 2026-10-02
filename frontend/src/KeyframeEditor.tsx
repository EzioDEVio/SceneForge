import React, {useEffect, useState} from 'react';
import {Diamond, Plus, RefreshCw, Trash2, X} from 'lucide-react';
import {EASES, Ease, Keyframe, MAX_KEYFRAMES, captureKeyframe, removeKeyframe, sortKeyframes, upsertKeyframe} from './keyframes';

// Scene-local playhead, fed by the timeline's `sceneforge-seek` events (ruler scrubs, clip
// clicks, frame steps). Kept per scene so panels opened later still know where it is.
const lastSeek: Record<string, number> = {};
const listeners = new Set<() => void>();
let installed = false;
function install() {
  if (installed || typeof window === 'undefined') return;
  installed = true;
  window.addEventListener('sceneforge-seek', e => {
    const d = (e as CustomEvent).detail;
    if (d && typeof d.sceneId === 'string' && Number.isFinite(d.timeMs)) {lastSeek[d.sceneId] = Math.max(0, d.timeMs); listeners.forEach(f => f());}
  });
}
/** Playhead time inside `sceneId` (ms from the scene start). */
export function useScenePlayhead(sceneId: string) {
  install();
  const [, force] = useState(0);
  useEffect(() => {const f = () => force(n => n + 1); listeners.add(f); return () => {listeners.delete(f);};}, []);
  return lastSeek[sceneId] ?? 0;
}
/** The layer with `keyframes` set, or without the key when the list is empty. */
export function withKeyframes<T extends {keyframes?: Keyframe[] | null}>(layer: T, kfs: Keyframe[] | null): T {
  const {keyframes: _drop, ...rest} = layer as any;
  return (kfs && kfs.length ? {...rest, keyframes: kfs} : rest) as T;
}

const sec = (ms: number) => (ms / 1000).toFixed(2);
const short: Record<string, string> = {x: 'X', y: 'Y', width: 'Size', size: 'Size', rotation: 'Rot', opacity: 'Op'};

/** Compact keyframe strip for one overlay or text layer. */
export function KeyframeEditor({sceneId, label, startMs, endMs, keyframes, keys, current, onChange, disabled}: {
  sceneId: string; label: string; startMs: number; endMs: number; keyframes?: Keyframe[] | null;
  keys: readonly string[]; current: (sceneMs: number) => Record<string, number>;
  onChange: (next: Keyframe[] | null) => void; disabled?: boolean;
}) {
  const playhead = useScenePlayhead(sceneId);
  const kfs = sortKeyframes(keyframes || []);
  const span = Math.max(100, endMs - startMs);
  const local = playhead - startMs;
  const inside = local >= 0 && local <= span;
  const at = Math.max(0, Math.min(span, Math.round(local)));
  const existing = kfs.find(k => Math.abs(k.t_ms - at) <= 40);
  const set = (next: Keyframe[]) => onChange(next.length ? next : null);
  function add() {set(upsertKeyframe(kfs, captureKeyframe(current(startMs + at), keys, at, existing?.ease || 'linear')));}
  function seekTo(k: Keyframe) {window.dispatchEvent(new CustomEvent('sceneforge-seek', {detail: {sceneId, timeMs: startMs + k.t_ms}}));}
  function retime(k: Keyframe, seconds: number) {
    const t = Math.max(0, Math.min(span, Math.round(seconds * 1000)));
    if (t === k.t_ms || kfs.some(x => x !== k && x.t_ms === t)) return;
    set(sortKeyframes(kfs.map(x => x === k ? {...x, t_ms: t} : x)));
  }
  return <section className="keyframe-strip" aria-label={`${label} keyframes`}>
    <div className="keyframe-head">
      <strong><Diamond size={12}/> Keyframes</strong><span>{kfs.length}/{MAX_KEYFRAMES}</span>
      <span className="keyframe-at" aria-live="polite">Playhead {sec(Math.max(0, local))}s{inside ? '' : ' · outside this layer'}</span>
      <button className="btn" aria-label={`Add keyframe at playhead for ${label}`} title="Capture the current position, size, rotation and opacity at the timeline playhead" disabled={disabled || (!existing && kfs.length >= MAX_KEYFRAMES)} onClick={add}><Plus size={13}/> {existing ? 'Update keyframe at playhead' : 'Add keyframe at playhead'}</button>
      {kfs.length > 0 && <button className="icon-reset" aria-label={`Clear keyframes for ${label}`} title="Remove every keyframe (the layer keeps its fixed settings)" disabled={disabled} onClick={() => set([])}><X size={12}/></button>}
    </div>
    <div className="keyframe-track" role="group" aria-label={`${label} keyframe track`}>
      <span className="keyframe-playhead" aria-hidden="true" style={{left: `${Math.max(0, Math.min(100, local / span * 100))}%`, opacity: inside ? 1 : .35}}/>
      {kfs.map((k, i) => <button key={k.t_ms} className={`keyframe-diamond ${existing === k ? 'current' : ''}`} style={{left: `${Math.min(100, k.t_ms / span * 100)}%`}} aria-label={`Keyframe ${i + 1} at ${sec(k.t_ms)}s`} title={`Keyframe ${i + 1} · ${sec(k.t_ms)}s · click to move the preview there`} onClick={() => seekTo(k)}/>)}
    </div>
    {kfs.length === 0 ? <p className="hint">Move the timeline playhead inside this layer and add keyframes to animate position, size, rotation and opacity. With keyframes, dragging on the preview edits the keyframe at the playhead.</p> :
      <ol className="keyframe-list">{kfs.map((k, i) => <li key={k.t_ms}>
        <label>t<input aria-label={`Keyframe ${i + 1} time (s)`} type="number" min={0} max={span / 1000} step={0.05} defaultValue={(k.t_ms / 1000).toFixed(2)} key={k.t_ms} disabled={disabled} onBlur={e => retime(k, Number(e.target.value))} onKeyDown={e => {if (e.key === 'Enter') e.currentTarget.blur();}}/>s</label>
        <select aria-label={`Keyframe ${i + 1} easing`} value={k.ease || 'linear'} disabled={disabled} onChange={e => set(kfs.map(x => x === k ? {...x, ease: e.target.value as Ease} : x))}>{EASES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
        <small>{keys.filter(key => (k as any)[key] != null).map(key => `${short[key] || key} ${Math.round((k as any)[key])}`).join(' · ')}</small>
        <button className="icon-reset" aria-label={`Set keyframe ${i + 1} to the current values`} title="Replace this keyframe with the values shown at the playhead" disabled={disabled} onClick={() => set(upsertKeyframe(kfs, captureKeyframe(current(startMs + at), keys, k.t_ms, k.ease || 'linear'), 0))}><RefreshCw size={11}/></button>
        <button className="icon-reset" aria-label={`Delete keyframe ${i + 1}`} disabled={disabled} onClick={() => set(removeKeyframe(kfs, k.t_ms))}><Trash2 size={11}/></button>
      </li>)}</ol>}
  </section>;
}
