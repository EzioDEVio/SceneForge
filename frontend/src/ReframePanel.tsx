import React, {useEffect, useRef, useState} from 'react';
import {Smartphone, X} from 'lucide-react';
import {reframeApi, type Project, type ReframeJob, type Shot, type Reframe} from './api';

/** File → "Create vertical 9:16 version (auto-reframe)": copies the project to 9:16 and lets
 * every clip follow its main subject (backend render/reframe.py). The original is not changed. */
export function ReframeProjectDialog({project, onClose, onOpen}: {project: Project; onClose: () => void; onOpen: (projectId: string) => void}) {
  const [job, setJob] = useState<ReframeJob | null>(null);
  const [error, setError] = useState('');
  const [starting, setStarting] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const shots = project.scenes.reduce((a, s) => a + s.shots.length, 0);
  const vertical = project.height > project.width;
  const running = job?.status === 'running';
  useEffect(() => () => {if (timer.current) clearInterval(timer.current);}, []);
  useEffect(() => {const esc = (e: KeyboardEvent) => e.key === 'Escape' && !running && onClose(); window.addEventListener('keydown', esc); return () => window.removeEventListener('keydown', esc);});
  async function start() {
    setError(''); setStarting(true);
    try {
      const r = await reframeApi.start(project.id, '9:16');
      setJob({job_id: r.job_id, project_id: r.project_id, source_project_id: project.id, status: 'running', stage: 'starting', progress: 0, done: 0, total: r.total, warnings: [], error: null});
      timer.current = setInterval(async () => {
        try {
          const j = await reframeApi.job(r.job_id);
          if (!j) return;
          setJob(j);
          if (j.status !== 'running' && timer.current) {clearInterval(timer.current); timer.current = null;}
        } catch (e: any) {setError(e.message);}
      }, 700);
    } catch (e: any) {setError(e.message);} finally {setStarting(false);}
  }
  return <div className="info-backdrop" onMouseDown={e => e.target === e.currentTarget && !running && onClose()}>
    <div className="info-panel reframe-dialog" role="dialog" aria-modal="true" aria-label="Create vertical version">
      <header><span className="info-title"><Smartphone size={18}/> Create vertical 9:16 version</span><button className="icon-reset info-close" aria-label="Close" disabled={running} onClick={onClose}><X size={16}/></button></header>
      <div className="info-body">
        <p>Makes a <b>copy</b> of “{project.title}” in 9:16 for TikTok, Reels and Shorts. For each of the {shots} clip{shots === 1 ? '' : 's'}, SceneForge finds the main subject and moves the vertical crop to follow it (auto-reframe). Your original project is not changed.</p>
        <p className="hint">Works best when there is one main subject. With several people it follows the largest one; you can switch any clip to Center or a manual position under Motion → Reframe.</p>
        {vertical && <p className="hint">This project is already vertical; the copy will re-frame its clips for 9:16 again.</p>}
        {job && <div className="reframe-progress" role="status" aria-label="Reframe progress">
          <progress max={100} value={job.progress} aria-label="Auto-reframe progress"/>
          <span>{job.status === 'running' ? `${job.stage} · ${job.progress}%` : job.status === 'succeeded' ? `Done: ${job.total} clip${job.total === 1 ? '' : 's'} reframed.` : job.status === 'cancelled' ? 'Cancelled. The copy keeps the clips that were finished.' : 'Reframing failed.'}</span>
        </div>}
        {!!job?.warnings?.length && <ul className="hint" aria-label="Reframe notes">{job.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>}
        {(error || job?.error) && <p role="alert">{error || job?.error?.split('\n')[0]}</p>}
        <div className="button-row">
          {!job && <><button className="btn" onClick={onClose}>Cancel</button><button className="btn btn-primary" disabled={starting || !shots} onClick={() => void start()}><Smartphone size={14}/> Create vertical 9:16 version (auto-reframe)</button></>}
          {running && <button className="btn" onClick={() => void reframeApi.cancel(job!.job_id)}>Stop</button>}
          {job && !running && <><button className="btn" onClick={onClose}>Stay here</button><button className="btn btn-primary" onClick={() => onOpen(job.project_id)}>Open vertical project</button></>}
        </div>
        {!shots && <p className="hint">Add pictures or video clips first.</p>}
      </div>
    </div>
  </div>;
}

const MODES: [Reframe['mode'], string][] = [['center', 'Center'], ['follow', 'Follow subject'], ['manual', 'Manual']];

/** Per-clip reframe override (shown in Motion → Crop & focal zoom). */
export function ShotReframe({shot, save}: {shot: Shot; save: (f: () => Promise<unknown>) => Promise<boolean>}) {
  const r = shot.crop_json?.reframe;
  const [x, setX] = useState(Math.round((r?.x ?? 0.5) * 100));
  const [busy, setBusy] = useState(false);
  useEffect(() => setX(Math.round((r?.x ?? 0.5) * 100)), [shot.id, r?.x]);
  const set = async (body: Parameters<typeof reframeApi.setShot>[1]) => {setBusy(true); try {await save(() => reframeApi.setShot(shot.id, body));} finally {setBusy(false);}};
  const mode = r?.mode;
  return <div className="shot-reframe" role="group" aria-label="Reframe">
    <div className="fit-choice"><span>Reframe for other shapes</span>
      <div className="segmented" role="radiogroup" aria-label="Reframe mode">
        {MODES.map(([m, label]) => <button key={m} role="radio" aria-checked={mode === m} className={mode === m ? 'selected' : ''} disabled={busy} onClick={() => void set(m === 'manual' ? {mode: m, x: x / 100} : {mode: m})}>{label}</button>)}
      </div>
      <p className="hint">{busy ? 'Working… finding the subject takes a few seconds per clip.' : !r ? 'Off: the frame is cut from the centre. Follow subject finds the main subject and keeps it in a narrower frame (works best with one main subject).'
        : mode === 'follow' ? `Following the subject${r.method === 'matte' ? ' (cutout matte)' : r.method === 'face' ? ' (face)' : ' — none found, stays centred'} · ${r.track?.length || 0} keyframe${r.track?.length === 1 ? '' : 's'}. Render to check.`
        : mode === 'manual' ? 'Fixed horizontal position for the crop window.' : 'Centred crop window.'}</p>
      {mode === 'manual' && <label className="range-control">Reframe position<div><input aria-label="Reframe position slider" type="range" min={0} max={100} step={1} value={x} onChange={e => setX(+e.target.value)} onPointerUp={e => void set({mode: 'manual', x: +e.currentTarget.value / 100})} onKeyUp={e => void set({mode: 'manual', x: +e.currentTarget.value / 100})}/><span>{x}%</span></div></label>}
      {r && <div className="button-row">{mode === 'follow' && <button className="text-btn" disabled={busy} onClick={() => void set({mode: 'follow', reanalyze: true})}>Re-analyse clip</button>}<button className="text-btn" disabled={busy} onClick={() => void set({mode: 'off'})}>Turn reframe off</button></div>}
    </div>
  </div>;
}
