import React, {useEffect, useMemo, useRef, useState} from 'react';
import {Clock, Crop, Frame, Move, Sparkles, Type, X, Layers} from 'lucide-react';
import {api, type Overlay, type Project, type Scene} from './api';
import {OverlayCanvas, OverlayPanel} from './Overlays';
import {TexturedTitlePanel, VideoInTextPanel, type KnockoutSettings, type TexturedSettings} from './CreativeTools';

export type CreativeKind = 'videoText' | 'textured';
/** Layers made by these tools carry an id prefix from the server (creative.py). */
export const creativeKindOf = (o: Overlay): CreativeKind | null => o.id?.startsWith('ko') ? 'videoText' : o.id?.startsWith('tt') ? 'textured' : null;

const TABS = [
  {id: 'create', label: 'Create', Icon: Sparkles},
  {id: 'Position & size', label: 'Position & size', Icon: Crop},
  {id: 'Frame', label: 'Frame', Icon: Frame},
  {id: 'Move & green screen', label: 'Move & green screen', Icon: Move},
  {id: 'Timing & animation', label: 'Timing & animation', Icon: Clock},
] as const;

// Approximate looks of the built-in textures, for the live preview only (the render uses the real texture).
const TEXTURE_CSS: Record<string, string> = {
  lava: 'radial-gradient(circle at 30% 40%,#ffde59 0 8%,transparent 20%),radial-gradient(circle at 70% 60%,#ff9f1c 0 10%,transparent 25%),linear-gradient(135deg,#ff4d00,#7a0c00 55%,#1a0500)',
  neon: 'linear-gradient(90deg,#ff2bd6,#7a5cff,#00e5ff)', gold: 'linear-gradient(160deg,#fff3b0,#d4a017 35%,#8a6200 60%,#ffe27a 80%,#a87900)',
  chrome: 'linear-gradient(180deg,#ffffff,#9aa4b1 45%,#2b3138 52%,#cfd6de 70%,#ffffff)', marble: 'linear-gradient(120deg,#f4f1ec,#d9d4cc 30%,#f8f6f2 50%,#bdb6ab 70%,#f1ede6)',
  ice: 'linear-gradient(160deg,#e9fbff,#9ad9ff 40%,#4fa9e6 60%,#d8f4ff)', fire: 'linear-gradient(0deg,#7a0c00,#ff4500 35%,#ffb300 65%,#fff3b0)',
  pixel: 'repeating-conic-gradient(#36c 0 25%,#f90 0 50%)', galaxy: 'radial-gradient(circle at 20% 30%,#fff 0 1px,transparent 2px),radial-gradient(circle at 70% 70%,#fff 0 1px,transparent 2px),linear-gradient(135deg,#1b0b3a,#4b1b8f 45%,#0b2a6b)',
};

function KnockoutLive({s, aspect}: {s: KnockoutSettings; aspect: number}) {
  // The card with the title cut out, as an SVG mask: the scene picture shows through the letters.
  const W = 1920, H = Math.round(1920 / aspect);
  const text = s.text.trim() || 'YOUR TITLE';
  return <svg className="cs-knockout" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden>
    <defs><mask id="cs-ko-mask"><rect width={W} height={H} fill="white"/>
      <text x={W / 2} y={H * s.y / 100} textAnchor="middle" dominantBaseline="middle" fontFamily={s.font} fontSize={s.font_size * H / 1080}
        textLength={text.length * s.font_size * H / 1080 * .62 > W * .92 ? W * .92 : undefined} lengthAdjust="spacingAndGlyphs" fill="black">{text}</text></mask></defs>
    <rect width={W} height={H} fill={s.background} opacity={s.opacity / 100} mask="url(#cs-ko-mask)"/>
    {s.outline > 0 && <text x={W / 2} y={H * s.y / 100} textAnchor="middle" dominantBaseline="middle" fontFamily={s.font} fontSize={s.font_size * H / 1080}
      textLength={text.length * s.font_size * H / 1080 * .62 > W * .92 ? W * .92 : undefined} lengthAdjust="spacingAndGlyphs" fill="none" stroke={s.outline_color} strokeWidth={s.outline}>{text}</text>}
  </svg>;
}

