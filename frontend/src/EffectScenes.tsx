import React, {useEffect, useState} from 'react';
import {X, Timer} from 'lucide-react';

type Opts = {style: 'film' | 'modern' | 'minimal'; seconds: number; beep: 'each' | 'two-pop' | 'none'; tone: 'bw' | 'sepia'; color: string};
const STYLES: {key: Opts['style']; name: string; note: string}[] = [
  {key: 'film', name: 'Film leader', note: 'Classic cinema countdown with wedge, circles, grain, scratches and projector sound'},
  {key: 'modern', name: 'Modern', note: 'Dark with a glowing ring and popping numbers'},
  {key: 'minimal', name: 'Minimal', note: 'Clean white numbers on black'},
];

/** Insert a cinema countdown as its own scene (picture + sound). */
export function CountdownDialog({onClose, onInsert, selectedTitle}: {onClose: () => void; onInsert: (o: Opts, where: 'start' | 'after') => Promise<void>; selectedTitle?: string}) {
  const [o, setO] = useState<Opts>({style: 'film', seconds: 5, beep: 'each', tone: 'bw', color: '#8F7CF0'});
  const [where, setWhere] = useState<'start' | 'after'>('start');
  const [busy, setBusy] = useState(false);
  useEffect(() => {const esc = (e: KeyboardEvent) => e.key === 'Escape' && !busy && onClose(); window.addEventListener('keydown', esc); return () => window.removeEventListener('keydown', esc);}, [busy, onClose]);
  const set = (p: Partial<Opts>) => setO(v => ({...v, ...p}));
  return <div className="info-backdrop" onMouseDown={e => e.target === e.currentTarget && !busy && onClose()}>
    <div className="info-panel" role="dialog" aria-modal="true" aria-label="Insert countdown">
      <header><span className="info-title"><Timer size={18}/> Insert countdown</span><button className="icon-reset info-close" aria-label="Close" disabled={busy} onClick={onClose}><X size={16}/></button></header>
      <div className="info-body">
        <div className="countdown-styles" role="radiogroup" aria-label="Countdown style">
          {STYLES.map(s => <button key={s.key} role="radio" aria-checked={o.style === s.key} className={`countdown-style ${o.style === s.key ? 'selected' : ''}`} onClick={() => set({style: s.key})}>
            <span className={`countdown-thumb ${s.key} ${s.key === 'film' && o.tone === 'sepia' ? 'sepia' : ''}`} style={s.key === 'modern' ? {['--ring' as any]: o.color} : undefined}><b>3</b></span>
            <strong>{s.name}</strong><small>{s.note}</small></button>)}
        </div>
        <div className="countdown-options">
          <label className="control-label">Length<select aria-label="Countdown length" value={o.seconds} onChange={e => set({seconds: Number(e.target.value)})}>{[3, 4, 5, 6, 7, 8, 9, 10].map(n => <option key={n} value={n}>{n} seconds (counts {n} → 2)</option>)}</select></label>
          <label className="control-label">Beeps<select aria-label="Countdown beeps" value={o.beep} onChange={e => set({beep: e.target.value as Opts['beep']})}>
            <option value="each">A beep on every number</option><option value="two-pop">Classic “2-pop” only</option><option value="none">Silent (projector only for film)</option></select></label>
          {o.style === 'film' && <label className="control-label">Tone<select aria-label="Countdown tone" value={o.tone} onChange={e => set({tone: e.target.value as Opts['tone']})}><option value="bw">Black & white</option><option value="sepia">Sepia</option></select></label>}
          {o.style === 'modern' && <label className="control-label">Ring colour<input type="color" aria-label="Countdown ring colour" value={o.color} onChange={e => set({color: e.target.value.toUpperCase()})}/></label>}
          <label className="control-label">Insert<select aria-label="Countdown position" value={where} onChange={e => setWhere(e.target.value as 'start' | 'after')}>
            <option value="start">At the start of the video</option>{selectedTitle && <option value="after">After “{selectedTitle}”</option>}</select></label>
        </div>
        <p className="muted">The countdown becomes its own scene: you can move, trim, duplicate or add effects to it. Its sound goes on the Narration lane with its own volume. The last second is black, so your picture starts exactly 2 s after the “2”, like a real film leader.</p>
        <div className="button-row"><button className="btn" disabled={busy} onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy} onClick={async () => {setBusy(true); try {await onInsert(o, where);} finally {setBusy(false);}}}>{busy ? 'Creating countdown…' : 'Insert countdown'}</button></div>
      </div>
    </div>
  </div>;
}
