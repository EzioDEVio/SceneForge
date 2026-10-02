// Typewriter box (0.9.0): the caption typewriter reveal, its timing and its keystroke sound
// in one place. Before 0.9.0 the on/off switch lived in Caption style → Animation and the
// timing/sound controls were further down the Text tab, which users found hard to follow.
import React, {useEffect, useRef, useState} from 'react';
import {Keyboard, Pause, Play, Upload, Volume2} from 'lucide-react';
import type {Scene} from './api';
import {FeatureHelp} from './FeatureHelp';

const SPEEDS = [{label: 'Slow', ms: 220, hint: 'about 4 letters a second'}, {label: 'Natural', ms: 160, hint: 'about 6 letters a second'}, {label: 'Fast', ms: 80, hint: 'about 12 letters a second'}];

type Props = {
  scene: Scene;
  captions: string;            // current caption text (what gets typed)
  narration: string;           // narration script, copied into captions when they are empty
  update: (patch: Record<string, unknown>) => unknown;
  onCopyNarration: () => void; // fill empty captions from narration
  onUploadSound: () => void;   // opens the file picker
};

export function TypewriterPanel({scene, captions, narration, update, onCopyNarration, onUploadSound}: Props) {
  const f = scene.font_json;
  const on = !!f.typewriter;
  const letters = Math.max(1, Array.from(captions).length - 1);
  const reveal = f.typewriter_duration_ms || letters * 160;
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState('');
  const audio = useRef<HTMLAudioElement | null>(null);
  useEffect(() => () => {audio.current?.pause();}, []);

  function toggle(next: boolean) {
    if (next && !captions.trim() && narration.trim()) onCopyNarration();
    void update({font: {typewriter: next, ...(next ? {captions_enabled: true, karaoke: false, split: 'full'} : {})}});
  }
  async function preview() {
    if (playing) {audio.current?.pause(); setPlaying(false); return;}
    setError('');
    const el = new Audio(`/api/scenes/${scene.id}/typewriter-preview?v=${Date.now()}`);
    audio.current = el;
    el.onended = () => setPlaying(false);
    el.onerror = async () => {
      setPlaying(false);
      try {const r = await fetch(el.src); const j = await r.json(); setError(j.detail || 'The preview could not be played.');}
      catch {setError('The preview could not be played.');}
    };
    try {await el.play(); setPlaying(true);} catch {setPlaying(false);}
  }

  return <section className="typewriter-controls typewriter-box" aria-label="Typewriter">
    <div className="section-heading"><h3><Keyboard size={15}/> Typewriter</h3>
      <FeatureHelp compact title="Typewriter" description="Types your on-screen captions letter by letter, with an optional keystroke sound that follows each letter."
        steps="Turn on Typewriter reveal, pick a speed, then switch on the keystroke sound if you want it. Use Preview sound to hear it. Render the scene to see and hear the result together. Titles have their own typewriter option under the title's Animation."/></div>

    <label className="switch-label finishing-toggle"><input type="checkbox" checked={on} onChange={e => toggle(e.target.checked)}/> Typewriter reveal (captions)</label>
    <p className="hint">{on ? 'Captions type themselves in. Other caption animations are paused while this is on.' : 'Off: captions use the style and animation chosen above.'}</p>

    <fieldset className={`tw-group ${on ? "" : "tw-off"}`}>
      <legend>Speed</legend>
      <div className="button-row tw-speeds">{SPEEDS.map(p => <button className={`btn ${f.typewriter_duration_ms === Math.min(120000, Math.max(100, letters * p.ms)) ? 'selected' : ''}`} key={p.label} title={p.hint}
        onClick={() => update({font: {typewriter_duration_ms: Math.min(120000, Math.max(100, letters * p.ms))}})}>{p.label}</button>)}</div>
      <div className="timing-inputs">
        <label className="control-label">Start delay (seconds)<input aria-label="Typing start delay" type="number" min={0} max={120} step={.1} key={f.typewriter_delay_ms} defaultValue={(f.typewriter_delay_ms || 0) / 1000}
          onBlur={e => {const v = Math.min(120, Math.max(0, Number(e.target.value) || 0)) * 1000; if (v !== (f.typewriter_delay_ms || 0)) void update({font: {typewriter_delay_ms: v}});}}/></label>
        <label className="control-label">Reveal time (seconds)<input aria-label="Typing reveal time" type="number" min={.1} max={120} step={.1} key={f.typewriter_duration_ms} defaultValue={f.typewriter_duration_ms ? f.typewriter_duration_ms / 1000 : ''} placeholder="Auto"
          onBlur={e => {if (e.target.value) {const v = Math.min(120, Math.max(.1, Number(e.target.value) || 3)) * 1000; void update({font: {typewriter_duration_ms: v}});}}}/></label>
      </div>
      <button className="text-btn" onClick={() => update({timing_mode: 'fixed', requested_duration_ms: Math.max(scene.requested_duration_ms || 4000, (f.typewriter_delay_ms || 0) + reveal + 1000)})}>Extend scene to fit typing + 1s hold</button>
      <p className="hint">Typing takes {(((f.typewriter_delay_ms || 0) + reveal) / 1000).toFixed(1)} s. If the scene is shorter, typing speeds up to fit; Extend scene keeps your speed (the scene switches to a fixed length).</p>
    </fieldset>

    <fieldset className={`tw-group ${on ? "" : "tw-off"}`}>
      <legend>Sound</legend>
      <label className="check-label"><input type="checkbox" checked={!!f.typewriter_sound} onChange={e => update({font: {typewriter_sound: e.target.checked}})}/> Synchronized keystrokes</label>
      <label className="control-label tw-volume"><span><Volume2 size={13}/> Keystroke volume · {f.typewriter_volume ?? 50}%</span>
        <input aria-label="Keystroke volume" type="range" min={0} max={100} step={5} key={f.typewriter_volume} defaultValue={f.typewriter_volume ?? 50} disabled={!f.typewriter_sound}
          onPointerUp={e => {const v = Number(e.currentTarget.value); if (v !== (f.typewriter_volume ?? 50)) void update({font: {typewriter_volume: v}});}}
          onKeyUp={e => {const v = Number(e.currentTarget.value); if (v !== (f.typewriter_volume ?? 50)) void update({font: {typewriter_volume: v}});}}/></label>
      <div className="tw-sound-row">
        <span className="tw-sound-name">{f.typewriter_sound_asset_id ? 'Your uploaded sound (one keystroke is cut from it)' : 'Included typewriter keystroke'}</span>
        <button className="btn" aria-label={playing ? 'Stop sound preview' : 'Preview typewriter sound'} disabled={!f.typewriter_sound} onClick={() => void preview()}>{playing ? <Pause size={13}/> : <Play size={13}/>} {playing ? 'Stop' : 'Preview sound'}</button>
      </div>
      {error && <p className="error-box">{error}</p>}
      <div className="button-row">
        <button className="btn upload-btn" onClick={onUploadSound}><Upload size={14}/> Upload typewriter sound</button>
        {f.typewriter_sound_asset_id && <button className="text-btn" onClick={() => update({font: {typewriter_sound_asset_id: null}})}>Use included keystroke</button>}
      </div>
      <p className="hint">The sound follows each letter as it appears, not the rhythm of the original recording. If you also used this recording as narration, remove it under Audio so you don't hear it twice.</p>
    </fieldset>
  </section>;
}
