import React, {useState} from 'react';
import {Gauge} from 'lucide-react';
import type {Shot} from './api';

type Speed = {speed: number; ramp: 'none' | 'slow_middle' | 'fast_middle'; freeze_at_ms: number; freeze_ms: number};
const NEUTRAL: Speed = {speed: 1, ramp: 'none', freeze_at_ms: 0, freeze_ms: 0};

/** Speed, speed ramps and freeze frames for a video clip. */
export function SpeedControls({shot, disabled, save}: {shot: Shot; disabled: boolean; save: (s: Speed) => void}) {
  const [sp, setSp] = useState<Speed>({...NEUTRAL, ...((shot as any).speed_json || {})});
  const set = (patch: Partial<Speed>) => {const next = {...sp, ...patch}; setSp(next); save(next);};
  return <section className="look-section speed-controls" aria-label="Clip speed">
    <h3><Gauge size={15}/> Clip speed</h3>
    <label className="control-label">Speed · {sp.speed.toFixed(2)}×
      <input type="range" aria-label="Clip speed" min={0.25} max={4} step={0.05} value={sp.speed} disabled={disabled} onChange={e => setSp({...sp, speed: Number(e.target.value)})} onPointerUp={() => save(sp)} onKeyUp={() => save(sp)}/></label>
    <div className="film-option"><span>Speed ramp</span><div className="segmented" role="radiogroup" aria-label="Speed ramp">
      {([['none', 'None'], ['slow_middle', 'Slow-motion moment'], ['fast_middle', 'Fast moment']] as const).map(([v, l]) =>
        <button key={v} role="radio" aria-checked={sp.ramp === v} className={sp.ramp === v ? 'selected' : ''} disabled={disabled} onClick={() => set({ramp: v})}>{l}</button>)}
    </div></div>
    <div className="audio-times">
      <label>Freeze at (s)<input aria-label="Freeze at seconds" type="number" min={0} step={0.1} value={(sp.freeze_at_ms / 1000).toFixed(1)} disabled={disabled} onChange={e => set({freeze_at_ms: Math.max(0, Math.round(Number(e.target.value) * 1000) || 0)})}/></label>
      <label>Hold (s)<input aria-label="Freeze hold seconds" type="number" min={0} max={10} step={0.1} value={(sp.freeze_ms / 1000).toFixed(1)} disabled={disabled} onChange={e => set({freeze_ms: Math.max(0, Math.min(10000, Math.round(Number(e.target.value) * 1000) || 0))})}/></label>
    </div>
    <p className="hint">Slow motion stretches the middle of the clip; a freeze holds one frame. The scene length stays the same. Render to see it.</p>
    {(sp.speed !== 1 || sp.ramp !== 'none' || sp.freeze_ms > 0) && <button className="text-btn" disabled={disabled} onClick={() => set({...NEUTRAL})}>Reset speed</button>}
  </section>;
}


/** Sound of a video clip: volume, mute, and lowering it under narration (so the voice stays clear). */
export function ClipSoundControls({shot, save}: {shot: Shot; save: (a: {volume: number; mute: boolean; duck: boolean}) => void}) {
  const a0 = ((shot as any).audio_json || {}) as {volume?: number; mute?: boolean; duck?: boolean};
  const [a, setA] = React.useState({volume: a0.volume ?? 100, mute: !!a0.mute, duck: a0.duck ?? true});
  const commit = (p: Partial<typeof a>) => {const next = {...a, ...p}; setA(next); save(next);};
  return <section className="clip-sound" aria-label="Clip sound">
    <h4>Clip sound</h4>
    <label className="switch-label finishing-toggle"><input type="checkbox" aria-label="Mute clip sound" checked={a.mute} onChange={e => commit({mute: e.target.checked})}/> Mute this clip's sound</label>
    <div className="adjust-row changed"><label>Volume</label>
      <input type="range" aria-label="Clip volume" min={0} max={200} step={5} value={a.volume} disabled={a.mute} onChange={e => setA({...a, volume: Number(e.target.value)})} onMouseUp={() => save(a)} onKeyUp={() => save(a)} onTouchEnd={() => save(a)}/>
      <input type="number" aria-label="Clip volume value" min={0} max={200} value={a.volume} disabled={a.mute} onChange={e => commit({volume: Math.max(0, Math.min(200, Number(e.target.value) || 0))})}/><span className="unit">%</span></div>
    <label className="switch-label finishing-toggle"><input type="checkbox" aria-label="Lower clip sound under narration" checked={a.duck} disabled={a.mute} onChange={e => commit({duck: e.target.checked})}/> Lower it under narration (voice stays clear)</label>
    <p className="hint">The clip's own sound plays with it in the render. With narration, it drops to about a third so the voice is heard clearly.</p>
  </section>;
}
