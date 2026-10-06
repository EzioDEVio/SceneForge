import {AudioCensor} from './AudioCensor';
import type {CensorRange} from './api';
import React, {useEffect, useRef, useState} from 'react';
import {Play, Square, Trash2, RotateCcw, AudioLines} from 'lucide-react';
import {api, AudioEdit, Scene, VoiceTake, Waveform} from './api';
import {sceneDuration} from './duration';
import {FeatureHelp} from './FeatureHelp';
import {NarrationVoiceIsolation} from './VoiceIsolation';

/** Take the audio off a scene without touching its picture. A scene that
 *  followed the audio keeps its current length (switches to fixed timing),
 *  so the timeline does not jump. The take stays in the scene's takes list
 *  and the file stays in the Media Pool. */
export async function removeSceneAudio(scene: Scene) {
  if (scene.timing_mode === 'audio_driven') {
    await api.updateScene(scene.id, {timing_mode: 'fixed', requested_duration_ms: Math.max(1000, Math.round(sceneDuration(scene)))});
  }
  await api.clearNarration(scene.id);
}

const waveCache = new Map<string, Promise<Waveform>>();
export function loadWaveform(assetId: string, points = 600): Promise<Waveform> {
  const key = `${assetId}:${points}`;
  if (!waveCache.has(key)) waveCache.set(key, api.waveform(assetId, points).catch(e => {waveCache.delete(key); throw e;}));
  return waveCache.get(key)!;
}

const DEFAULTS = {in_ms: 0, out_ms: null as number | null, volume: 100, fade_in_ms: 0, fade_out_ms: 0, voice_fx: 'none',censor:[] as CensorRange[]};
const secs = (ms: number) => (ms / 1000).toFixed(2);

/** Peak bars as a single SVG path, from `from` to `to` (0..1 of the file). */
export function WavePath({peaks, from = 0, to = 1, height = 40, className}: {peaks: number[]; from?: number; to?: number; height?: number; className?: string}) {
  const a = Math.floor(from * peaks.length), b = Math.max(a + 1, Math.ceil(to * peaks.length));
  const slice = peaks.slice(a, b);
  const w = slice.length, mid = height / 2;
  const d = slice.map((p, i) => `M${i + .5} ${mid - p * mid}V${mid + p * mid}`).join('');
  return <svg className={className} viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none" aria-hidden="true"><path d={d} vectorEffect="non-scaling-stroke"/></svg>;
}

type Props = {scene: Scene; take: VoiceTake; disabled: boolean; onChanged: () => Promise<unknown> | void; onRemove: () => Promise<unknown> | void};

