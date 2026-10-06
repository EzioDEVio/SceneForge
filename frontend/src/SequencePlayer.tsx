import {LayerPreview} from "./TimelineLayers";
import React, {useEffect, useMemo, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {Clapperboard, X} from 'lucide-react';
import {api, Project, Scene} from './api';

// Live timeline playback: plays the sequence scene by scene from each scene's rendered part
// (GET /api/scenes/{id}/preview-media, which has the timeline audio and music mixed under it),
// without rendering the full video. Two <video> elements alternate: the next rendered scene is
// preloaded in the idle one and swapped in at the cut. Transitions are hard cuts here: a scene
// plays until the next scene's start on the timeline (the start of the transition overlap).
// Scenes that are not rendered, or changed since their render, show a still for their length.

export type LiveClip = {scene: Scene; start: number; duration: number; overlap: number; end: number};
export type LiveStatus = 'ready' | 'stale' | 'unrendered' | 'empty';
export type LiveSegment = {scene: Scene; start: number; end: number; cutAt: number; status: LiveStatus; url: string | null; still: string | null};

function hashText(text: string) {let h = 0; for (let i = 0; i < text.length; i++) h = (h * 31 + text.charCodeAt(i)) | 0; return (h >>> 0).toString(36);}
/** Same cache key the scene editor uses for its rendered preview (App.tsx previewMixKey). */
export function previewMixKey(project: Project, scene: Scene) {
  return `${scene.rendered_asset_id}:${hashText(JSON.stringify([project.finishing_json?.audio_clips || [], project.finishing_json?.music || null, project.finishing_json?.timeline?.tracks || {}, project.scenes.map(s => [s.id, s.revision])]))}`;
}
export function liveStatus(scene: Scene): LiveStatus {
  if (!scene.shots.length) return 'empty';
  if (!scene.rendered_asset_id) return 'unrendered';
  return scene.is_stale ? 'stale' : 'ready';
}
export function liveSegments(project: Project, clips: LiveClip[]): LiveSegment[] {
  return clips.map((c, i) => {
    const status = liveStatus(c.scene), shot = c.scene.shots[0];
    const next = clips[i + 1];
    return {scene: c.scene, start: c.start, end: c.end, cutAt: next ? Math.max(c.start, Math.min(c.end, next.start)) : c.end, status,
      url: status === 'ready' ? api.scenePreviewUrl(c.scene.id, previewMixKey(project, c.scene)) : null,
      still: shot?.asset && shot.asset.type !== 'audio' ? api.assetThumbUrl(shot.asset_id, 960, shot.source_in_ms || 0) : null};
  });
}
/** Index of the segment that plays at timeline time `ms`. */
export function segmentAt(segs: LiveSegment[], ms: number) {
  for (let i = segs.length - 1; i >= 0; i--) if (ms >= segs[i].start - 0.5) return i;
  return 0;
}

type RenderQueue = {total: number; done: number; title: string; progress: number; stage: string; error?: string};

export function SequencePlayer({project, clips, host, playing, rate, seekRequest, onTime, onPlayingChange, onClose, onRefresh}: {
  project: Project; clips: LiveClip[]; host: HTMLElement; playing: boolean; rate: number; seekRequest: {ms: number; n: number};
  onTime: (ms: number) => void; onPlayingChange: (playing: boolean) => void; onClose: () => void; onRefresh?: () => Promise<unknown> | void;
}) {
  const segs = useMemo(() => liveSegments(project, clips), [project, clips]);
  const segsRef = useRef(segs); segsRef.current = segs;
  const length = segs[segs.length - 1]?.end || 0;
  const videos = [useRef<HTMLVideoElement>(null), useRef<HTMLVideoElement>(null)];
  const [previewTime,setPreviewTime]=useState(seekRequest.ms);
  const [active, setActive] = useState(0);
  const [index, setIndex] = useState(() => segmentAt(segs, seekRequest.ms));
  const st = useRef({active: 0, index: segmentAt(segs, seekRequest.ms), loaded: ['', ''] as string[], time: seekRequest.ms, wall: 0, wallMs: 0, raf: 0, lastEmit: 0, playing: false, rate: 1});
  const [error, setError] = useState('');
  const [queue, setQueue] = useState<RenderQueue | null>(null);
  const cancelled = useRef(false), jobRef = useRef<string | null>(null);
  const missing = segs.filter(s => s.status === 'stale' || s.status === 'unrendered');
  const emit = (ms: number, force = false) => {
    const s = st.current; s.time = ms;
    const now = performance.now();
    if (force || now - s.lastEmit > 40) {s.lastEmit = now; setPreviewTime(ms); onTime(Math.max(0, Math.min(length, ms)));}
  };
  function load(slot: number, url: string) {
    const v = videos[slot].current; if (!v) return;
    if (st.current.loaded[slot] !== url) {st.current.loaded[slot] = url; v.src = url; v.preload = 'auto';}
  }
  function preloadNext() {
    const s = st.current, next = segsRef.current[s.index + 1];
    if (next?.status === 'ready' && next.url) load(1 - s.active, next.url);
  }
  function playVideo(v: HTMLVideoElement) {
    v.playbackRate = st.current.rate;
    try {const p = v.play(); if (p && typeof p.catch === 'function') p.catch(() => {/* paused or not loaded yet */});} catch {/* media unavailable */}
  }
  /** Show segment i at local time `localMs`, continuing playback when playing. */
  function goTo(i: number, localMs: number) {
    const s = st.current, seg = segsRef.current[i];
    if (!seg) return;
    s.index = i; setIndex(i); setError('');
    videos.forEach(r => r.current?.pause());
    if (seg.status === 'ready' && seg.url) {
      let slot = s.active;
      if (s.loaded[slot] !== seg.url && s.loaded[1 - slot] === seg.url) slot = 1 - slot;   // preloaded: swap
      s.active = slot; setActive(slot);
      load(slot, seg.url);
      const v = videos[slot].current!;
      const apply = () => {try {v.currentTime = Math.max(0, localMs) / 1000;} catch {/* not seekable yet */}};
      if (v.readyState >= 1) apply(); else v.addEventListener('loadedmetadata', apply, {once: true});
      if (s.playing) playVideo(v);
    }
    s.wall = performance.now(); s.wallMs = seg.start + Math.max(0, localMs);
    emit(seg.start + Math.max(0, localMs), true);
    preloadNext();
  }
  function advance() {
    const s = st.current, next = s.index + 1;
    if (next >= segsRef.current.length) {emit(length, true); stop(); onPlayingChange(false); return;}
    goTo(next, 0);
  }
  function tick() {
    const s = st.current; if (!s.playing) return;
    const seg = segsRef.current[s.index];
    if (seg) {
      let t: number;
      const v = videos[s.active].current;
      // A rendered scene's clock is its video (held while it is still loading).
      if (seg.status === 'ready' && v && s.loaded[s.active] === seg.url) t = v.readyState >= 1 ? seg.start + v.currentTime * 1000 : s.time;
      else t = s.wallMs + (performance.now() - s.wall) * s.rate;
      if (t >= seg.cutAt - 1) {advance(); if (!st.current.playing) return;}
      else emit(t);
    }
    s.raf = requestAnimationFrame(tick);
  }
  function stop() {const s = st.current; s.playing = false; cancelAnimationFrame(s.raf); videos.forEach(r => r.current?.pause());}
  // Seeks from the ruler, J/K/L, scene buttons and Play.
  useEffect(() => {const i = segmentAt(segsRef.current, seekRequest.ms); goTo(i, seekRequest.ms - (segsRef.current[i]?.start || 0));}, [seekRequest.n]);
  useEffect(() => {
    const s = st.current; s.rate = rate;
    videos.forEach(r => {if (r.current) r.current.playbackRate = rate;});
    s.wallMs = s.time; s.wall = performance.now();
  }, [rate]);
  useEffect(() => {
    const s = st.current;
    if (playing && !s.playing) {
      s.playing = true;
      const seg = segsRef.current[s.index];
      if (s.time >= length - 1) {goTo(0, 0);}
      else if (seg?.status === 'ready') {const v = videos[s.active].current; if (v) playVideo(v);}
      s.wall = performance.now(); s.wallMs = s.time;
      s.raf = requestAnimationFrame(tick);
    } else if (!playing && s.playing) {stop(); emit(s.time, true);}
  }, [playing]);
  // A scene finished rendering (or changed): show it at the current time.
  const statusKey = segs.map(s => `${s.scene.id}:${s.status}:${s.url}`).join('|');
  const firstStatus = useRef(statusKey);
  useEffect(() => {
    if (firstStatus.current === statusKey) return; firstStatus.current = statusKey;
    const s = st.current, i = segmentAt(segsRef.current, s.time); goTo(i, s.time - (segsRef.current[i]?.start || 0));
  }, [statusKey]);
  useEffect(() => () => {stop(); cancelled.current = true;}, []);

  async function renderMissing() {
    const ids = missing.map(s => s.scene.id);
    if (!ids.length) return;
    cancelled.current = false;
    for (let i = 0; i < ids.length && !cancelled.current; i++) {
      const scene = project.scenes.find(s => s.id === ids[i]);
      setQueue({total: ids.length, done: i, title: scene?.title || 'Scene', progress: 0, stage: 'Queued'});
      try {
        const {job_id} = await api.renderPart(ids[i]); jobRef.current = job_id;
        let job = await api.getJob(job_id);
        while (!['succeeded', 'failed', 'cancelled'].includes(job.status) && !cancelled.current) {
          setQueue(q => q && {...q, progress: Math.round(job.progress || 0), stage: job.stage || 'Rendering'});
          await new Promise(r => setTimeout(r, 1000));
          job = await api.getJob(job_id);
        }
        if (job.status !== 'succeeded') {if (!cancelled.current) setQueue(q => q && {...q, error: job.error || `Render ${job.status}.`}); jobRef.current = null; return;}
        jobRef.current = null;
        await onRefresh?.();
      } catch (e: any) {setQueue(q => q && {...q, error: e?.message || String(e)}); jobRef.current = null; return;}
    }
    setQueue(null);
  }
  function cancelQueue() {cancelled.current = true; if (jobRef.current) void api.cancelJob(jobRef.current).catch(() => {}); jobRef.current = null; setQueue(null);}

  const seg = segs[index];
  const message = seg?.status === 'empty' ? 'Empty part — add media (skipped on export)'
    : seg?.status === 'stale' ? 'Changed since its last render — render this scene to see it here'
    : seg?.status === 'unrendered' ? 'Not rendered — render this scene' : '';
  return createPortal(<div className="program-monitor live-monitor" role="region" aria-label="Live timeline playback">
    <header>
      <strong>Timeline playback</strong>
      <span className="live-note">Preview: transitions show as cuts — Render full video for the exact result</span>
      {queue ? <><span role="status">{queue.error ? `Render stopped: ${queue.error}` : `Rendering ${queue.done + 1} of ${queue.total} · ${queue.title} · ${queue.progress}%`}</span><button onClick={cancelQueue}>{queue.error ? 'Dismiss' : 'Cancel'}</button></>
        : missing.length > 0 && <button title="Render the scenes that are new or changed, one at a time" onClick={() => void renderMissing()}><Clapperboard size={13}/> Render missing scenes ({missing.length})</button>}
      <button aria-label="Close timeline playback" onClick={() => {stop(); onClose();}}><X size={16}/></button>
    </header>
    <div className="live-stage">
      <div className="live-layer-frame" style={{aspectRatio:`${project.width}/${project.height}`,"--live-aspect":project.width/project.height} as React.CSSProperties}><LayerPreview project={project} time={previewTime} playing={playing} rate={rate}/></div>
      {[0, 1].map(slot => <video key={slot} ref={videos[slot]} data-slot={slot} className={slot === active && seg?.status === 'ready' ? 'active' : ''} aria-hidden={slot !== active || seg?.status !== 'ready'} playsInline preload="auto"
        onEnded={() => {if (slot === st.current.active && st.current.playing) advance();}}
        onError={() => {if (slot === st.current.active && segsRef.current[st.current.index]?.status === 'ready') setError('This scene\'s preview could not be loaded. Render the scene again and retry.');}}/>)}
      {seg && seg.status !== 'ready' && <div className="live-card" data-status={seg.status}>{seg.still && <img src={seg.still} alt=""/>}<p>{seg.scene.title} · {message}</p>{seg.status !== 'empty' && !queue && <button onClick={() => void renderMissing()}>Render missing scenes</button>}</div>}
    </div>
    {error && <p role="alert">{error}</p>}
    <footer><span aria-live="polite">Scene {index + 1} of {segs.length} · {seg?.scene.title}</span>{queue && !queue.error && <progress max={100} value={queue.progress} aria-label="Scene render progress"/>}</footer>
  </div>, host);
}
