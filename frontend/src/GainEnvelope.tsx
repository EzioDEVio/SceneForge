// Volume envelope (keyframed gain) for a timeline audio clip. Points are stored in the
// clip's source time, so they stay on the same sound after moving, trimming or splitting.
import React from 'react';
import type {ProjectAudioClip} from './api';

export function envelopeDb(points: [number, number][] | undefined, sourceMs: number) {
  if (!points?.length) return 0;
  const p = [...points].sort((a, b) => a[0] - b[0]);
  if (sourceMs <= p[0][0]) return p[0][1];
  for (let i = 1; i < p.length; i++) if (sourceMs < p[i][0]) return p[i - 1][1] + (p[i][1] - p[i - 1][1]) * (sourceMs - p[i - 1][0]) / Math.max(1, p[i][0] - p[i - 1][0]);
  return p[p.length - 1][1];
}

/** Polyline for drawing the envelope over a clip block (0..100 x, 0..100 y; +12 dB top, -60 bottom). */
export function envelopePath(clip: ProjectAudioClip) {
  if (!clip.gain?.length) return '';
  const span = Math.max(1, clip.source_out_ms - clip.source_in_ms), y = (db: number) => (12 - db) / 72 * 100;
  const xs = [clip.source_in_ms, ...clip.gain.map(p => p[0]).filter(t => t > clip.source_in_ms && t < clip.source_out_ms), clip.source_out_ms];
  return xs.map(t => `${((t - clip.source_in_ms) / span * 100).toFixed(2)},${y(envelopeDb(clip.gain, t)).toFixed(2)}`).join(' ');
}

const PRESETS: [string, (c: ProjectAudioClip) => [number, number][]][] = [
  ['Dip in the middle (under a voice)', c => {const a = c.source_in_ms, d = c.source_out_ms - a; return [[a + d * .2, 0], [a + d * .3, -14], [a + d * .7, -14], [a + d * .8, 0]].map(([t, g]) => [Math.round(t), g]) as [number, number][];}],
  ['Swell up', c => [[c.source_in_ms, -24], [c.source_out_ms, 0]]],
  ['Fade down to quiet', c => [[c.source_in_ms, 0], [c.source_out_ms, -30]]],
];

export function GainEnvelopeEditor({clip, disabled, onChange}: {clip: ProjectAudioClip; disabled: boolean; onChange: (points: [number, number][]) => void}) {
  const points = [...(clip.gain || [])].sort((a, b) => a[0] - b[0]);
  const rel = (t: number) => ((t - clip.source_in_ms) / 1000).toFixed(2);
  const set = (i: number, patch: Partial<{t: number; db: number}>) => onChange(points.map((p, j) => j === i ? [patch.t ?? p[0], patch.db ?? p[1]] as [number, number] : p));
  function add() {
    const t = points.length ? Math.min(clip.source_out_ms, Math.round((points[points.length - 1][0] + clip.source_out_ms) / 2)) : Math.round((clip.source_in_ms + clip.source_out_ms) / 2);
    onChange([...points, [t, Math.round(envelopeDb(points, t))]].slice(0, 32) as [number, number][]);
  }
  return <fieldset className="gain-envelope" aria-label="Volume envelope" disabled={disabled}>
    <legend>Volume envelope <small>(keyframes, dB)</small></legend>
    {points.length === 0 && <p className="hint">No keyframes: the clip plays at its clip volume. Add points to ramp the level up or down over time; the line also shows on the timeline clip.</p>}
    {points.map(([t, db], i) => <div className="gain-point" key={i}>
      <label>At <input aria-label={`Envelope point ${i + 1} time (seconds into the clip)`} type="number" step={0.1} min={0} max={(clip.source_out_ms - clip.source_in_ms) / 1000} value={rel(t)} onChange={e => {const v = Number(e.target.value); if (Number.isFinite(v)) set(i, {t: Math.max(0, Math.min(clip.source_duration_ms || clip.source_out_ms, Math.round(clip.source_in_ms + v * 1000)))});}}/>s</label>
      <label>{db > 0 ? '+' : ''}{db.toFixed(1)} dB<input aria-label={`Envelope point ${i + 1} gain`} type="range" min={-60} max={12} step={0.5} value={db} onChange={e => set(i, {db: Number(e.target.value)})}/></label>
      <button className="text-btn" aria-label={`Remove envelope point ${i + 1}`} onClick={() => onChange(points.filter((_, j) => j !== i))}>Remove</button>
    </div>)}
    <div className="button-row"><button className="text-btn" disabled={points.length >= 32} onClick={add}>Add point</button>
      <select aria-label="Envelope preset" value="" onChange={e => {const p = PRESETS.find(x => x[0] === e.target.value); if (p) onChange(p[1](clip));}}><option value="">Preset…</option>{PRESETS.map(([n]) => <option key={n}>{n}</option>)}</select>
      {points.length > 0 && <button className="text-btn" onClick={() => onChange([])}>Clear envelope</button>}</div>
  </fieldset>;
}