function TexturedLive({s, textureUrl}: {s: TexturedSettings; textureUrl?: string}) {
  const image = s.source === 'pool' && textureUrl ? `url(${textureUrl})` : s.source === 'preset' ? TEXTURE_CSS[s.preset] || TEXTURE_CSS.lava : 'linear-gradient(135deg,#7a8696,#cfd6de)';
  // Glow sits on the wrapper: a filter on the clipped element itself can drop the text clip.
  return <div className="cs-textured" aria-hidden style={{filter: s.glow ? `drop-shadow(0 0 ${s.glow / 6}px rgba(255,255,255,${Math.min(.9, s.glow / 100)}))` : undefined}}>
    <span style={{fontFamily: s.font, fontSize: `${s.font_size / 1080 * 100}cqh`, backgroundImage: image, backgroundSize: s.preset === 'pixel' && s.source === 'preset' ? '14px 14px' : 'cover', backgroundPosition: 'center',
      WebkitBackgroundClip: 'text', backgroundClip: 'text', WebkitTextFillColor: 'transparent', color: 'transparent', WebkitTextStroke: s.outline ? `${Math.max(1, s.outline / 3)}px rgba(255,255,255,.85)` : undefined}}>{s.text.trim() || 'YOUR TITLE'}</span></div>;
}

/** Video inside text and Textured title in one place: create on the left tab, then adjust the
 *  new layer's position, frame, motion and timing, with the preview updating as you change it. */