export function AudioClipEditor({scene, take, disabled, onChanged, onRemove}: Props) {
  const asset = take.audio_asset;
  const source = take.measured_duration_ms || 0;
  const [edit, setEdit] = useState({...DEFAULTS, ...(take.edit_json || {})});
  const [wave, setWave] = useState<Waveform | null>(null);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [playing, setPlaying] = useState(false);
  const [previewRate,setPreviewRate]=useState(1),[original,setOriginal]=useState(false);
  const beforeMute=useRef(100);
  const [head, setHead] = useState<number | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const audio = useRef<HTMLAudioElement>(null);
  const graph = useRef<{ctx: AudioContext; gain: GainNode; censor:GainNode; tone:GainNode} | null>(null);
  const strip = useRef<HTMLDivElement>(null);
  const raf = useRef(0);

  useEffect(() => {setEdit({...DEFAULTS, ...(take.edit_json || {})}); setError('');}, [take.id]);
  useEffect(() => {let live = true; if (asset) loadWaveform(asset.id).then(w => live && setWave(w)).catch(() => live && setWave(null)); return () => {live = false;};}, [asset?.id]);
  useEffect(() => () => {stop(); if (timer.current) clearTimeout(timer.current);void graph.current?.ctx.close();}, []);

  const outMs = edit.out_ms ?? source;
  const clipMs = Math.max(0, outMs - edit.in_ms);

  function change(patch: Partial<typeof edit>,now=false) {
    const next = {...edit, ...patch};
    const used=Math.max(0,(next.out_ms??source)-next.in_ms);next.fade_in_ms=Math.min(next.fade_in_ms,used);next.fade_out_ms=Math.min(next.fade_out_ms,Math.max(0,used-next.fade_in_ms));
    setEdit(next); setError(''); setStatus('Unsaved changes');
    if (timer.current) clearTimeout(timer.current);
    if(now)void save(next);else timer.current = setTimeout(() => void save(next), 450);
  }
  async function save(next: typeof edit) {
    try {
      const out: AudioEdit = {...next, out_ms: next.out_ms !== null && next.out_ms >= source ? null : next.out_ms};
      await api.editTake(take.id, out);
      setStatus('Saved'); await onChanged();
    } catch (e: any) {setError(e.message || 'Could not save the audio settings.'); setStatus('');}
  }

  // Trim handles: drag on the waveform strip.
  function dragHandle(which: 'in' | 'out', e: React.PointerEvent) {
    if (disabled || !strip.current || !source) return;
    e.preventDefault(); (e.target as HTMLElement).setPointerCapture(e.pointerId);
    const rect = strip.current.getBoundingClientRect();
    const move = (ev: PointerEvent) => {
      const ms = Math.round(Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width)) * source / 10) * 10;
      if (which === 'in') change({in_ms: Math.min(ms, outMs - 200)});
      else change({out_ms: Math.max(ms, edit.in_ms + 200)});
    };
    const up = () => {window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up);};
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up);
  }

  function stop() {
    cancelAnimationFrame(raf.current);
    audio.current?.pause(); if(graph.current)graph.current.tone.gain.value=0; setPlaying(false); setHead(null);
  }
  async function play() {
    const el = audio.current; if (!el) return;
    if (playing) {stop(); return;}
    const vol = original?1:edit.volume / 100;
    el.playbackRate=previewRate;
    try {
      if (!graph.current && typeof AudioContext !== 'undefined') {
        const ctx = new AudioContext(); const gain = ctx.createGain();
        const censor=ctx.createGain(),tone=ctx.createGain(),osc=ctx.createOscillator();osc.frequency.value=1000;tone.gain.value=0;osc.connect(tone).connect(gain);osc.start();ctx.createMediaElementSource(el).connect(censor).connect(gain).connect(ctx.destination);
        graph.current = {ctx, gain, censor, tone};
      }
      const g = graph.current;
      if (g) {
        await g.ctx.resume(); const now = g.ctx.currentTime, clip = (original?source:clipMs) / 1000 / previewRate;
        g.gain.gain.cancelScheduledValues(now);
        g.gain.gain.setValueAtTime(!original&&edit.fade_in_ms ? 0 : vol, now);
        if (!original&&edit.fade_in_ms) g.gain.gain.linearRampToValueAtTime(vol, now + edit.fade_in_ms / 1000 / previewRate);
        if (!original&&edit.fade_out_ms) {g.gain.gain.setValueAtTime(vol, now + clip - edit.fade_out_ms / 1000 / previewRate); g.gain.gain.linearRampToValueAtTime(0, now + clip);}
        el.volume = 1;
      } else el.volume = Math.min(1, vol);
      if(g){const range=!original&&edit.censor.find(r=>edit.in_ms>=r.start_ms&&edit.in_ms<r.end_ms);g.censor.gain.value=range?0:1;g.tone.gain.value=range&&range.mode==='bleep'?.15:0;}
      el.currentTime = original?0:edit.in_ms / 1000;
      await el.play(); setPlaying(true);
      const tick = () => {
        const t = el.currentTime * 1000;
        if (t >= (original?source:outMs) || el.paused) {stop(); return;}
        if(g){const range=!original&&edit.censor.find(r=>t>=r.start_ms&&t<r.end_ms);g.censor.gain.value=range?0:1;g.tone.gain.value=range&&range.mode==='bleep'?.15:0;}
        setHead(t); raf.current = requestAnimationFrame(tick);
      };
      raf.current = requestAnimationFrame(tick);
    } catch {setError('Playback was blocked by the browser. Click Play again.');}
  }

  if (!asset) return null;
  const pct = (ms: number) => `${source ? (ms / source) * 100 : 0}%`;
  return <section className="audio-clip-editor" aria-label="Scene audio clip">
    <div className="look-heading"><h3><AudioLines size={15}/> Scene audio</h3><FeatureHelp compact title="Scene audio clip" description="Edit the selected narration or recording without changing the original audio file in the Media Pool." steps="Adjust the in/out handles, volume, fades, and voice effect. Changes are saved on this scene's selected take."/><span className="hint" aria-live="polite">{status}</span></div>
    <p className="audio-clip-name" title={asset.original_filename}>{asset.original_filename || take.voice || 'Narration'} · {secs(clipMs)} s used of {secs(source)} s</p>
    <div className="audio-card"><h4>Trim & listen</h4><p className="hint">Drag the handles to keep the part you need.</p><div className="audio-wave" ref={strip}>
      {wave ? <WavePath peaks={wave.peaks} height={56} className="audio-wave-svg"/> : <div className="audio-wave-empty">Reading waveform…</div>}
      {edit.censor.map((range,i)=><div key={i} className="audio-censor-band" aria-label={`${range.mode} range ${(range.start_ms/1000).toFixed(2)}–${(range.end_ms/1000).toFixed(2)} seconds`} style={{position:"absolute",top:0,bottom:0,left:pct(range.start_ms),width:pct(range.end_ms-range.start_ms),background:"#aa77dd55",pointerEvents:"none"}}/>)}
      <div className="audio-trimmed" style={{left: 0, width: pct(edit.in_ms)}}/>
      <div className="audio-trimmed" style={{left: pct(outMs), right: 0}}/>
      {edit.fade_in_ms > 0 && <div className="audio-fade in" style={{left: pct(edit.in_ms), width: pct(edit.fade_in_ms)}}/>}
      {edit.fade_out_ms > 0 && <div className="audio-fade out" style={{left: pct(outMs - edit.fade_out_ms), width: pct(edit.fade_out_ms)}}/>}
      <div className="audio-handle" role="slider" aria-label="Trim start" aria-valuemin={0} aria-valuemax={source} aria-valuenow={edit.in_ms} tabIndex={0} style={{left: pct(edit.in_ms)}} onPointerDown={e => dragHandle('in', e)}
        onKeyDown={e => {if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {e.preventDefault(); change({in_ms: Math.max(0, Math.min(outMs - 200, edit.in_ms + (e.key === 'ArrowRight' ? 100 : -100)))});}}}/>
      <div className="audio-handle out" role="slider" aria-label="Trim end" aria-valuemin={0} aria-valuemax={source} aria-valuenow={outMs} tabIndex={0} style={{left: pct(outMs)}} onPointerDown={e => dragHandle('out', e)}
        onKeyDown={e => {if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {e.preventDefault(); change({out_ms: Math.min(source, Math.max(edit.in_ms + 200, outMs + (e.key === 'ArrowRight' ? 100 : -100)))});}}}/>
      {head !== null && <div className="audio-head" style={{left: pct(head)}}/>}
    </div>
    <div className="audio-times">
      <label>Start (s)<input aria-label="Audio start seconds" type="number" min={0} step={0.1} value={secs(edit.in_ms)} disabled={disabled}
        onChange={e => change({in_ms: Math.max(0, Math.min(outMs - 200, Math.round(Number(e.target.value) * 1000) || 0))})}/></label>
      <label>End (s)<input aria-label="Audio end seconds" type="number" min={0} step={0.1} value={secs(outMs)} disabled={disabled}
        onChange={e => change({out_ms: Math.min(source, Math.max(edit.in_ms + 200, Math.round(Number(e.target.value) * 1000) || source))})}/></label>
      <button className="btn" onClick={() => void play()} disabled={disabled}>{playing ? <><Square size={13}/> Stop</> : <><Play size={13}/> Play clip</>}</button>
    </div>
    <div className="audio-preview-options"><label>Preview speed<select aria-label="Audio preview speed" value={previewRate} disabled={disabled} onChange={e=>{stop();setPreviewRate(Number(e.target.value));}}>{[.75,1,1.25,1.5].map(n=><option key={n} value={n}>{n}×</option>)}</select></label><label className="switch-label"><input type="checkbox" aria-label="Listen to original audio" checked={original} disabled={disabled} onChange={e=>{stop();setOriginal(e.target.checked);}}/> Hear original file</label></div><p className="audio-listening-state">{original?"Listening: original file (trim, fades, level and censor bypassed)":"Listening: edited narration (trim, fades, level and censor applied)"}</p><p className="hint">Preview speed and Hear original are for listening only. Voice effects are heard after rendering.</p></div>
    <div className="audio-card"><h4>Level & fades</h4><label className="switch-label"><input type="checkbox" aria-label="Mute scene narration" checked={edit.volume===0} disabled={disabled} onChange={e=>{if(e.target.checked){beforeMute.current=edit.volume||100;change({volume:0});}else change({volume:beforeMute.current});}}/> Mute narration</label><label className="control-label">Volume · {edit.volume}%
      <input aria-label="Audio volume" type="range" min={0} max={200} step={5} value={edit.volume} disabled={disabled} onChange={e => change({volume: Number(e.target.value)})} onDoubleClick={() => change({volume: 100})}/></label>
    <div className="audio-fades">
      <label className="control-label">Fade in · {secs(edit.fade_in_ms)} s
        <input aria-label="Fade in" type="range" min={0} max={Math.min(10000, Math.max(0, clipMs - edit.fade_out_ms))} step={100} value={edit.fade_in_ms} disabled={disabled} onChange={e => change({fade_in_ms: Number(e.target.value)})}/></label>
      <label className="control-label">Fade out · {secs(edit.fade_out_ms)} s
        <input aria-label="Fade out" type="range" min={0} max={Math.min(10000, Math.max(0, clipMs - edit.fade_in_ms))} step={100} value={edit.fade_out_ms} disabled={disabled} onChange={e => change({fade_out_ms: Number(e.target.value)})}/></label>
    </div>
    </div><div className="audio-card"><h4>Voice cleanup & style</h4><div className="audio-preset-grid" role="group" aria-label="Scene audio presets">{[['Clear speech','clean'],['Dialogue','dialogue'],['Vintage radio','radio'],['Natural','none']].map(([label,fx])=><button className="btn" key={fx} disabled={disabled} onClick={()=>change({voice_fx:fx})}>{label}</button>)}</div><p className="hint">Presets change the voice effect while keeping your trim, volume and fades.</p><label className="control-label">Voice effect<select aria-label="Voice effect" value={edit.voice_fx || 'none'} disabled={disabled} onChange={e => change({voice_fx: e.target.value})}>
      <option value="none">None</option><option value="clean">Clean up (less noise, even level)</option><option value="dialogue">Dialogue cleanup (noise reduction — not AI voice isolation)</option><option value="radio">1940s radio / newsreel</option><option value="telephone">Telephone</option>
    </select></label>
    <NarrationVoiceIsolation scene={scene} take={take} disabled={disabled} onChanged={onChanged}/>
    </div><AudioCensor ranges={edit.censor} sourceMs={source} disabled={disabled} onChange={censor=>{stop();change({censor},true);}} words={scene.font_json.transcript?.source==='narration'&&scene.font_json.transcript.source_asset_id===asset.id?scene.font_json.transcript.words||[]:[]} wordOffset={(scene.font_json.transcript?.source_in_ms??edit.in_ms)-(scene.font_json.transcript?.source_offset_ms??scene.lead_ms??250)}/>{error && <p className="form-error" role="alert">{error}</p>}
    <div className="button-row audio-actions">
      <button className="text-btn" disabled={disabled || JSON.stringify(edit) === JSON.stringify(DEFAULTS)} onClick={() => change({...DEFAULTS})}><RotateCcw size={12}/> Reset edits</button>
      <button className="btn danger" disabled={disabled} onClick={() => {stop(); void onRemove();}}><Trash2 size={13}/> Remove from scene</button>
    </div>
    <p className="hint">{scene.timing_mode === 'audio_driven' ? 'The scene length follows the trimmed audio.' : 'The scene has a fixed length; audio longer than the scene is cut at the end.'} Removing keeps the scene’s picture; the file stays in the Media Pool and in the takes list below.</p>
    <audio ref={audio} src={api.assetStreamUrl(asset.id)} preload="metadata" onEnded={stop}/>
  </section>;
}
