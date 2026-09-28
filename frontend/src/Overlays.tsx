import React, {useEffect, useRef, useState} from 'react';
import {Plus, Trash2, Copy, ArrowUp, ArrowDown, Upload, PictureInPicture2, Search, Sticker} from 'lucide-react';
import {api, Asset, Overlay, Scene} from './api';
import {FeatureHelp} from './FeatureHelp';

export const OVERLAY_DEFAULTS: Omit<Overlay, 'id' | 'asset_id'> = {
  x: 72, y: 30, width: 34, rotation: 0, opacity: 100, radius: 6, border: 6, border_color: '#FFFFFF', shadow: 60, feather: 0, chroma: null, chroma_similarity: 30, x2: null, y2: null,
  start_ms: 0, end_ms: null, anim_in: 'fade', anim_out: 'fade', anim_ms: 600,
};
const ANIMS: [Overlay['anim_in'], string][] = [['none', 'None'], ['fade', 'Fade'], ['slide_left', 'Slide'], ['slide_up', 'Rise'], ['zoom', 'Zoom pop']];
const newId = () => 'ov' + Math.random().toString(36).slice(2, 9);
const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));
const STICKERS = [
  ['😀','Grinning face','reaction happy smile'],['😂','Laughing','reaction funny tears'],['🥳','Party','celebration confetti'],['😍','Heart eyes','reaction love'],['😮','Wow','reaction surprised'],['🤔','Thinking','reaction question'],['😎','Cool','reaction sunglasses'],['😭','Crying','reaction sad'],['👏','Clap','hands applause'],['👍','Thumbs up','hands approve'],['👎','Thumbs down','hands dislike'],['❤️','Heart','love symbol'],['🔥','Fire','trending hot'],['✨','Sparkles','magic shine'],['⭐','Star','rating favorite'],['💯','100','perfect score'],['✅','Check','done correct'],['❌','Cross','wrong no'],['⚠️','Warning','alert caution'],['❓','Question','help ask'],['💡','Idea','light bulb tip'],['🎉','Confetti','party celebration'],['🎬','Movie','film video'],['🎵','Music','sound audio'],['📍','Pin','location map'],['🚀','Rocket','launch fast'],['💬','Speech bubble','comment message'],['👀','Eyes','look watch'],['🙏','Thanks','please hands'],['💪','Strong','muscle power'],['🌟','Glow star','star shine'],['☀️','Sun','weather bright'],['🌈','Rainbow','color pride'],['🧠','Brain','think smart'],['💰','Money','cash finance'],['🎯','Target','goal focus'],['🏆','Trophy','winner award'],['☕','Coffee','drink break'],['🍿','Popcorn','movie snack'],['🐱','Cat','animal pet'],['🐶','Dog','animal pet'],['🦋','Butterfly','nature'],['🌸','Blossom','flower spring'],['💖','Sparkling heart','love heart'],['🚨','Siren','alert urgent'],['🛑','Stop','halt'],['▶️','Play','video start'],['⏸️','Pause','video stop'],
].map(([emoji,name,tags])=>({emoji,name,tags}));

function useProjectMedia(projectId: string) {
  const [media, setMedia] = useState<Asset[]>([]);
  useEffect(() => {api.listAssets(projectId).then(a => setMedia(a.filter(x => x.type === 'image' || x.type === 'video'))).catch(() => {});}, [projectId]);
  return [media, setMedia] as const;
}

/** Overlays drawn over the editor preview. Drag to move; drag the corner
 *  handle to resize (keeps the centre). Changes are live, saved on release. */
