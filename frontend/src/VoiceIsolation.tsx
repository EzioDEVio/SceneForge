import React, {useEffect, useRef, useState} from 'react';
import {Mic} from 'lucide-react';
import {api, Asset, Project, ProjectAudioClip, Scene, Shot, VoiceIsolationStatus, VoiceTake} from './api';
import {sequenceClips} from './ProjectTimeline';

/** AI voice isolation (dialogue isolation) with the local MDX-Net model.
 *  Every action creates a NEW audio file; the original stays in the Media Pool. */

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));
const mb = (n: number) => Math.round(n / 1_000_000);

export type IsolateFn = (assetId: string) => Promise<Asset>;

/** Start isolation and wait for the background job, reporting progress text. */
export async function isolateVoiceAsset(assetId: string, strength: number, onProgress: (text: string, pct: number) => void): Promise<Asset> {
  let r = await api.isolateVoice(assetId, strength);
  if (r.status === 'done' && r.asset) return r.asset;
  const jobId = r.job_id!;
  for (;;) {
    await sleep(700);
    const j = await api.voiceIsolationJob(jobId);
    if (j.status === 'done' && j.asset) return j.asset;
    if (j.status === 'error') throw new Error(j.error || 'Voice isolation failed.');
    if (j.stage === 'downloading model') {
      const st = await api.voiceIsolationStatus().catch(() => null);
      const d = st?.download;
      onProgress(d ? `Downloading the voice model… ${mb(d.done)} of ${mb(d.total)} MB (once)` : 'Downloading the voice model (once)…', d && d.total ? Math.round(d.done / d.total * 100) : 0);
    } else onProgress(j.stage === 'isolating' ? `Isolating voice… ${Math.round(j.progress)}%` : 'Isolating voice… loading the model', j.progress);
  }
}

export function VoiceIsolateButton({disabled, label = 'Isolate voice (AI)', hint, action}: {
  disabled?: boolean; label?: string; hint?: React.ReactNode;
  /** Runs the whole operation; returns a success message. */
  action: (isolate: IsolateFn) => Promise<string | void>;
}) {
  const [st, setSt] = useState<VoiceIsolationStatus | null>(null);
  const [strength, setStrength] = useState(100);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<{text: string; pct: number} | null>(null);
  const [done, setDone] = useState('');
  const [error, setError] = useState('');
  const live = useRef(true);
  useEffect(() => {live.current = true; api.voiceIsolationStatus().then(s => live.current && setSt(s)).catch(() => {}); return () => {live.current = false;};}, []);

  async function go() {
    setBusy(true); setError(''); setDone(''); setProgress({text: 'Isolating voice…', pct: 0});
    try {
      const msg = await action(id => isolateVoiceAsset(id, strength, (text, pct) => live.current && setProgress({text, pct})));
      if (live.current) setDone(msg || 'Voice isolated.');
      api.voiceIsolationStatus().then(s => live.current && setSt(s)).catch(() => {});
    } catch (e: any) {if (live.current) setError(e?.message || 'Voice isolation failed.');}
    finally {if (live.current) {setBusy(false); setProgress(null);}}
  }

  const size = st ? `~${st.approx_mb} MB` : '~67 MB';
  return <div className="voice-isolation" aria-label="AI voice isolation">
    <div className="lut-row">
      <button className="btn" disabled={disabled || busy} onClick={() => void go()}><Mic size={13}/> {busy ? 'Isolating voice…' : label}</button>
      <label className="control-label">Strength · {strength}%
        <input type="range" aria-label="Voice isolation strength" min={0} max={100} step={5} value={strength} disabled={disabled || busy} onChange={e => setStrength(Number(e.target.value))} onDoubleClick={() => setStrength(100)}/></label>
    </div>
    {progress && <div aria-live="polite"><progress max={100} value={progress.pct} aria-label="Voice isolation progress"/> <span className="hint">{progress.text}</span></div>}
    <p className="hint">AI voice isolation (local model, {size} download once) · {st ? (st.downloaded ? 'model downloaded' : `not downloaded yet — saved to ${st.folder}`) : 'checking model…'}. Removes music, ambience and noise behind speech; 100% keeps only the voice, lower values blend some of the original back. Runs on your computer (about 1–2 s per second of audio).</p>
    {hint && <p className="hint">{hint}</p>}
    {done && <p className="hint" role="status">{done}</p>}
    {error && <p className="form-error" role="alert">{error}</p>}
  </div>;
}

