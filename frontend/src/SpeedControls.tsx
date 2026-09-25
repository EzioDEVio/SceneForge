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
