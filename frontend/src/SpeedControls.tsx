import React, {useState} from 'react';
import {Gauge} from 'lucide-react';
import type {Shot} from './api';
import {FeatureHelp} from './FeatureHelp';

type Ramp = 'none' | 'slow_middle' | 'fast_middle' | 'ease_in' | 'ease_out' | 'bullet' | 'curve';
type Speed = {speed: number; ramp: Ramp; freeze_at_ms: number; freeze_ms: number; curve?: number[]; smooth?: boolean};
const NEUTRAL: Speed = {speed: 1, ramp: 'none', freeze_at_ms: 0, freeze_ms: 0};
const RAMP_OPTIONS: [Ramp, string][] = [['none', 'None'], ['slow_middle', 'Slow-motion moment'], ['fast_middle', 'Fast moment'],
  ['ease_in', 'Ease in (slow → fast)'], ['ease_out', 'Ease out (fast → slow)'], ['bullet', 'Bullet time (fast–slow–fast)'], ['curve', 'Custom curve']];
/** Strip keys the backend does not expect for this ramp (curve only with ramp "curve"). */
const tidy = (s: Speed): Speed => {const {curve, smooth, ...rest} = s; return {...rest, ...(s.ramp === 'curve' ? {curve: curve || [1, 0.4, 1]} : {}), ...(smooth ? {smooth: true} : {})};};

/** Speed, speed ramps and freeze frames for a video clip. */
export function SpeedControls({shot, disabled, save}: {shot: Shot; disabled: boolean; save: (s: Speed) => void}) {
  const [sp, setSp] = useState<Speed>({...NEUTRAL, ...((shot as any).speed_json || {})});
  const set = (patch: Partial<Speed>) => {const next = tidy({...sp, ...patch}); setSp(next); save(next);};
  const curve = sp.curve || [1, 0.4, 1];
  return <section className="look-section speed-controls" aria-label="Clip speed">
    <h3><Gauge size={15}/> Clip speed</h3>
    <label className="control-label">Speed · {sp.speed.toFixed(2)}×
      <input type="range" aria-label="Clip speed" min={0.25} max={4} step={0.05} value={sp.speed} disabled={disabled} onChange={e => setSp({...sp, speed: Number(e.target.value)})} onPointerUp={() => save(tidy(sp))} onKeyUp={() => save(tidy(sp))}/></label>
    <div className="film-option"><span>Speed ramp</span><div className="segmented speed-ramp-options" role="radiogroup" aria-label="Speed ramp">
      {RAMP_OPTIONS.map(([v, l]) =>
        <button key={v} role="radio" aria-checked={sp.ramp === v} className={sp.ramp === v ? 'selected' : ''} disabled={disabled} onClick={() => set({ramp: v})}>{l}</button>)}
    </div></div>
    {sp.ramp === 'curve' && <fieldset className="adjust-group" aria-label="Speed curve points"><legend>Speed curve ({curve.length} points, evenly spaced across the clip)</legend>
      {curve.map((v, i) => <div key={i} className="adjust-row changed"><label>Point {i + 1}</label>
        <input type="range" aria-label={`Speed curve point ${i + 1}`} min={0.25} max={4} step={0.05} value={v} disabled={disabled} onChange={e => setSp({...sp, curve: curve.map((x, k) => k === i ? Number(e.target.value) : x)})} onPointerUp={() => save(tidy(sp))} onKeyUp={() => save(tidy(sp))}/>
        <span className="unit">{v.toFixed(2)}×</span><span/></div>)}
      <div className="button-row">
        <button className="text-btn" disabled={disabled || curve.length >= 5} onClick={() => set({curve: [...curve, 1]})}>Add point</button>
        <button className="text-btn" disabled={disabled || curve.length <= 3} onClick={() => set({curve: curve.slice(0, -1)})}>Remove last point</button>
      </div>
      <p className="hint">Curve points are the actual speeds (0.25–4×); the constant speed above is not applied.</p>
    </fieldset>}
    <label className="switch-label finishing-toggle"><input type="checkbox" aria-label="Smooth slow motion" checked={!!sp.smooth} disabled={disabled} onChange={e => set({smooth: e.target.checked})}/> Smooth slow motion (frame interpolation, slower render)</label>
    <div className="audio-times">
      <label>Freeze at (s)<input aria-label="Freeze at seconds" type="number" min={0} step={0.1} value={(sp.freeze_at_ms / 1000).toFixed(1)} disabled={disabled} onChange={e => set({freeze_at_ms: Math.max(0, Math.round(Number(e.target.value) * 1000) || 0)})}/></label>
      <label>Hold (s)<input aria-label="Freeze hold seconds" type="number" min={0} max={10} step={0.1} value={(sp.freeze_ms / 1000).toFixed(1)} disabled={disabled} onChange={e => set({freeze_ms: Math.max(0, Math.min(10000, Math.round(Number(e.target.value) * 1000) || 0))})}/></label>
    </div>
    <p className="hint">Ramps change speed across the clip; a freeze holds one frame. The scene length stays the same. Smooth slow motion uses FFmpeg motion interpolation where the clip plays slower than 1×. Render to see it.</p>
    {(sp.speed !== 1 || sp.ramp !== 'none' || sp.freeze_ms > 0 || !!sp.smooth) && <button className="text-btn" disabled={disabled} onClick={() => set({...NEUTRAL, smooth: false, curve: undefined})}>Reset speed</button>}
  </section>;
}


