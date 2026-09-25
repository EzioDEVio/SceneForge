import React, {useEffect, useRef, useState} from 'react';
import {Music, Upload, Clapperboard, Gauge} from 'lucide-react';
import {api, Asset, Finishing, Project} from './api';

const MUSIC_DEFAULTS = {volume: 35, duck: 70, fade_in_ms: 1500, fade_out_ms: 3000};

/** Whole-video finishing, applied when the video is exported: background
 *  music that ducks under narration, YouTube loudness, countdown leader. */
export function FinishingPanel({project, disabled, onChanged}: {project: Project; disabled: boolean; onChanged: () => Promise<unknown> | void}) {
  const [fin, setFin] = useState<Finishing>(project.finishing_json || {});
  const [tracks, setTracks] = useState<Asset[]>([]);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [syncing, setSyncing] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => {setFin(project.finishing_json || {});}, [project.id]);
  useEffect(() => {api.listAssets(project.id).then(a => setTracks(a.filter(x => x.type === 'audio'))).catch(() => {});}, [project.id]);

  function save(next: Finishing, now = false) {
    setFin(next); setError(''); setStatus('Unsaved changes');
    if (timer.current) clearTimeout(timer.current);
    const go = async () => {
      try {await api.updateProject(project.id, {finishing: next}); setStatus('Saved · applied when you export'); await onChanged();}
      catch (e: any) {setError(e.message || 'Could not save.'); setStatus('');}
    };
    if (now) void go(); else timer.current = setTimeout(go, 450);
  }
  async function upload(f?: File) {
    if (!f) return;
    try {
      const a = await api.uploadAsset(project.id, f);
      if (a.type !== 'audio') {setError('Choose an audio file (MP3, WAV, M4A, AAC, OGG or FLAC).'); return;}
      setTracks(t => [...t, a]);
      save({...fin, music: {...MUSIC_DEFAULTS, ...(fin.music || {}), asset_id: a.id}}, true);
    } catch (e: any) {setError(e.message || 'Upload failed.');}
    finally {if (file.current) file.current.value = '';}
  }
  const m = fin.music;
  const slider = (key: 'volume' | 'duck', label: string) => m && <label className="control-label">{label} · {m[key]}%
    <input aria-label={`Music ${label}`} type="range" min={0} max={100} step={5} value={m[key]} disabled={disabled} onChange={e => save({...fin, music: {...m, [key]: Number(e.target.value)}})}/></label>;

  return <section className="look-section finishing-panel" aria-label="Music and finishing">
    <div className="look-heading"><h3><Music size={15}/> Music & finishing</h3><span className="hint" aria-live="polite">{status}</span></div>
    <p className="hint">For the whole video. Applied when you export.</p>
    <div className="lut-row">
      <select aria-label="Background music" value={m?.asset_id || ''} disabled={disabled} onChange={e => save({...fin, music: e.target.value ? {...MUSIC_DEFAULTS, ...(m || {}), asset_id: e.target.value} : null}, true)}>
        <option value="">No background music</option>
        {tracks.map(t => <option key={t.id} value={t.id}>{t.original_filename}</option>)}
      </select>
      <button className="btn" disabled={disabled} onClick={() => file.current?.click()}><Upload size={14}/> Add music</button>
      <input ref={file} type="file" accept="audio/*,.mp3,.wav,.m4a,.aac,.ogg,.flac" hidden aria-label="Upload music" onChange={e => void upload(e.target.files?.[0])}/>
    </div>
    {m && <>
      {slider('volume', 'Music volume')}
      {slider('duck', 'Lower under narration')}
      <div className="audio-fades">
        <label className="control-label">Fade in · {(m.fade_in_ms / 1000).toFixed(1)} s<input aria-label="Music fade in" type="range" min={0} max={10000} step={500} value={m.fade_in_ms} disabled={disabled} onChange={e => save({...fin, music: {...m, fade_in_ms: Number(e.target.value)}})}/></label>
        <label className="control-label">Fade out · {(m.fade_out_ms / 1000).toFixed(1)} s<input aria-label="Music fade out" type="range" min={0} max={10000} step={500} value={m.fade_out_ms} disabled={disabled} onChange={e => save({...fin, music: {...m, fade_out_ms: Number(e.target.value)}})}/></label>
      </div>
      <p className="hint">The music loops to the length of the video and gets quieter automatically whenever someone is speaking.</p>
      <button className="btn" disabled={disabled || syncing} onClick={async () => {setSyncing(true); setError(''); try {const r = await api.beatSync(project.id); setStatus(`${r.bpm} BPM · ${r.scenes_changed} cut${r.scenes_changed === 1 ? '' : 's'} moved onto the beat${r.scenes_kept ? ` · ${r.scenes_kept} narrated scene${r.scenes_kept === 1 ? '' : 's'} kept` : ''}`); await onChanged();} catch (e: any) {setError(e.message || 'Beat sync failed.');} finally {setSyncing(false);}}}>{syncing ? 'Finding the beat…' : 'Sync scene cuts to the beat'}</button>
      <p className="hint">Changes fixed-length scenes so each cut lands on a beat. Scenes that follow their narration keep their length.</p>
    </>}
    <label className="switch-label finishing-toggle"><input type="checkbox" aria-label="Level loudness for YouTube" checked={!!fin.loudnorm} disabled={disabled} onChange={e => save({...fin, loudnorm: e.target.checked}, true)}/><Gauge size={14}/> Level loudness for YouTube (-14 LUFS)</label>
    <label className="switch-label finishing-toggle"><input type="checkbox" aria-label="Countdown leader" checked={!!fin.leader} disabled={disabled} onChange={e => save({...fin, leader: e.target.checked}, true)}/><Clapperboard size={14}/> Film countdown leader at the start (5 s, with the “2-pop” beep)</label>
    {error && <p className="form-error" role="alert">{error}</p>}
  </section>;
}