export function CreativeStudio({kind, scene, project, overlays, editIndex, onChangeOverlays, onDone, onClose, disabled}: {
  kind: CreativeKind; scene: Scene; project: Project; overlays: Overlay[]; editIndex?: number;
  onChangeOverlays: (next: Overlay[], save?: boolean) => void; onDone: () => void | Promise<void>; onClose: () => void; disabled: boolean;
}) {
  const known = useRef(new Set(overlays.map(o => o.id)));
  const [index, setIndex] = useState<number>(editIndex ?? -1);
  const [tab, setTab] = useState<string>(editIndex != null ? 'Position & size' : 'create');
  const [ko, setKo] = useState<KnockoutSettings | null>(null);
  const [tx, setTx] = useState<TexturedSettings | null>(null);
  const ovRef = useRef(overlays); ovRef.current = overlays;
  const dialog = useRef<HTMLElement>(null);
  const shot = scene.shots.find(s => s.is_selected) || scene.shots[0];
  const aspect = project.width / project.height;
  const title = kind === 'videoText' ? 'Video inside text' : 'Textured title';
  // A layer created by this dialog: select it and move to its settings.
  useEffect(() => {
    if (index >= 0) return;
    const i = overlays.findIndex(o => !known.current.has(o.id) && creativeKindOf(o) === kind);
    if (i >= 0) {setIndex(i); setTab('Position & size');}
  }, [overlays, index, kind]);
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    dialog.current?.querySelector<HTMLElement>('[role=tab][aria-selected=true]')?.focus();
    const key = (e: KeyboardEvent) => {if (e.key === 'Escape') {e.stopPropagation(); onClose();}};
    window.addEventListener('keydown', key, true);
    return () => {window.removeEventListener('keydown', key, true); prev?.focus?.();};
  }, []);
  // Settings tabs show one group of the layer controls at a time.
  useEffect(() => {
    const host = dialog.current?.querySelector('.cs-layer-settings');
    host?.querySelectorAll<HTMLFieldSetElement>('fieldset').forEach(f => {const l = f.querySelector('legend')?.textContent || ''; f.hidden = tab !== 'create' && l !== tab && !(tab === 'Move & green screen' && l === 'Loop motion');});
  });
  const textureUrl = useMemo(() => tx?.source === 'pool' && tx.pool_id ? api.assetThumbUrl(tx.pool_id, 640) : undefined, [tx?.source, tx?.pool_id]);
  const layer = index >= 0 ? overlays[index] : null;
  return <div className="info-backdrop cs-backdrop" onMouseDown={e => e.target === e.currentTarget && onClose()}>
    <section ref={dialog} className="info-panel wide creative-studio" role="dialog" aria-modal="true" aria-label={title}>
      <header><span className="info-title"><Type size={18}/> {title}</span><span className="subtle">{scene.title}</span>
        <button className="icon-reset info-close" aria-label={`Close ${title}`} onClick={onClose}><X size={16}/></button></header>
      <div className="cs-body">
        <div className="cs-preview-col">
          <div className="cs-stage" style={{aspectRatio: String(aspect)}}>
            {shot?.asset_id ? <img className="cs-picture" src={api.assetThumbUrl(shot.asset_id, 1280)} alt=""/> : <div className="cs-empty">Add a picture or video to this scene: it is what shows inside the letters.</div>}
            {!layer && kind === 'videoText' && ko && <KnockoutLive s={ko} aspect={aspect}/>}
            {!layer && kind === 'textured' && tx && <TexturedLive s={tx} textureUrl={textureUrl}/>}
            {layer && <div className="cs-overlays"><OverlayCanvas sceneId={scene.id} overlays={overlays} frameAspect={aspect} selected={index} onSelect={setIndex}
              onChange={(i, patch, commit) => {const next = ovRef.current.map((x, k) => k === i ? {...x, ...patch} : x); ovRef.current = next; onChangeOverlays(next, !!commit);}}
              onCommit={() => onChangeOverlays(ovRef.current, true)}/></div>}
          </div>
          <div className="cs-companion" data-companion-preview/>
          <p className="hint">{layer ? 'Drag the layer to move it, or its corner to resize. Changes save as you go; render the scene to see the final video.' : 'Live preview of your settings. Press Add to create the layer, then adjust it here.'}</p>
        </div>
        <div className="cs-settings-col">
          <div className="cs-tabs" role="tablist" aria-label={`${title} settings`}>
            {TABS.map(({id, label, Icon}) => {const off = id !== 'create' && !layer; return <button key={id} role="tab" aria-selected={tab === id} disabled={off}
              title={off ? 'Add the layer first' : label} onClick={() => setTab(id)}><Icon size={15} aria-hidden/><span>{label}</span></button>;})}
          </div>
          <div className="cs-tab-body" role="tabpanel">
            <div hidden={tab !== 'create'}>
              {layer && <p className="info-status" role="status"><Layers size={13}/> Added as layer {index + 1}. Use the tabs above to place and time it. Create again to add another.</p>}
              {kind === 'videoText'
                ? <VideoInTextPanel scene={scene} disabled={disabled} onDone={async () => {setIndex(-1); known.current = new Set(ovRef.current.map(o => o.id)); await onDone();}} onSettings={setKo}/>
                : <TexturedTitlePanel scene={scene} disabled={disabled} onDone={async () => {setIndex(-1); known.current = new Set(ovRef.current.map(o => o.id)); await onDone();}} onSettings={setTx}/>}
            </div>
            {layer && <div className="cs-layer-settings" hidden={tab === 'create'}>
              <OverlayPanel scene={scene} overlays={overlays} selected={index} onSelect={setIndex} onChange={next => onChangeOverlays(next, true)} disabled={disabled}/>
            </div>}
          </div>
        </div>
      </div>
      <footer className="cs-footer"><span className="subtle">{layer ? `Layer ${index + 1} of ${overlays.length} · saved` : 'Not added yet'}</span><button className="btn btn-primary" onClick={onClose}>Done</button></footer>
    </section>
  </div>;
}
