// "Clean up" panel: remove silences (jump cuts) and filler words.
//
// Opened from the timeline context menus with a window event:
//   window.dispatchEvent(new CustomEvent(CLEANUP_EVENT, {detail: {mode, target}}))
// Targets: timeline audio clips on A3–A8 (silences), a scene's video clip sound
// (scene jump cut, backend), or a scene's narration (moved to A3, then cut there).
// Every Apply is one undoable step.
import React, {useEffect, useMemo, useRef, useState} from 'react';
import {Scissors, X} from 'lucide-react';
import {api, Project, ProjectAudioClip, Scene} from './api';
import {CLEANUP_EVENT, CleanupMode, CleanupTarget, DEFAULT_FILLERS, TIMELINE_SEEK_EVENT, FillerResult, OPTIONAL_FILLERS, SILENCE_DEFAULTS, SilenceParams, SilenceResult, cleanupApi} from './cleanupApi';
import {sequenceClips} from './ProjectTimeline';
import {Range, jumpCuts, mergeRanges} from './timeline/jumpCuts';
import {frameMs} from './timeline/timeMath';
import {clipTrack} from './timeline/timeline.types';


/** One detected range: `source` is in the audio a timeline clip plays, `scene` in scene time. */
type Row = {key: string; label: string; clipId?: string; source: Range; scene?: Range; seekMs: number; context?: string};
const secs = (ms: number) => `${(ms / 1000).toFixed(ms < 10000 ? 2 : 1)}s`;

