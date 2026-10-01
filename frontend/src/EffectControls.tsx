import React, {useEffect, useState} from 'react';
import {RotateCcw, SlidersHorizontal} from 'lucide-react';
import {api} from './api';

/** Per-effect settings ("Effect settings" panel), generated from the backend
 *  schema at GET /api/effects/schema (backend/app/render/effect_params.py), so
 *  the editor and the renderer never drift. Values are stored per preset in
 *  look.fx_params = {<preset>: {<param>: value}}; switching back to a look
 *  restores its settings. Missing values mean the default. */
export type EffectParam = {
  name: string; label: string; kind: 'number' | 'color'; default: number | string;
  min?: number; max?: number; step?: number; unit?: string; help?: string;
  css?: {fn: string; k?: number};
};
export type EffectSchema = {version: number; look_key: string; presets: Record<string, {managed_by?: string; params: EffectParam[]}>};
export type FxParams = Record<string, Record<string, number | string>>;

let cached: EffectSchema | null = null;
let inflight: Promise<EffectSchema | null> | null = null;

export function loadEffectSchema(): Promise<EffectSchema | null> {
  if (cached) return Promise.resolve(cached);
  if (!inflight) inflight = api.effectsSchema()
    .then(s => {cached = s && s.presets ? s : null; return cached;})
    .catch(() => null)          // older backend: no settings panel, everything else works
    .finally(() => {inflight = null;});
  return inflight;
}

export function useEffectSchema(): EffectSchema | null {
  const [schema, setSchema] = useState<EffectSchema | null>(cached);
  useEffect(() => {
    let live = true;
    if (!cached) void loadEffectSchema().then(s => {if (live && s) setSchema(s);});
    return () => {live = false;};
  }, []);
  return schema;
}

const fmt = (v: number) => Number(v.toFixed(3));

/** CSS approximation of the changed settings for the canvas preview and the
 *  effect tile (the exact result comes from the FFmpeg render). */
export function fxPreviewFilter(schema: EffectSchema | null, preset: string | null | undefined, fx?: FxParams | null): string {
  const entry = preset ? schema?.presets[preset] : undefined;
  const vals = preset ? fx?.[preset] : undefined;
  if (!entry || entry.managed_by || !vals) return '';
  const parts: string[] = [];
  for (const q of entry.params) {
    const v = vals[q.name];
    if (q.kind !== 'number' || !q.css || typeof v !== 'number' || v === q.default) continue;
    const d = Number(q.default), x = (v - d) * (q.css.k ?? 0.01);
    switch (q.css.fn) {
      case 'saturate': case 'contrast': parts.push(`${q.css.fn}(${fmt(Math.max(0, d ? v / d : 1 + v / 100))})`); break;
      case 'contrast_k': parts.push(`contrast(${fmt(Math.max(0, 1 + x))})`); break;
      case 'brightness': parts.push(`brightness(${fmt(Math.max(0, 1 + x))})`); break;
      case 'hue': parts.push(`hue-rotate(${fmt(x)}deg)`); break;
      case 'blur': if (x > 0) parts.push(`blur(${fmt(x)}px)`); break;
      case 'warmth': parts.push(x > 0 ? `sepia(${fmt(Math.min(0.8, x))}) saturate(${fmt(1 + x * 0.5)})` : `hue-rotate(${fmt(-x * 40)}deg) saturate(${fmt(Math.max(0.3, 1 + x * 0.5))})`); break;
    }
  }
  return parts.join(' ');
}

const snap = (v: number, q: EffectParam) => {
  const step = q.step || 1, lo = q.min ?? 0, hi = q.max ?? 100;
  return Math.max(lo, Math.min(hi, Number((Math.round((v - lo) / step) * step + lo).toFixed(4))));
};

/** The generic "Effect settings" panel for the active preset. Hidden for
 *  Original and for presets with their own panel (glitch, focus, mosaic, RGB split). */
export function EffectSettings({preset, look, disabled, onDraft}: {
  preset: string; look?: {fx_params?: FxParams | null} | null; disabled?: boolean;
  onDraft: (look: {fx_params: FxParams | null}) => void;
}) {
  const schema = useEffectSchema();
  const [fx, setFx] = useState<FxParams>(() => ({...(look?.fx_params || {})}));
  const entry = schema?.presets[preset];
  if (!entry || entry.managed_by || !entry.params.length) return null;
  const vals = fx[preset] || {};
  const commit = (next: FxParams) => {setFx(next); onDraft({fx_params: Object.keys(next).length ? next : null});};
  const set = (name: string, v: number | string) => commit({...fx, [preset]: {...vals, [name]: v}});
  const reset = () => {const next = {...fx}; delete next[preset]; commit(next);};
  const changed = entry.params.some(q => q.name in vals && vals[q.name] !== q.default);
  return <section className="look-section effect-settings" aria-label="Effect settings">
    <div className="look-heading"><h3><SlidersHorizontal size={15}/> Effect settings</h3>
      <button className="text-btn" disabled={disabled || !changed} onClick={reset} title="Restore this effect's default settings"><RotateCcw size={13}/> Reset to default</button></div>
    <p className="hint">Fine-tune this effect. Settings are kept per effect, so switching back restores them. The preview is approximate; render to see the exact result.</p>
    {entry.params.map(q => {
      const v = vals[q.name] ?? q.default;
      const isChanged = v !== q.default;
      const aria = `Effect ${q.label.toLowerCase()}`;
      if (q.kind === 'color') return <div key={q.name} className={`adjust-row ${isChanged ? 'changed' : ''}`} title={q.help}>
        <label>{q.label}</label>
        <input aria-label={aria} type="color" value={String(v).toLowerCase()} disabled={disabled} onChange={e => set(q.name, e.target.value.toUpperCase())}/>
        <span className="unit">{String(v).toUpperCase()}</span></div>;
      const num = Number(v);
      return <div key={q.name} className={`adjust-row ${isChanged ? 'changed' : ''}`} title={q.help}>
        <label>{q.label}</label>
        <input aria-label={aria} type="range" min={q.min} max={q.max} step={q.step || 1} value={num} disabled={disabled}
          onChange={e => set(q.name, snap(Number(e.target.value), q))} onDoubleClick={() => set(q.name, q.default)}/>
        <input aria-label={`${aria} value`} type="number" min={q.min} max={q.max} step={q.step || 1} value={num} disabled={disabled}
          onChange={e => {const n = Number(e.target.value); if (e.target.value !== '' && Number.isFinite(n)) set(q.name, snap(n, q));}}/>
        <span className="unit">{q.unit || ''}</span></div>;
    })}
  </section>;
}
