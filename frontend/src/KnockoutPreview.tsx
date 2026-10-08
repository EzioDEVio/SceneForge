import React, {useEffect, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {api} from './api';

type Settings = Parameters<typeof api.knockoutTitle>[1];
/** A real isolated render. Saved scene settings only change through the Add button. */
export function KnockoutPreview({sceneId, settings, disabled}: {sceneId: string; settings: Settings; disabled: boolean}) {
  const [open, setOpen] = useState(false), [starting, setStarting] = useState(false);
  const [jobId, setJobId] = useState(''), [job, setJob] = useState<any>(null), [error, setError] = useState('');
  const [signature, setSignature] = useState(''), [retry, setRetry] = useState(0);
  const ticket = useRef(0), activeJob = useRef('');
  const current = JSON.stringify(settings);
  // Inside the Video inside text dialog the rendered preview shows in the dialog, not behind it.
  const host = document.querySelector('.creative-studio [data-companion-preview]') || document.querySelector('.scene-editor:not([hidden]) [data-companion-preview]');
  const running = starting || !!jobId && (!job || ['queued', 'running', 'cancelling'].includes(job.status));
  useEffect(() => () => {ticket.current++; if (activeJob.current) void api.cancelJob(activeJob.current).catch(() => {});}, [sceneId]);
  useEffect(() => {
    if (!jobId) return;
    let live = true, checking = false;
    const controller = new AbortController();
    const poll = async () => {
      if (checking || !live) return; checking = true;
      const limit = setTimeout(() => controller.abort(), 10000);
      try {const next = await api.getJob(jobId, controller.signal); if (live) {setJob(next); setError(''); if (['succeeded','failed','cancelled'].includes(next.status)) {activeJob.current = ''; clearInterval(timer);}}}
      catch {if (live) setError('Cannot check the preview. Retry the connection or close it.');}
      finally {clearTimeout(limit); checking = false;}
    };
    void poll(); const timer = setInterval(() => {if (!controller.signal.aborted) void poll();}, 1000);
    return () => {live = false; controller.abort(); clearInterval(timer);};
  }, [jobId, retry]);
  async function close() {
    ticket.current++; setOpen(false); setJobId(''); setJob(null); setStarting(false);
    if (activeJob.current) {const id = activeJob.current; activeJob.current = ''; try {await api.cancelJob(id);} catch {setError('Could not stop the preview. Check active jobs.');}}
  }
  async function render() {
    const n = ++ticket.current, before = current;
    setStarting(true); setOpen(true); setJob(null); setJobId(''); setError('');
    try {
      const result = await api.previewKnockoutTitle(sceneId, settings);
      if (n !== ticket.current) {void api.cancelJob(result.job_id).catch(() => {}); return;}
      activeJob.current = result.job_id; setJobId(result.job_id); setSignature(before);
    } catch (e: any) {if (n === ticket.current) setError(e.message);}
    finally {if (n === ticket.current) setStarting(false);}
  }
  const ready = job?.status === 'succeeded' && job.artifact_asset_id;
  const status = error || (job?.status === 'failed' && (job.error || 'Preview failed. Try again.')) || (job?.status === 'cancelled' && 'Preview stopped.') || (starting ? 'Starting preview…' : `${job?.stage || 'Rendering scene'} · ${Math.round(job?.progress || 0)}%`);
  const view = <section className="companion-preview" aria-label="Video inside text preview">
    <header><strong>Video inside text · preview</strong><button aria-label="Close video inside text preview" onClick={() => void close()}>×</button></header>
    <div className="draft-media-frame">{ready ? <video controls preload="auto" aria-label="Rendered video inside text preview" src={api.assetStreamUrl(job.artifact_asset_id)} onError={() => setError('The preview video could not load. Try again.')}/> : <p role="status">{status}</p>}</div>
    {ready && signature !== current && <p role="status">Settings changed · render again to update.</p>}
    <p className="hint">Draft only · your saved scene stays unchanged until you add the title. Optional AI subject cutout runs after Add.</p>
    {error && <button className="btn" onClick={() => setRetry(n => n + 1)}>Retry preview connection</button>}
  </section>;
  return <><button className="btn" disabled={disabled || running} onClick={() => void render()}>Preview video inside text</button>{open && (host ? createPortal(view, host) : view)}</>;
}
