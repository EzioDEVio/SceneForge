import React, {useEffect, useRef, useState} from 'react';
import {X, Clapperboard, Film} from 'lucide-react';

const STAGES: Record<string, string> = {
  queued: 'Waiting to start…', visual: 'Rendering the picture', captions_audio: 'Adding captions and mixing sound', finalize: 'Finishing the scene',
  export: 'Joining scenes and transitions', 'compositing export': 'Joining scenes and transitions', delivery: 'Writing your chosen format and quality', finishing: 'Music and loudness', done: 'Done', cancelling: 'Cancelling…',
};
const fmt = (s: number) => s >= 3600 ? `${Math.floor(s / 3600)}h ${Math.floor(s % 3600 / 60)}m` : s >= 60 ? `${Math.floor(s / 60)}m ${Math.round(s % 60)}s` : `${Math.max(0, Math.round(s))}s`;

/** Modern progress for renders and exports: stage in plain words, animated bar, percent,
 *  elapsed time, estimated time left, and cancel. `floating` pins it to the corner. */
export function ProgressCard({title, stage, progress, status, onCancel, floating}: {title: string; stage?: string | null; progress: number; status?: string; onCancel?: () => void; floating?: boolean}) {
  const started = useRef(Date.now());
  const [now, setNow] = useState(Date.now());
  useEffect(() => {const id = setInterval(() => setNow(Date.now()), 500); return () => clearInterval(id);}, []);
  const p = Math.max(0, Math.min(100, progress || 0));
  const elapsed = (now - started.current) / 1000;
  const eta = p > 3 && p < 100 ? elapsed * (100 - p) / p : null;
  const label = status === 'cancelling' ? STAGES.cancelling : (stage && STAGES[stage]) || stage || 'Working…';
  const Icon = floating ? Film : Clapperboard;
  return <div className={`progress-card ${floating ? 'floating' : ''}`} role="progressbar" aria-label={title} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(p)} aria-valuetext={`${label}, ${Math.round(p)}%`}>
    <div className="pc-head"><span className="pc-icon"><Icon size={15}/></span>
      <div className="pc-titles"><strong>{title}</strong><span>{label}</span></div>
      <span className="pc-pct">{Math.round(p)}%</span>
      {onCancel && status !== 'cancelling' && <button className="icon-reset pc-cancel" aria-label={`Cancel ${title.toLowerCase()}`} title="Cancel" onClick={onCancel}><X size={14}/></button>}
    </div>
    <div className="pc-track"><div className="pc-fill" style={{width: `${Math.max(p, 2)}%`}}><span className="pc-shimmer"/></div></div>
    <div className="pc-meta"><span>Elapsed {fmt(elapsed)}</span><span>{eta !== null ? `About ${fmt(eta)} left` : p >= 100 ? 'Finishing up' : 'Estimating time…'}</span></div>
  </div>;
}