export function OverlayCanvas({overlays, frameAspect, selected, onSelect, onChange, onCommit}: {
  overlays: Overlay[]; frameAspect: number; selected: number; onSelect: (i: number) => void;
  onChange: (i: number, patch: Partial<Overlay>, commit?: boolean) => void; onCommit: () => void;
}) {
  const [media] = useProjectMediaFromOverlays(overlays);
  const box = useRef<HTMLDivElement>(null);
  function drag(i: number, mode: 'move' | 'resize', e: React.PointerEvent) {
    e.preventDefault(); e.stopPropagation(); onSelect(i);
    const rect = box.current!.getBoundingClientRect();
    const o = overlays[i], sx = e.clientX, sy = e.clientY;
    const move = (ev: PointerEvent) => {
      if (mode === 'move') onChange(i, {x: +clamp(o.x + (ev.clientX - sx) / rect.width * 100, -20, 120).toFixed(2), y: +clamp(o.y + (ev.clientY - sy) / rect.height * 100, -20, 120).toFixed(2)});
      else {
        const cx = rect.left + rect.width * o.x / 100;
        onChange(i, {width: +clamp(Math.abs(ev.clientX - cx) * 2 / rect.width * 100, 3, 100).toFixed(2)});
      }
    };
    const up = () => {window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); onCommit();};
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up);
  }
  return <div ref={box} className="overlay-canvas">
    {overlays.map((o, i) => {
      const a = media[o.asset_id];
      const aspect = a ? (a.height || 9) / (a.width || 16) : 9 / 16;     // height / width of the media
      const heightCqw = o.width * aspect;
      const borderCqw = o.border / 1080 * 100 / frameAspect;           // px at 1080p -> % of frame width
      const radiusCqw = o.radius / 100 * Math.min(o.width, heightCqw) + borderCqw;
      const style: React.CSSProperties = {
        left: `${o.x}%`, top: `${o.y}%`, width: `${o.width}cqw`, height: `${heightCqw}cqw`,
        transform: `translate(-50%,-50%) rotate(${o.rotation}deg)`, opacity: o.opacity / 100,
        border: o.border ? `${borderCqw}cqw solid ${o.border_color}` : 'none', borderRadius: `${radiusCqw}cqw`,
        boxShadow: o.shadow ? `0 ${o.width * 0.02}cqw ${o.width * 0.05 * o.shadow / 100}cqw rgba(0,0,0,${0.55 * o.shadow / 100})` : 'none',
      };
      return <div key={o.id} className={`overlay-item ${i === selected ? 'selected' : ''}`} style={style} data-box={`${o.width}x${+heightCqw.toFixed(2)}@${o.x},${o.y}r${o.rotation}`} role="button" tabIndex={0}
        aria-label={`Overlay ${i + 1}${a ? `: ${a.original_filename}` : ''}. Drag to move.`} onPointerDown={e => drag(i, 'move', e)}
        onKeyDown={e => {const step = e.shiftKey ? 5 : 1; const k = {ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step]}[e.key]; if (k) {e.preventDefault(); onChange(i, {x: +clamp(o.x + k[0], -20, 120).toFixed(2), y: +clamp(o.y + k[1], -20, 120).toFixed(2)}, true);}}}>
        {a?.type === 'video' ? <video src={api.assetStreamUrl(o.asset_id)} muted loop autoPlay playsInline/> : <img src={api.assetThumbUrl(o.asset_id, 640)} alt="" draggable={false}/>}
        {i === selected && <span className="overlay-handle" role="slider" aria-label={`Resize overlay ${i + 1}`} aria-valuenow={o.width} aria-valuemin={3} aria-valuemax={100} onPointerDown={e => drag(i, 'resize', e)}/>}
      </div>;
    })}
  </div>;
}

// Media lookups for the canvas (dimensions decide the card's aspect).
const mediaCache: Record<string, Asset> = {};
function useProjectMediaFromOverlays(overlays: Overlay[]) {
  const [, force] = useState(0);
  useEffect(() => {
    const missing = overlays.map(o => o.asset_id).filter(id => !mediaCache[id]);
    missing.forEach(id => api.getAsset(id).then(a => {mediaCache[id] = a; force(n => n + 1);}).catch(() => {}));
  }, [overlays.map(o => o.asset_id).join()]);
  return [mediaCache] as const;
}

