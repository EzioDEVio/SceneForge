import React, {useEffect, useMemo, useState} from 'react';
import {X, Upload, MonitorPlay, Smartphone, Square, Film, Music, Image as ImageIcon, Gauge, FileText, Info} from 'lucide-react';
import {api, type Project} from './api';
import {sceneDuration} from './duration';

type S = {resolution: string; fps: string | number; format: string; quality: string};
const PRESETS: {key: string; name: string; note: string; Icon: typeof Film; vertical?: boolean; s: S}[] = [
  {key: 'yt', name: 'YouTube', note: '1080p · 30 fps · H.264', Icon: MonitorPlay, s: {resolution: '1080p', fps: 'project', format: 'mp4_h264', quality: 'high'}},
  {key: 'yt4k', name: 'YouTube 4K', note: '2160p · H.264 High', Icon: MonitorPlay, s: {resolution: '4k', fps: 'project', format: 'mp4_h264', quality: 'high'}},
  {key: 'short', name: 'TikTok · Reels · Shorts', note: '1080×1920 · 30 fps', Icon: Smartphone, vertical: true, s: {resolution: '1080p', fps: 30, format: 'mp4_h264', quality: 'high'}},
  {key: 'ig', name: 'Instagram feed', note: '1080p · H.264', Icon: Square, s: {resolution: '1080p', fps: 30, format: 'mp4_h264', quality: 'standard'}},
  {key: 'small', name: 'Small file', note: '720p · H.265 · for sharing', Icon: Gauge, s: {resolution: '720p', fps: 'project', format: 'mp4_h265', quality: 'standard'}},
  {key: 'edit', name: 'For editing', note: 'ProRes MOV · large', Icon: Film, s: {resolution: 'project', fps: 'project', format: 'mov_prores', quality: 'high'}},
  {key: 'gif', name: 'Animated GIF', note: 'No sound · short clips', Icon: ImageIcon, s: {resolution: 'project', fps: 'project', format: 'gif', quality: 'standard'}},
  {key: 'mp3', name: 'Audio only', note: 'MP3 · voice and music', Icon: Music, s: {resolution: 'project', fps: 'project', format: 'mp3', quality: 'high'}},
];
// approximate video bitrate in Mbit/s at 1080p for each format / quality (for the size estimate)
const RATE: Record<string, number[]> = {mp4_h264: [3, 6, 9, 14], mp4_h265: [1.8, 3.5, 5.5, 9], webm: [2, 4, 6, 9], mov_prores: [45, 100, 145, 220], gif: [6, 8, 10, 14]};
const SHORT: Record<string, number> = {'720p': 720, '1080p': 1080, '1440p': 1440, '4k': 2160};