export function CleanupPanel({project, disabled, record, onUpdateAudioClips, onDetachNarration, onScenesChanged}: {
  project: Project; disabled?: boolean;
  record: (label: string, undo: () => Promise<unknown>, redo: () => Promise<unknown>) => Promise<void>;
  onUpdateAudioClips: (clips: ProjectAudioClip[]) => Promise<void> | void;
  onDetachNarration: (sceneId: string, placeMs: number, then: (clip: ProjectAudioClip) => Promise<ProjectAudioClip[]>) => Promise<void> | void;
  onScenesChanged?: (selectId: string) => void;
}) {
  const [open, setOpen] = useState<{mode: CleanupMode; target: CleanupTarget} | null>(null);
  const [params, setParams] = useState<SilenceParams>(SILENCE_DEFAULTS);
  const [terms, setTerms] = useState(DEFAULT_FILLERS.join(', '));
  const [optional, setOptional] = useState<Record<string, boolean>>({});
  const [rows, setRows] = useState<Row[]>([]);
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [status, setStatus] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const seq = useRef(0);

  useEffect(() => {
    const onOpen = (e: Event) => {const d = (e as CustomEvent).detail; if (d?.mode && d?.target) {setOpen({mode: d.mode, target: d.target}); setRows([]); setError('');}};
    window.addEventListener(CLEANUP_EVENT, onOpen);
    return () => window.removeEventListener(CLEANUP_EVENT, onOpen);
  }, []);

  const audioClips: ProjectAudioClip[] = (project.finishing_json || {}).audio_clips || [];
  const target = open?.target;
  const scene = target?.kind === 'scene' ? project.scenes.find(s => s.id === target.sceneId) : undefined;
  const sceneStart = useMemo(() => scene ? sequenceClips(project.scenes).find(c => c.scene.id === scene.id)?.start ?? 0 : 0, [project.scenes, scene?.id]);
  const targetClips = target?.kind === 'clips' ? audioClips.filter(c => target.ids.includes(c.id)) : [];
  const words = useMemo(() => [...terms.split(',').map(t => t.trim()).filter(Boolean), ...OPTIONAL_FILLERS.filter(w => optional[w])], [terms, optional]);
  const fillersUnavailable = open?.mode === 'fillers' && target?.kind === 'clips';

  // Detect (again) whenever the target or the settings change; stale answers are ignored.
  useEffect(() => {
    if (!open || fillersUnavailable) return;
    const id = ++seq.current;
    const t = setTimeout(() => void detect(id), 250);
    return () => clearTimeout(t);
  }, [open, params, words.join('|'), project.id]);

  async function detect(id: number) {
    if (!open) return;
    setBusy(true); setError(''); setStatus('Detecting…');
    try {
      let next: Row[] = [];
      if (open.mode === 'silence' && target?.kind === 'clips') {
        const assets = [...new Set(targetClips.map(c => c.asset_id))];
        const found: Record<string, SilenceResult> = {};
        for (const a of assets) found[a] = await cleanupApi.detectSilence({asset_id: a}, params);
        for (const c of targetClips) for (const [s, e] of mergeRanges(found[c.asset_id].ranges, c.source_in_ms, c.source_out_ms))
          next.push({key: `${c.id}:${s}`, clipId: c.id, label: `${clipTrack(c)} · ${c.name}`, source: [s, e], seekMs: c.start_ms + s - c.source_in_ms});
      } else if (open.mode === 'silence' && target?.kind === 'scene') {
        const r = await cleanupApi.detectSilence({scene_id: target.sceneId, source: target.source}, params);
        next = r.ranges.map((src, i) => {const sc = r.scene_ranges?.[i] ?? src; return {key: `s${i}`, label: target.source === 'narration' ? 'Narration' : 'Clip sound', source: src, scene: sc, seekMs: sceneStart + sc[0]};});
      } else if (open.mode === 'fillers' && target?.kind === 'scene') {
        const r: FillerResult = await cleanupApi.detectFillers(target.sceneId, target.source, words);
        next = r.matches.map(m => ({key: `f${m.index}`, label: `“${m.text}”`, source: [m.source_start_ms, m.source_end_ms], scene: [m.start_ms, m.end_ms], seekMs: sceneStart + m.start_ms, context: `${m.prev} [${m.text}] ${m.next}`.trim()}));
      }
      if (id !== seq.current) return;
      setRows(next); setChecked(Object.fromEntries(next.map(r => [r.key, true]))); setStatus('');
    } catch (e: any) {
      if (id !== seq.current) return;
      setRows([]); setStatus(''); setError(e?.message || 'Detection failed.');
    } finally {if (id === seq.current) setBusy(false);}
  }

  const picked = rows.filter(r => checked[r.key]);
  const savedMs = useMemo(() => {
    if (target?.kind === 'clips') return targetClips.reduce((sum, c) => sum + mergeRanges(picked.filter(r => r.clipId === c.id).map(r => r.source)).reduce((s, [a, b]) => s + b - a, 0), 0);
    return mergeRanges(picked.map(r => r.source)).reduce((s, [a, b]) => s + b - a, 0);
  }, [picked, target]);
  const what = open?.mode === 'fillers' ? 'filler word' : 'silence';
  const seek = (ms: number) => window.dispatchEvent(new CustomEvent(TIMELINE_SEEK_EVENT, {detail: {timeMs: Math.max(0, Math.round(ms))}}));

  async function apply() {
    if (!open || !target || !picked.length) return;
    const frame = frameMs(project.fps);
    setError('');
    if (target.kind === 'clips') {
      const r = jumpCuts(audioClips, target.ids, c => picked.filter(p => p.clipId === c.id).map(p => p.source), {frame});
      if (!r.ok) {setError(r.error); return;}
      await onUpdateAudioClips(r.clips);
    } else if (target.source === 'narration') {
      // Existing detach-to-A3 flow, then cut the new clip. Detach + cuts are one undo step.
      const ranges = picked.map(p => p.source);
      let failure = '';
      await onDetachNarration(target.sceneId, sceneStart, async clip => {
        const r = jumpCuts([clip], [clip.id], () => ranges, {frame, ripple: 'clip'});
        if (!r.ok) {failure = r.error; return [clip];}
        return r.clips;
      });
      if (failure) {setError(failure); return;}
    } else {
      if (!scene) return;
      const snapshot: Scene = scene, cuts = picked.map(p => p.scene ?? p.source);
      let created: string[] = [];
      await record(open.mode === 'fillers' ? 'remove filler words' : 'remove silences', async () => {
        for (const id of created) await api.deleteScene(id);
        await api.restoreScene(snapshot.id, snapshot); onScenesChanged?.(snapshot.id);
      }, async () => {
        const r = await cleanupApi.jumpCutScene(snapshot.id, cuts);
        created = r.scenes.slice(1).map(s => s.id); onScenesChanged?.(snapshot.id);
      });
    }
    setOpen(null);
  }

  if (!open || !target) return null;
  const title = target.kind === 'clips' ? `${targetClips.length} timeline audio clip${targetClips.length === 1 ? '' : 's'}`
    : `${scene?.title || 'Scene'} · ${target.source === 'narration' ? 'narration (A1)' : 'video clip sound'}`;
  const applyHint = target.kind === 'clips' ? 'Cuts the clip and closes the gaps; later clips on the track move left.'
    : target.source === 'narration' ? 'Moves the narration to A3, then cuts it there. The picture is unchanged.'
    : 'Splits the scene into consecutive scenes that keep only the remaining picture and sound.';
  return <aside className="cleanup-panel" role="dialog" aria-label="Clean up" onKeyDown={e => {if (e.key === 'Escape') setOpen(null);}}>
    <header><Scissors size={14}/><strong>Clean up</strong><span>{title}</span><button aria-label="Close clean up" onClick={() => setOpen(null)}><X size={14}/></button></header>
    <div className="cleanup-modes" role="tablist" aria-label="Clean up mode">
      {(['silence', 'fillers'] as const).map(m => <button key={m} role="tab" aria-selected={open.mode === m} disabled={m === 'fillers' && target.kind === 'clips'} title={m === 'fillers' && target.kind === 'clips' ? 'Filler words need a scene transcript: use it on a scene’s narration or clip sound.' : undefined} onClick={() => setOpen({...open, mode: m})}>{m === 'silence' ? 'Remove silences' : 'Remove filler words'}</button>)}
    </div>
    {open.mode === 'silence' ? <div className="cleanup-settings">
      <label>Threshold <input type="range" aria-label="Silence threshold" min={-60} max={-20} step={1} value={params.threshold_db} onChange={e => setParams({...params, threshold_db: Number(e.target.value)})}/><output>{params.threshold_db} dB</output></label>
      <label>Shortest silence <input type="range" aria-label="Shortest silence" min={200} max={3000} step={50} value={params.min_silence_ms} onChange={e => setParams({...params, min_silence_ms: Number(e.target.value)})}/><output>{params.min_silence_ms} ms</output></label>
      <label>Keep around speech <input type="range" aria-label="Padding around speech" min={0} max={500} step={10} value={params.padding_ms} onChange={e => setParams({...params, padding_ms: Number(e.target.value)})}/><output>{params.padding_ms} ms</output></label>
    </div> : <div className="cleanup-settings">
      <label className="cleanup-terms">Filler words <input aria-label="Filler words" value={terms} onChange={e => setTerms(e.target.value)} dir="auto"/></label>
      <span className="cleanup-optional">{OPTIONAL_FILLERS.map(w => <label key={w}><input type="checkbox" checked={!!optional[w]} onChange={e => setOptional({...optional, [w]: e.target.checked})}/> “{w}”</label>)}<small>Often meaningful, so off by default.</small></span>
    </div>}
    {fillersUnavailable && <p className="cleanup-error" role="alert">Filler words need a scene transcript. Right-click a scene’s narration or clip sound instead.</p>}
    {error && <p className="cleanup-error" role="alert">{error}</p>}
    <p className="cleanup-summary" aria-live="polite">{busy ? status || 'Detecting…' : `${picked.length} ${what}${picked.length === 1 ? '' : 's'} selected · ${picked.length} cut${picked.length === 1 ? '' : 's'} · saves ${secs(savedMs)}`}</p>
    <ul className="cleanup-list" aria-label={`Detected ${what}s`}>
      {rows.map(r => <li key={r.key}>
        <input type="checkbox" aria-label={`Remove ${r.label} at ${secs((r.scene ?? r.source)[0])}`} checked={!!checked[r.key]} onChange={e => setChecked({...checked, [r.key]: e.target.checked})}/>
        <button className="cleanup-seek" onClick={() => seek(r.seekMs)} title="Move the playhead here">
          <span>{r.label}</span><span className="cleanup-time">{secs((r.scene ?? r.source)[0])}–{secs((r.scene ?? r.source)[1])} · {secs(r.source[1] - r.source[0])}</span>
          {r.context && <small dir="auto">{r.context}</small>}
        </button>
      </li>)}
      {!busy && !rows.length && !error && !fillersUnavailable && <li className="cleanup-empty">No {what}s found with these settings.</li>}
    </ul>
    <footer>
      <small>{applyHint}</small>
      <button className="btn btn-primary" disabled={disabled || busy || !picked.length} onClick={() => void apply()}>Apply {picked.length} cut{picked.length === 1 ? '' : 's'}</button>
    </footer>
  </aside>;
}