export function OverlayPanel({scene, overlays, selected, onSelect, onChange, disabled}: {
  scene: Scene; overlays: Overlay[]; selected: number; onSelect: (i: number) => void;
  onChange: (next: Overlay[]) => void; disabled: boolean;
}) {
  const [media, setMedia] = useProjectMedia(scene.project_id);
  const [error, setError] = useState('');
  const [stickerQuery,setStickerQuery]=useState('');
  const [stickerBusy,setStickerBusy]=useState('');
  const file = useRef<HTMLInputElement>(null);
  const o = overlays[selected];
  const set = (patch: Partial<Overlay>) => onChange(overlays.map((x, i) => i === selected ? {...x, ...patch} : x));
  function add(asset_id: string) {
    if (overlays.length >= 8) {setError('A scene can have at most 8 overlays.'); return;}
    const offset = overlays.length * 4;
    onChange([...overlays, {...OVERLAY_DEFAULTS, id: newId(), asset_id, x: clamp(72 - offset, 10, 90), y: clamp(30 + offset, 10, 90)}]);
    onSelect(overlays.length); setError('');
  }
  async function upload(f?: File) {
    if (!f) return;
    try {const a = await api.uploadAsset(scene.project_id, f); if (a.type !== 'image' && a.type !== 'video') {setError('Choose an image or a video.'); return;} setMedia(m => [...m, a]); add(a.id);}
    catch (e: any) {setError(e.message || 'Upload failed.');}
    finally {if (file.current) file.current.value = '';}
  }
  async function addSticker(sticker:{emoji:string;name:string}) {
    if(overlays.length>=8){setError('A scene can have at most 8 overlays. Remove one before adding another.');return;}
    setStickerBusy(sticker.name);setError('');
    try {
      const canvas=document.createElement('canvas');canvas.width=512;canvas.height=512;
      const ctx=canvas.getContext('2d');if(!ctx)throw new Error('Sticker rendering is unavailable in this browser.');
      ctx.clearRect(0,0,512,512);ctx.textAlign='center';ctx.textBaseline='middle';
      ctx.font='380px "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", sans-serif';
      ctx.shadowColor='rgba(0,0,0,.28)';ctx.shadowBlur=10;ctx.fillText(sticker.emoji,256,264,448);
      const blob=await new Promise<Blob>((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(new Error('Could not create the sticker image.')),'image/png'));
      const safe=sticker.name.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
      const asset=await api.uploadAsset(scene.project_id,new File([blob],`sticker-${safe}.png`,{type:'image/png'}));
      setMedia(m=>[...m,asset]);add(asset.id);
    }catch(e:any){setError(e?.message||'Could not add this sticker.');}
    finally{setStickerBusy('');}
  }
  const num = (key: keyof Overlay, label: string, min: number, max: number, step = 1, unit = '') =>
    <div className="adjust-row changed"><label htmlFor={`ov-${key}`}>{label}</label>
      <input id={`ov-${key}`} aria-label={`Overlay ${label}`} type="range" min={min} max={max} step={step} value={o[key] as number} disabled={disabled} onChange={e => set({[key]: Number(e.target.value)} as any)}/>
      <input aria-label={`Overlay ${label} value`} type="number" min={min} max={max} step={step} value={o[key] as number} disabled={disabled} onChange={e => set({[key]: clamp(Number(e.target.value) || 0, min, max)} as any)}/><span className="unit">{unit}</span></div>;
  const seconds = (ms: number | null) => ms === null ? '' : (ms / 1000).toFixed(1);

  return <div className="overlay-panel">
    <h3><PictureInPicture2 size={15}/> Picture in picture</h3>
    <p className="hint">Place an image or video inside this scene, like a map, portrait or document. Drag it on the preview to move it; drag its corner to resize.</p>
    <div className="lut-row">
      <select aria-label="Add overlay from media" value="" disabled={disabled} onChange={e => e.target.value && add(e.target.value)}>
        <option value="">Add from Media Pool…</option>
        {media.map(m => <option key={m.id} value={m.id}>{m.type === 'video' ? '🎞 ' : '🖼 '}{m.original_filename}</option>)}
      </select>
      <button className="btn" disabled={disabled} onClick={() => file.current?.click()}><Upload size={14}/> Upload</button>
      <input ref={file} type="file" accept="image/*,video/*" hidden aria-label="Upload overlay media" onChange={e => void upload(e.target.files?.[0])}/>
    </div>
    {error && <p className="form-error" role="alert">{error}</p>}
    <section className="sticker-library" aria-label="Stickers and emoji">
      <div className="section-heading"><h3><Sticker size={15}/> Stickers & emoji</h3><span>{STICKERS.length}</span><FeatureHelp compact title="Stickers and emoji" description="Add a reusable graphic or emoji as a normal image overlay on the scene." steps="Search or browse the sticker grid, click an item, then select it in the overlay list or preview to resize, position, animate, or delete it."/></div>
      <p className="hint">Choose a transparent sticker. It is saved as a PNG overlay, so it renders consistently with your project.</p>
      <label className="search-control"><Search size={14}/><input aria-label="Search stickers and emoji" placeholder="Search stickers…" value={stickerQuery} onChange={e=>setStickerQuery(e.target.value)}/></label>
      <div className="sticker-grid" role="group" aria-label="Sticker choices">{STICKERS.filter(s=>`${s.name} ${s.tags} ${s.emoji}`.toLowerCase().includes(stickerQuery.toLowerCase())).map(s=><button key={s.name} className="sticker-choice" title={s.name} aria-label={`Add ${s.name} sticker`} disabled={disabled||!!stickerBusy||overlays.length>=8} onClick={()=>void addSticker(s)}><span aria-hidden="true">{stickerBusy===s.name?'…':s.emoji}</span><small>{s.name}</small></button>)}</div>
      {!STICKERS.some(s=>`${s.name} ${s.tags} ${s.emoji}`.toLowerCase().includes(stickerQuery.toLowerCase()))&&<p className="hint">No stickers match that search.</p>}
      {overlays.length>=8&&<p className="hint">This scene has reached the 8 overlay limit.</p>}
    </section>
    {overlays.length > 0 && <ul className="overlay-list" aria-label="Overlays (top of list is drawn on top)">
      {[...overlays.keys()].reverse().map(i => <li key={overlays[i].id} className={i === selected ? 'selected' : ''}>
        <button className="overlay-pick" aria-pressed={i === selected} onClick={() => onSelect(i)}><img src={api.assetThumbUrl(overlays[i].asset_id, 160)} alt=""/> Overlay {i + 1}</button>
        <button className="icon-reset" aria-label={`Bring overlay ${i + 1} forward`} disabled={disabled || i === overlays.length - 1} onClick={() => {const n = [...overlays]; [n[i], n[i + 1]] = [n[i + 1], n[i]]; onChange(n); onSelect(i + 1);}}><ArrowUp size={12}/></button>
        <button className="icon-reset" aria-label={`Send overlay ${i + 1} back`} disabled={disabled || i === 0} onClick={() => {const n = [...overlays]; [n[i], n[i - 1]] = [n[i - 1], n[i]]; onChange(n); onSelect(i - 1);}}><ArrowDown size={12}/></button>
        <button className="icon-reset" aria-label={`Duplicate overlay ${i + 1}`} disabled={disabled || overlays.length >= 8} onClick={() => {onChange([...overlays, {...overlays[i], id: newId(), x: clamp(overlays[i].x + 4, 0, 100), y: clamp(overlays[i].y + 4, 0, 100)}]); onSelect(overlays.length);}}><Copy size={12}/></button>
        <button className="icon-reset" aria-label={`Delete overlay ${i + 1}`} disabled={disabled} onClick={() => {onChange(overlays.filter((_, k) => k !== i)); onSelect(Math.max(0, Math.min(selected, overlays.length - 2)));}}><Trash2 size={12}/></button>
      </li>)}
    </ul>}
    {o && <div className="panel-grid">
      <fieldset className="adjust-group"><legend>Position & size</legend>
        {num('x', 'Left–right', -20, 120, 0.5, '%')}{num('y', 'Up–down', -20, 120, 0.5, '%')}{num('width', 'Size', 3, 100, 0.5, '%')}
        {num('rotation', 'Rotation', -180, 180, 1, '°')}{num('opacity', 'Opacity', 0, 100, 1, '%')}
      </fieldset>
      <fieldset className="adjust-group"><legend>Frame</legend>
        {num('radius', 'Corners', 0, 50, 1, '%')}{num('border', 'Border', 0, 40, 1, 'px')}
        <div className="adjust-row changed"><label htmlFor="ov-color">Border colour</label><input id="ov-color" aria-label="Overlay border colour" type="color" value={o.border_color} disabled={disabled} onChange={e => set({border_color: e.target.value.toUpperCase()})}/><span/><span/></div>
        {num('shadow', 'Shadow', 0, 100, 1, '%')}
        {num('feather', 'Soft edges', 0, 100, 1, '%')}
      </fieldset>
      <fieldset className="adjust-group"><legend>Move & green screen</legend>
        <label className="switch-label finishing-toggle"><input type="checkbox" aria-label="Glide to another position" checked={o.x2 != null} disabled={disabled} onChange={e => set(e.target.checked ? {x2: clamp(o.x - 30, -20, 120), y2: o.y} : {x2: null, y2: null})}/> Glide to another position during its time</label>
        {o.x2 != null && <>
          {num('x2' as any, 'End left–right', -20, 120, 0.5, '%')}{num('y2' as any, 'End up–down', -20, 120, 0.5, '%')}
        </>}
        <label className="switch-label finishing-toggle"><input type="checkbox" aria-label="Green screen" checked={!!o.chroma} disabled={disabled} onChange={e => set({chroma: e.target.checked ? '#00FF00' : null})}/> Green screen (make one colour transparent)</label>
        {o.chroma && <>
          <div className="adjust-row changed"><label htmlFor="ov-chroma">Key colour</label><input id="ov-chroma" aria-label="Green screen colour" type="color" value={o.chroma} disabled={disabled} onChange={e => set({chroma: e.target.value.toUpperCase()})}/><span/><span/></div>
          {num('chroma_similarity' as any, 'Tolerance', 1, 100, 1, '%')}
        </>}
      </fieldset>
      <fieldset className="adjust-group"><legend>Timing & animation</legend>
        <div className="audio-times">
          <label>Show from (s)<input aria-label="Overlay start seconds" type="number" min={0} step={0.1} value={seconds(o.start_ms)} disabled={disabled} onChange={e => set({start_ms: Math.max(0, Math.round(Number(e.target.value) * 1000) || 0)})}/></label>
          <label>Until (s)<input aria-label="Overlay end seconds" type="number" min={0} step={0.1} placeholder="scene end" value={seconds(o.end_ms)} disabled={disabled} onChange={e => set({end_ms: e.target.value === '' ? null : Math.max(o.start_ms + 100, Math.round(Number(e.target.value) * 1000))})}/></label>
        </div>
        {(['anim_in', 'anim_out'] as const).map(key => <div key={key} className="film-option"><span>{key === 'anim_in' ? 'Entrance' : 'Exit'}</span>
          <div className="segmented" role="radiogroup" aria-label={key === 'anim_in' ? 'Overlay entrance' : 'Overlay exit'}>
            {ANIMS.map(([v, l]) => <button key={v} role="radio" aria-checked={o[key] === v} className={o[key] === v ? 'selected' : ''} disabled={disabled} onClick={() => set({[key]: v} as any)}>{l}</button>)}
          </div></div>)}
        {num('anim_ms', 'Anim. length', 0, 3000, 100, 'ms')}
      </fieldset>
    </div>}
    {o && <p className="hint">Videos play silently and loop. Render the scene for the final result.</p>}
  </div>;
}