export function ExportDialog({project, onClose, onExport}: {project: Project; onClose: () => void; onExport: (s: S) => void}) {
  const vertical = project.height > project.width * 1.2;
  const [preset, setPreset] = useState(vertical ? 'short' : 'yt');
  const [s, setS] = useState<S>((PRESETS.find(p => p.key === (vertical ? 'short' : 'yt')) || PRESETS[0]).s);
  const [adv, setAdv] = useState(true);
  useEffect(() => {const esc = (e: KeyboardEvent) => e.key === 'Escape' && onClose(); window.addEventListener('keydown', esc); return () => window.removeEventListener('keydown', esc);}, [onClose]);
  const seconds = useMemo(() => project.scenes.filter(x => x.shots.length).reduce((a, x) => a + sceneDuration(x), 0) / 1000, [project]);
  const short = SHORT[s.resolution] || Math.min(project.width, project.height);
  const w = project.width >= project.height ? Math.round(short * project.width / project.height / 2) * 2 : short;
  const h = project.width >= project.height ? short : Math.round(short * project.height / project.width / 2) * 2;
  const q = ['draft', 'standard', 'high', 'max'].indexOf(s.quality);
  const mb = s.format === 'mp3' ? seconds * [128, 192, 256, 320][q] / 8 / 1000 : s.format === 'wav' ? seconds * 0.192 :
    seconds * ((RATE[s.format] || RATE.mp4_h264)[q] * (w * h) / (1920 * 1080) + 0.19) / 8;
  const pick = (k: string) => {const p = PRESETS.find(x => x.key === k)!; setPreset(k); setS(p.s);};
  const set = (p: Partial<S>) => {setPreset('custom'); setS(v => ({...v, ...p}));};
  const audio = s.format === 'mp3' || s.format === 'wav';
  return <div className="info-backdrop" onMouseDown={e => e.target === e.currentTarget && onClose()}>
    <div className="info-panel wide export-dialog" role="dialog" aria-modal="true" aria-label="Export video">
      <header><span className="info-title"><Upload size={18}/> Export video</span><button className="icon-reset info-close" aria-label="Close" onClick={onClose}><X size={16}/></button></header>
      <div className="info-body">
        <div className="export-presets" role="radiogroup" aria-label="Export preset">
          {PRESETS.map(p => <button key={p.key} role="radio" aria-checked={preset === p.key} className={`export-preset ${preset === p.key ? 'selected' : ''}`} onClick={() => pick(p.key)}>
            <p.Icon size={18}/><strong>{p.name}</strong><small>{p.note}</small>{p.vertical && !vertical && <em>Needs a 9:16 project</em>}</button>)}
        </div>
        <button className="text-btn" aria-expanded={adv} onClick={() => setAdv(a => !a)}>{adv ? '▾' : '▸'} Advanced settings</button>
        {adv && <div className="export-advanced">
          <label className="control-label">Resolution<select aria-label="Export resolution" value={s.resolution} disabled={audio} onChange={e => set({resolution: e.target.value})}>
            <option value="project">Project size ({project.width}×{project.height})</option><option value="720p">720p HD</option><option value="1080p">1080p Full HD</option><option value="1440p">1440p 2K</option><option value="4k">2160p 4K</option></select></label>
          <label className="control-label">Frame rate<select aria-label="Export frame rate" value={String(s.fps)} disabled={audio} onChange={e => set({fps: e.target.value === 'project' ? 'project' : Number(e.target.value)})}>
            <option value="project">Project ({project.fps} fps)</option>{[24, 25, 30, 50, 60].map(f => <option key={f} value={f}>{f} fps</option>)}</select></label>
          <label className="control-label">Format<select aria-label="Export format" value={s.format} onChange={e => set({format: e.target.value})}>
            <option value="mp4_h264">MP4 · H.264 (plays everywhere)</option><option value="mp4_h265">MP4 · H.265/HEVC (smaller files)</option><option value="webm">WebM · VP9 (web)</option>
            <option value="mov_prores">MOV · ProRes (for editing)</option><option value="gif">Animated GIF (no sound)</option><option value="mp3">MP3 (audio only)</option><option value="wav">WAV (audio only)</option></select></label>
          <label className="control-label">Quality<select aria-label="Export quality" value={s.quality} onChange={e => set({quality: e.target.value})}>
            <option value="draft">Draft · fast, small</option><option value="standard">Standard</option><option value="high">High</option><option value="max">Maximum · slow, large</option></select></label>
        </div>}
        <div className="export-summary">
          <span><Info size={13}/> {audio ? `Audio only · ${Math.round(seconds)} s` : `${s.format === 'gif' ? 'GIF' : `${w}×${h}`} · ${s.fps === 'project' ? project.fps : s.fps} fps · ${Math.round(seconds)} s`}</span>
          <span>About <b>{mb >= 1000 ? `${(mb / 1000).toFixed(1)} GB` : `${Math.max(1, Math.round(mb))} MB`}</b></span>
        </div>
        {s.resolution === '4k' && <p className="hint">4K takes longer and makes large files. It only looks sharper if your photos and videos are high resolution.</p>}
        {s.format === 'gif' && seconds > 20 && <p className="hint">GIFs get very large for long videos; they suit short clips (under about 15 s).</p>}
        <div className="export-captions"><FileText size={14}/> Caption files for YouTube and others:
          <a className="text-btn" href={api.captionsUrl(project.id, 'srt')} download>SRT</a><a className="text-btn" href={api.captionsUrl(project.id, 'vtt')} download>VTT</a>
          <span className="muted">Captions you styled are also burned into the video.</span></div>
        <div className="button-row export-actions"><button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={() => onExport(s)}><Upload size={14}/> Export</button></div>
      </div>
    </div>
  </div>;
}