/** Sound of a video clip: volume, mute, and lowering it under narration (so the voice stays clear). */
type ClipAudioSettings={volume:number;mute:boolean;duck:boolean;fade_in_ms:number;fade_out_ms:number};
export function ClipSoundControls({shot, save}: {shot: Shot; save: (a: ClipAudioSettings) => void}) {
  const audio = ((shot as any).audio_json || {}) as {volume?: number; mute?: boolean; duck?: boolean; fade_in_ms?:number; fade_out_ms?:number};
  const [a, setA] = React.useState({volume: audio.volume ?? 100, mute: !!audio.mute, duck: audio.duck ?? true, fade_in_ms: audio.fade_in_ms ?? 0, fade_out_ms: audio.fade_out_ms ?? 0});
  const editing = React.useRef(false);
  const latest = React.useRef(a); latest.current = a;
  React.useEffect(() => {if(editing.current)return;const next={volume:audio.volume??100,mute:!!audio.mute,duck:audio.duck??true,fade_in_ms:audio.fade_in_ms??0,fade_out_ms:audio.fade_out_ms??0};latest.current=next;setA(next);},[shot.id,shot.audio_json]);
  const commit = (p: Partial<typeof a>) => {const next = {...latest.current, ...p}; latest.current=next; setA(next); save(next);};
  const setVolume = (value:number) => {const next={...latest.current,volume:Math.max(0,Math.min(200,value))};latest.current=next;setA(next);};
  const saveVolume = (value:number) => commit({volume:Math.max(0,Math.min(200,value))});
  const fadeChange=(key:'fade_in_ms'|'fade_out_ms',value:number)=>{const next={...latest.current,[key]:Math.max(0,Math.min(10000,value))};latest.current=next;setA(next);};
  const fadeSave=(key:'fade_in_ms'|'fade_out_ms',value:number)=>commit({[key]:Math.max(0,Math.min(10000,value))});
  return <section className="clip-sound" aria-label="Clip sound">
    <div className="look-heading"><h4>Clip sound</h4><FeatureHelp compact title="Clip Audio" description="Adjust the sound embedded in this video clip without changing scene narration." steps="Set volume or mute, lower clip sound under narration, then tune fade-in and fade-out. These settings are saved with this video shot and applied when rendered."/></div>
    <label className="switch-label finishing-toggle"><input type="checkbox" aria-label="Mute clip sound" checked={a.mute} onChange={e => commit({mute: e.target.checked})}/> Mute this clip's sound</label>
    <div className="adjust-row changed"><label htmlFor="clip-volume">Volume</label>
      <input id="clip-volume" type="range" aria-label="Clip volume" min={0} max={200} step={5} value={a.volume} disabled={a.mute} onPointerDown={()=>{editing.current=true;}} onKeyDown={()=>{editing.current=true;}} onChange={e => setVolume(Number(e.target.value))} onPointerUp={e => {saveVolume(Number(e.currentTarget.value));editing.current=false;}} onKeyUp={e => {saveVolume(Number(e.currentTarget.value));editing.current=false;}} onBlur={e => {saveVolume(Number(e.currentTarget.value));editing.current=false;}} onPointerCancel={()=>{editing.current=false;}}/>
      <input type="number" aria-label="Clip volume value" min={0} max={200} value={a.volume} disabled={a.mute} onChange={e => setVolume(Number(e.target.value)||0)} onBlur={e=>saveVolume(Number(e.currentTarget.value)||0)}/><span className="unit">%</span></div>
    <label className="switch-label finishing-toggle"><input type="checkbox" aria-label="Lower clip sound under narration" checked={a.duck} disabled={a.mute} onChange={e => commit({duck: e.target.checked})}/> Lower it under narration (voice stays clear)</label>
    <div className="clip-audio-fades" aria-label="Clip audio fades"><label>Fade in · {(a.fade_in_ms/1000).toFixed(1)} s<input aria-label="Clip audio fade in" type="range" min={0} max={10000} step={100} value={a.fade_in_ms} disabled={a.mute} onPointerDown={()=>{editing.current=true;}} onKeyDown={()=>{editing.current=true;}} onChange={e=>fadeChange('fade_in_ms',Number(e.target.value))} onPointerUp={e=>{fadeSave('fade_in_ms',Number(e.currentTarget.value));editing.current=false;}} onKeyUp={e=>{fadeSave('fade_in_ms',Number(e.currentTarget.value));editing.current=false;}} onBlur={e=>{fadeSave('fade_in_ms',Number(e.currentTarget.value));editing.current=false;}} onPointerCancel={()=>{editing.current=false;}}/></label><label>Fade out · {(a.fade_out_ms/1000).toFixed(1)} s<input aria-label="Clip audio fade out" type="range" min={0} max={10000} step={100} value={a.fade_out_ms} disabled={a.mute} onPointerDown={()=>{editing.current=true;}} onKeyDown={()=>{editing.current=true;}} onChange={e=>fadeChange('fade_out_ms',Number(e.target.value))} onPointerUp={e=>{fadeSave('fade_out_ms',Number(e.currentTarget.value));editing.current=false;}} onKeyUp={e=>{fadeSave('fade_out_ms',Number(e.currentTarget.value));editing.current=false;}} onBlur={e=>{fadeSave('fade_out_ms',Number(e.currentTarget.value));editing.current=false;}} onPointerCancel={()=>{editing.current=false;}}/></label></div>
    <p className="hint">The clip's own sound plays with it in the render. With narration, it drops to about a third so the voice is heard clearly. Fade durations are limited to each clip's actual length at render time.</p>
  </section>;
}