/** Narration take: isolate the accepted take and switch to a new take using the result. */
export function NarrationVoiceIsolation({scene, take, disabled, onChanged}: {scene: Scene; take: VoiceTake; disabled: boolean; onChanged: () => Promise<unknown> | void}) {
  const asset = take.audio_asset;
  if (!asset) return null;
  return <VoiceIsolateButton disabled={disabled} hint="A/B: the original take stays in this scene's takes list — select it to compare or to go back."
    action={async isolate => {
      const iso = await isolate(asset.id);
      const created = await api.useAudioAsset(scene.id, iso.id) as VoiceTake;
      if (take.edit_json && Object.keys(take.edit_json).length) await api.editTake(created.id, take.edit_json);
      await onChanged();
      return `Now using “${iso.original_filename}” as the narration. Trims, level and fades were copied.`;
    }}/>;
}

/** Timeline audio clip (A3–A8): swap the clip's file for the isolated one, keeping its timing. */
export function TimelineClipVoiceIsolation({clip, disabled, onReplace}: {clip: ProjectAudioClip; disabled: boolean; onReplace: (patch: Partial<ProjectAudioClip>) => void}) {
  const latest = useRef(onReplace); latest.current = onReplace;  // isolation is slow: apply to the clips as they are when it finishes
  return <VoiceIsolateButton disabled={disabled} hint="Replaces this clip's audio with the isolated voice; position, trims, volume and fades stay. Undo restores the original file."
    action={async isolate => {
      const iso = await isolate(clip.asset_id);
      latest.current({asset_id: iso.id, name: iso.original_filename || clip.name, source_duration_ms: Math.max(clip.source_out_ms, iso.duration_ms || clip.source_duration_ms)});
      return 'Clip now uses the isolated voice.';
    }}/>;
}

/** Where a video shot's sound sits on the project timeline (same layout as the A2 track). */
function shotPlacement(project: Project, scene: Scene, shot: Shot) {
  const seq = sequenceClips(project.scenes).find(c => c.scene.id === scene.id);
  const start = seq?.start || 0, duration = seq?.duration || 0;
  const all = scene.shots;
  const weights = all.map(x => Math.max(1, x.duration_ms || x.asset?.duration_ms || duration / Math.max(1, all.length)));
  const total = weights.reduce((a, b) => a + b, 0), i = all.findIndex(x => x.id === shot.id);
  return {startMs: start + duration * weights.slice(0, i).reduce((a, b) => a + b, 0) / total, durationMs: duration * weights[i] / total};
}

/** Video clip sound: isolate it, mute the clip's own sound, and add the voice on A3. One undo step. */
export function ClipSoundVoiceIsolation({project, scene, shot, onRecord, onSelectAudioClip}: {
  project: Project; scene: Scene; shot: Shot;
  onRecord: (label: string, undo: () => Promise<unknown>, redo: () => Promise<unknown>) => void;
  onSelectAudioClip?: (id: string) => void;
}) {
  return <VoiceIsolateButton label="Isolate voice → timeline audio" hint="Isolates this clip's sound, mutes the embedded sound and adds the voice on A3 at the clip's position. Undo puts it back."
    action={async isolate => {
      const place = shotPlacement(project, scene, shot);
      const detached = await api.detachAudio(scene.id, {source: 'shot', shot_id: shot.id, duration_ms: Math.max(100, Math.round(place.durationMs))});
      const iso = await isolate(detached.asset.id);
      const duration = Math.max(200, Math.round(iso.duration_ms || place.durationMs));
      const audio = (shot as any).audio_json || {volume: 100, mute: false, duck: true};
      const clip: ProjectAudioClip = {id: crypto.randomUUID(), asset_id: iso.id, name: iso.original_filename || 'Isolated voice', start_ms: Math.max(0, Math.round(place.startMs + detached.offset_ms)),
        source_in_ms: 0, source_out_ms: duration, source_duration_ms: duration, volume: Math.max(0, Math.min(200, Number(audio.volume ?? 100))), fade_in_ms: 0, fade_out_ms: 0, mute: false};
      const writeClips = async (edit: (clips: ProjectAudioClip[]) => ProjectAudioClip[]) => {
        const current = await api.getProject(project.id);
        const fin = current.finishing_json || {};
        await api.updateProject(project.id, {finishing: {...fin, audio_clips: edit(fin.audio_clips || [])}});
      };
      onRecord('isolate clip voice',
        async () => {await writeClips(c => c.filter(x => x.id !== clip.id)); await api.updateShot(shot.id, {audio});},
        async () => {await api.updateShot(shot.id, {audio: {...audio, mute: true}}); await writeClips(c => [...c.filter(x => x.id !== clip.id), clip]);});
      onSelectAudioClip?.(clip.id);
      return `Voice added on A3 as “${clip.name}”; the clip's own sound is muted.`;
    }}/>;
}
