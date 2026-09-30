import React, {useState} from 'react';
import {Gauge} from 'lucide-react';
import type {Shot} from './api';
import {FeatureHelp} from './FeatureHelp';

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
