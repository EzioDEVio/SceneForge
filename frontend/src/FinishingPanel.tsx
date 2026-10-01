import React, {useEffect, useRef, useState} from 'react';
import {Music, Upload, Clapperboard, Gauge} from 'lucide-react';
import {api, Asset, Finishing, Project, ProjectAudioClip} from './api';
import {FeatureHelp} from './FeatureHelp';
import {GainEnvelopeEditor} from './GainEnvelope';
import {TimelineClipVoiceIsolation} from './VoiceIsolation';

const MUSIC_DEFAULTS = {volume: 35, duck: 70, fade_in_ms: 1500, fade_out_ms: 3000};

/** Whole-video finishing, applied when the video is exported: background
 *  music that ducks under narration, YouTube loudness, countdown leader. */
export function FinishingPanel({project, disabled, onChanged,selectedClipId,onSelectClip,onUpdateAudioClips}: {project: Project; disabled: boolean; onChanged: () => Promise<unknown> | void;selectedClipId?:string;onSelectClip?:(id:string)=>void;onUpdateAudioClips?:(clips:ProjectAudioClip[])=>void}) {
  const [fin, setFin] = useState<Finishing>(project.finishing_json || {});
  const [tracks, setTracks] = useState<Asset[]>([]);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [syncing, setSyncing] = useState(false);
  const [fitting, setFitting] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const clipFile = useRef<HTMLInputElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => {setFin(project.finishing_json || {});}, [project.id,project.finishing_json]);
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
  async function uploadTimelineClip(file?:File){
    if(!file)return;
    try{
      const asset=await api.uploadAsset(project.id,file);
      if(asset.type!=='audio')throw new Error('Choose an audio file such as MP3, WAV, M4A, AAC, OGG, or FLAC.');
      const duration=Math.max(200,Math.round(asset.duration_ms||1000));
      const clip:ProjectAudioClip={id:crypto.randomUUID(),asset_id:asset.id,name:asset.original_filename||file.name,start_ms:0,source_in_ms:0,source_out_ms:duration,source_duration_ms:duration,volume:100,fade_in_ms:0,fade_out_ms:0,mute:false};
      setTracks(items=>[...items,asset]);
      const next=[...(fin.audio_clips||[]),clip];
      if(onUpdateAudioClips)onUpdateAudioClips(next);else save({...fin,audio_clips:next},true);
      onSelectClip?.(clip.id);setStatus('Audio clip added to the timeline. Drag it on A3 to position it.');
    }catch(e:any){setError(e?.message||'Could not add the audio clip.');}
    finally{if(clipFile.current)clipFile.current.value='';}
  }
  const audioClips=fin.audio_clips||[];
  const activeClip=audioClips.find(clip=>clip.id===selectedClipId)||audioClips[0];
  function changeAudioClip(id:string,patch:Partial<ProjectAudioClip>,now=false){
    const next=audioClips.map(clip=>clip.id===id?{...clip,...patch}:clip);
    if(onUpdateAudioClips)onUpdateAudioClips(next);else save({...fin,audio_clips:next},now);
  }
  const m = fin.music;
  const slider = (key: 'volume' | 'duck', label: string) => m && <label className="control-label">{label} · {m[key]}%
    <input aria-label={`Music ${label}`} type="range" min={0} max={100} step={5} value={m[key]} disabled={disabled} onChange={e => save({...fin, music: {...m, [key]: Number(e.target.value)}})}/></label>;

  return <section className="look-section finishing-panel" aria-label="Music and finishing">
    <div className="look-heading"><h3><Music size={15}/> Music & finishing</h3><FeatureHelp compact title="Music and finishing" description="Add a project soundtrack and apply final loudness and audio treatments." steps="Import or choose music, adjust its level and narration ducking, set fades, and render the full project to hear the finished mix."/><span className="hint" aria-live="polite">{status}</span></div>
    <p className="hint">The background music bed plays across the whole video. Use A3 below for independent audio clips with their own move, trim, mute, volume, fade, and split controls.</p>
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
      <button className="btn" disabled={disabled || fitting} onClick={async () => {
        setFitting(true); setError('');
        try {
          const fitted = await api.musicFit(project.id, m.asset_id);
          setTracks(t => [...t, fitted]);
          save({...fin, music: {...m, asset_id: fitted.id}}, true);
          setStatus(`Music re-edited to ${((fitted.duration_ms || 0) / 1000).toFixed(1)} s on the beat · original kept in the list`);
        } catch (e: any) {setError(e.message || 'Could not fit the music.');} finally {setFitting(false);}
      }}>{fitting ? 'Re-editing on the beat…' : 'Fit music to video length'}</button>
      <p className="hint">Beat-aware re-edit (not AI): removes or repeats whole bars on the beat with short crossfades and ends with a fade-out. Saves a new copy and switches the music bed to it; the original file is unchanged.</p>
      <button className="btn" disabled={disabled || syncing} onClick={async () => {setSyncing(true); setError(''); try {const r = await api.beatSync(project.id); setStatus(`${r.bpm} BPM · ${r.scenes_changed} cut${r.scenes_changed === 1 ? '' : 's'} moved onto the beat${r.scenes_kept ? ` · ${r.scenes_kept} narrated scene${r.scenes_kept === 1 ? '' : 's'} kept` : ''}`); await onChanged();} catch (e: any) {setError(e.message || 'Beat sync failed.');} finally {setSyncing(false);}}}>{syncing ? 'Finding the beat…' : 'Sync scene cuts to the beat'}</button>
      <p className="hint">Changes fixed-length scenes so each cut lands on a beat. Scenes that follow their narration keep their length.</p>
    </>}
    <section className="timeline-audio-controls" aria-label="Timeline audio clips">
      <div className="section-heading"><h3>Timeline audio clips</h3><span>{audioClips.length} on A3–A8</span></div>
      <div className="lut-row"><select aria-label="Select timeline audio clip" value={activeClip?.id||''} disabled={disabled||!audioClips.length} onChange={e=>onSelectClip?.(e.target.value)}><option value="">No timeline audio clips</option>{audioClips.map(clip=><option key={clip.id} value={clip.id}>{clip.name}</option>)}</select><button className="btn" disabled={disabled} onClick={()=>clipFile.current?.click()}><Upload size={14}/> Add audio clip</button><input ref={clipFile} type="file" accept="audio/*,.mp3,.wav,.m4a,.aac,.ogg,.flac" hidden aria-label="Upload timeline audio clip" onChange={e=>void uploadTimelineClip(e.target.files?.[0])}/></div>
      {activeClip?<>
        <p className="hint">Click inside its block on A3–A8 to place the playhead, then use the scissors above to split. Drag the block to move it; drag either edge to trim. Volume, mute, and fades are controlled here.</p>
        <div className="section-heading"><strong>{activeClip.name}</strong><button className="text-btn" disabled={disabled} onClick={()=>{const next=audioClips.filter(clip=>clip.id!==activeClip.id);if(onUpdateAudioClips)onUpdateAudioClips(next);else save({...fin,audio_clips:next},true);onSelectClip?.(next[0]?.id||'');}}>Remove clip</button></div>
        <label className="control-label">Track<select aria-label="Timeline audio clip track" value={activeClip.track||'A3'} disabled={disabled} onChange={e=>changeAudioClip(activeClip.id,{track:e.target.value==='A3'?undefined:e.target.value as ProjectAudioClip['track']},true)}>{['A3','A4','A5','A6','A7','A8'].map(t=><option key={t} value={t}>{t}</option>)}</select></label>
        <label className="switch-label finishing-toggle"><input type="checkbox" aria-label="Mute timeline audio clip" checked={activeClip.mute} disabled={disabled} onChange={e=>changeAudioClip(activeClip.id,{mute:e.target.checked},true)}/> Mute this clip</label>
        <GainEnvelopeEditor clip={activeClip} disabled={disabled} onChange={gain=>changeAudioClip(activeClip.id,{gain:gain.length?gain:undefined},true)}/>
        <label className="control-label">Clip volume · {activeClip.volume}%<input aria-label="Timeline audio clip volume" type="range" min={0} max={200} step={5} value={activeClip.volume} disabled={disabled} onChange={e=>changeAudioClip(activeClip.id,{volume:Number(e.target.value)})}/></label>
        <label className="control-label">Trim start · {(activeClip.source_in_ms/1000).toFixed(2)}s<input aria-label="Timeline audio trim start" type="range" min={0} max={Math.max(0,activeClip.source_out_ms-100)} step={50} value={activeClip.source_in_ms} disabled={disabled} onChange={e=>{const nextIn=Number(e.target.value),duration=activeClip.source_out_ms-nextIn,fadeIn=Math.min(activeClip.fade_in_ms,duration);changeAudioClip(activeClip.id,{source_in_ms:nextIn,start_ms:Math.max(0,activeClip.start_ms+nextIn-activeClip.source_in_ms),fade_in_ms:fadeIn,fade_out_ms:Math.min(activeClip.fade_out_ms,Math.max(0,duration-fadeIn))});}}/></label>
        <label className="control-label">Trim end · {(activeClip.source_out_ms/1000).toFixed(2)}s<input aria-label="Timeline audio trim end" type="range" min={Math.min(activeClip.source_duration_ms,activeClip.source_in_ms+100)} max={activeClip.source_duration_ms} step={50} value={activeClip.source_out_ms} disabled={disabled} onChange={e=>{const sourceOut=Number(e.target.value),duration=sourceOut-activeClip.source_in_ms,fadeIn=Math.min(activeClip.fade_in_ms,duration);changeAudioClip(activeClip.id,{source_out_ms:sourceOut,fade_in_ms:fadeIn,fade_out_ms:Math.min(activeClip.fade_out_ms,Math.max(0,duration-fadeIn))});}}/></label>
        <div className="audio-fades"><label className="control-label">Fade in · {(activeClip.fade_in_ms/1000).toFixed(1)} s<input aria-label="Timeline audio fade in" type="range" min={0} max={10000} step={100} value={activeClip.fade_in_ms} disabled={disabled} onChange={e=>{const duration=activeClip.source_out_ms-activeClip.source_in_ms,fadeIn=Math.min(Number(e.target.value),duration);changeAudioClip(activeClip.id,{fade_in_ms:fadeIn,fade_out_ms:Math.min(activeClip.fade_out_ms,duration-fadeIn)});}}/></label><label className="control-label">Fade out · {(activeClip.fade_out_ms/1000).toFixed(1)} s<input aria-label="Timeline audio fade out" type="range" min={0} max={10000} step={100} value={activeClip.fade_out_ms} disabled={disabled} onChange={e=>{const duration=activeClip.source_out_ms-activeClip.source_in_ms,fadeOut=Math.min(Number(e.target.value),duration);changeAudioClip(activeClip.id,{fade_out_ms:fadeOut,fade_in_ms:Math.min(activeClip.fade_in_ms,duration-fadeOut)});}}/></label></div>
        <TimelineClipVoiceIsolation key={activeClip.id} clip={activeClip} disabled={disabled} onReplace={patch=>changeAudioClip(activeClip.id,patch,true)}/>
      </>:<p className="hint">Add an audio clip or drop one directly on an audio track (A3–A8). Clips can overlap and mix with video sound and background music.</p>}
    </section>
    <label className="switch-label finishing-toggle"><input type="checkbox" aria-label="Level loudness for YouTube" checked={!!fin.loudnorm} disabled={disabled} onChange={e => save({...fin, loudnorm: e.target.checked}, true)}/><Gauge size={14}/> Level loudness for YouTube (-14 LUFS)</label>
    
    {error && <p className="form-error" role="alert">{error}</p>}
  </section>;
}
