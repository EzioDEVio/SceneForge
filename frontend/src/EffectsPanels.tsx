import React, {useEffect, useState} from 'react';
import {Vibrate, Focus, EyeOff, Sun, Blend, Plus, Trash2, Palette, LayoutGrid, Route as RouteIcon, Box as BoxIcon, MousePointerClick, Undo2} from 'lucide-react';
import type {Look, Scene} from './api';

export type Shake = {amount: number; speed: number; impact: boolean};
export type Spot = {x: number; y: number; w: number; h: number; shape: 'rect' | 'ellipse'; dim: number; feather: number; start_ms: number; end_ms: number | null};
export type Redact = {x: number; y: number; w: number; h: number; mode: 'blur' | 'pixelate'; strength: number; start_ms: number; end_ms: number | null};
export type Leak = {amount: number; speed: number; color: 'warm' | 'cool' | 'rainbow'};
export type Tone = {shadow: string; highlight: string; amount: number; balance: number};
export type Wheels = {lift: number[]; gamma: number[]; gain: number[]};
export type Layout = {type: 'split2' | 'split2v' | 'split3' | 'grid4'; gap: number; bg: string};
export type RouteFx = {points: number[][]; color: string; width: number; style: 'solid' | 'dashed'; pins: boolean; start_ms: number; draw_ms: number};
export type Parallax = {x: number; y: number; w: number; h: number; shape: 'ellipse' | 'rect'; direction: 'in' | 'out' | 'left' | 'right'; amount: number};
const LAYOUT: Layout = {type: 'split2', gap: 8, bg: '#000000'};
const ROUTE: RouteFx = {points: [], color: '#E8413C', width: 8, style: 'solid', pins: true, start_ms: 0, draw_ms: 3000};
const PARALLAX: Parallax = {x: 50, y: 55, w: 40, h: 70, shape: 'ellipse', direction: 'in', amount: 50};
const ZERO3 = () => [0, 0, 0];

/** One colour wheel: drag the dot towards a colour to tint that range, the
 *  slider sets its brightness. Stored as an [r, g, b] offset in -100..100. */
function ColorWheel({label, value, onChange, disabled}: {label: string; value: number[]; onChange: (v: number[]) => void; disabled: boolean}) {
  const mean = (value[0] + value[1] + value[2]) / 3;
  const chroma = value.map(v => v - mean);
  // position of the dot: project the chroma offset onto the hue circle
  const ang = Math.atan2((chroma[1] - chroma[2]) * Math.sqrt(3) / 2, chroma[0] - (chroma[1] + chroma[2]) / 2);
  const mag = Math.min(1, Math.hypot(chroma[0] - (chroma[1] + chroma[2]) / 2, (chroma[1] - chroma[2]) * Math.sqrt(3) / 2) / 60);
  const ref = React.useRef<HTMLDivElement>(null);
  function fromPoint(clientX: number, clientY: number) {
    const r = ref.current!.getBoundingClientRect();
    let dx = (clientX - r.left - r.width / 2) / (r.width / 2), dy = -(clientY - r.top - r.height / 2) / (r.height / 2);
    const m = Math.min(1, Math.hypot(dx, dy)); const a = Math.atan2(dy, dx);
    const rgb = [Math.cos(a), Math.cos(a - 2 * Math.PI / 3), Math.cos(a + 2 * Math.PI / 3)].map(c => c * m * 60);
    onChange(rgb.map(c => Math.round(Math.max(-100, Math.min(100, c + mean)))));
  }
  function drag(e: React.PointerEvent) {
    if (disabled) return; e.preventDefault(); fromPoint(e.clientX, e.clientY);
    const move = (ev: PointerEvent) => fromPoint(ev.clientX, ev.clientY);
    const up = () => {window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up);};
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up);
  }
  return <div className="wheel">
    <div ref={ref} className="wheel-disc" role="slider" aria-label={`${label} colour wheel`} aria-valuetext={`red ${value[0]}, green ${value[1]}, blue ${value[2]}`} tabIndex={0}
      onPointerDown={drag} onDoubleClick={() => onChange(ZERO3())}
      onKeyDown={e => {const d = {ArrowRight: [4, -2, -2], ArrowLeft: [-4, 2, 2], ArrowUp: [-2, 4, -2], ArrowDown: [2, -4, 2]}[e.key]; if (d) {e.preventDefault(); onChange(value.map((v, i) => Math.max(-100, Math.min(100, v + d[i]))));}}}>
      <span className="wheel-dot" style={{left: `${50 + 45 * mag * Math.cos(ang)}%`, top: `${50 - 45 * mag * Math.sin(ang)}%`}}/>
    </div>
    <span className="wheel-label">{label}</span>
    <input type="range" aria-label={`${label} brightness`} min={-60} max={60} value={Math.round(mean)} disabled={disabled}
      onChange={e => {const nm = Number(e.target.value); onChange(chroma.map(c => Math.round(Math.max(-100, Math.min(100, c + nm)))));}}/>
  </div>;
}

const SHAKE: Shake = {amount: 40, speed: 50, impact: false};
const SPOT: Spot = {x: 50, y: 50, w: 40, h: 50, shape: 'ellipse', dim: 65, feather: 40, start_ms: 0, end_ms: null};
const REDACT: Redact = {x: 50, y: 50, w: 20, h: 20, mode: 'blur', strength: 70, start_ms: 0, end_ms: null};
const LEAK: Leak = {amount: 50, speed: 40, color: 'warm'};
const TONE: Tone = {shadow: '#1E5A8C', highlight: '#F2A541', amount: 40, balance: 0};

function Row({label, value, min, max, step = 1, unit = '', onChange, disabled}: {label: string; value: number; min: number; max: number; step?: number; unit?: string; onChange: (v: number) => void; disabled: boolean}) {
  const id = 'fx-' + label.replace(/\W+/g, '-').toLowerCase();
  return <div className="adjust-row changed"><label htmlFor={id}>{label}</label>
    <input id={id} aria-label={label} type="range" min={min} max={max} step={step} value={value} disabled={disabled} onChange={e => onChange(Number(e.target.value))}/>
    <input aria-label={`${label} value`} type="number" min={min} max={max} step={step} value={value} disabled={disabled} onChange={e => onChange(Math.max(min, Math.min(max, Number(e.target.value) || 0)))}/><span className="unit">{unit}</span></div>;
}
function Pills<T extends string>({label, value, options, onChange, disabled}: {label: string; value: T; options: [T, string][]; onChange: (v: T) => void; disabled: boolean}) {
  return <div className="film-option"><span>{label}</span><div className="segmented" role="radiogroup" aria-label={label}>
    {options.map(([v, l]) => <button key={v} role="radio" aria-checked={value === v} className={value === v ? 'selected' : ''} disabled={disabled} onClick={() => onChange(v)}>{l}</button>)}
  </div></div>;
}
function Section({title, Icon, on, onToggle, hint, children, disabled}: {title: string; Icon: typeof Sun; on: boolean; onToggle: (on: boolean) => void; hint: string; children: React.ReactNode; disabled: boolean}) {
  return <section className="look-section" aria-label={title}>
    <div className="look-heading"><h3><Icon size={15}/> {title}</h3>
      <label className="switch-label"><input type="checkbox" role="switch" aria-label={title} checked={on} disabled={disabled} onChange={e => onToggle(e.target.checked)}/> {on ? 'On' : 'Off'}</label></div>
    <p className="hint">{hint}</p>
    {on && children}
  </section>;
}
const Box = ({v, set, disabled}: {v: {x: number; y: number; w: number; h: number}; set: (p: any) => void; disabled: boolean}) => <>
  <Row label="Left–right" value={v.x} min={-10} max={110} step={0.5} unit="%" onChange={x => set({x})} disabled={disabled}/>
  <Row label="Up–down" value={v.y} min={-10} max={110} step={0.5} unit="%" onChange={y => set({y})} disabled={disabled}/>
  <Row label="Width" value={v.w} min={1} max={100} step={0.5} unit="%" onChange={w => set({w})} disabled={disabled}/>
  <Row label="Height" value={v.h} min={1} max={100} step={0.5} unit="%" onChange={h => set({h})} disabled={disabled}/>
</>;
const Timing = ({v, set, disabled, name}: {v: {start_ms: number; end_ms: number | null}; set: (p: any) => void; disabled: boolean; name: string}) =>
  <div className="audio-times">
    <label>Show from (s)<input aria-label={`${name} start seconds`} type="number" min={0} step={0.1} value={(v.start_ms / 1000).toFixed(1)} disabled={disabled} onChange={e => set({start_ms: Math.max(0, Math.round(Number(e.target.value) * 1000) || 0)})}/></label>
    <label>Until (s)<input aria-label={`${name} end seconds`} type="number" min={0} step={0.1} placeholder="scene end" value={v.end_ms === null ? '' : (v.end_ms / 1000).toFixed(1)} disabled={disabled} onChange={e => set({end_ms: e.target.value === '' ? null : Math.max(v.start_ms + 100, Math.round(Number(e.target.value) * 1000))})}/></label>
  </div>;

/** Scene effects: camera shake, spotlight, blur/pixelate regions, light leaks, split toning. */
export function SceneEffectsPanel({scene, disabled, onDraft, liveRoute, routeEditing, onRouteEditing, onAddMedia}: {scene: Scene; disabled: boolean; onDraft: (look: Look) => void;
  liveRoute?: RouteFx | null; routeEditing?: boolean; onRouteEditing?: (on: boolean) => void; onAddMedia?: () => void}) {
  const look = (scene.look_json || {}) as any;
  const pick = (l: any) => ({shake: l.shake || null, spotlight: l.spotlight || null, redact: l.redact || [], leak: l.leak || null, tone: l.tone || null, wheels: l.wheels || null, layout: l.layout || null, parallax: l.parallax || null});
  const [st, setSt] = useState(pick(look));
  useEffect(() => {setSt(pick((scene.look_json || {}) as any));}, [scene.id]);
  const route: RouteFx | null = liveRoute === undefined ? (look.route || null) : liveRoute;
  const videoOrImages = scene.shots.length;
  const put = (key: string, value: any) => {setSt(s => ({...s, [key]: value})); onDraft({[key]: value === null || (Array.isArray(value) && !value.length) ? null : value} as any);};
  const {shake, spotlight: sp, redact, leak, tone, wheels, layout, parallax: plx} = st;
  return <div className="look-panel scene-fx-panel">
    <Section title="Split toning" Icon={Blend} on={!!tone} onToggle={on => put('tone', on ? {...TONE} : null)} disabled={disabled} hint="Tint shadows and highlights with two colours, like a film grade. Shows in the preview.">
      {tone && <>
        <div className="adjust-row changed"><label>Shadows</label><input type="color" aria-label="Shadow colour" value={tone.shadow} disabled={disabled} onChange={e => put('tone', {...tone, shadow: e.target.value.toUpperCase()})}/><span/><span/></div>
        <div className="adjust-row changed"><label>Highlights</label><input type="color" aria-label="Highlight colour" value={tone.highlight} disabled={disabled} onChange={e => put('tone', {...tone, highlight: e.target.value.toUpperCase()})}/><span/><span/></div>
        <Row label="Amount" value={tone.amount} min={0} max={100} unit="%" onChange={amount => put('tone', {...tone, amount})} disabled={disabled}/>
        <Row label="Balance" value={tone.balance} min={-100} max={100} onChange={balance => put('tone', {...tone, balance})} disabled={disabled}/>
      </>}
    </Section>
    <Section title="Colour wheels" Icon={Palette} on={!!wheels} onToggle={on => put('wheels', on ? {lift: ZERO3(), gamma: ZERO3(), gain: ZERO3()} : null)} disabled={disabled} hint="Lift tints the shadows, Gamma the midtones, Gain the highlights. Drag a dot towards a colour; double-click to reset. Shows in the preview.">
      {wheels && <div className="wheels-row">
        {(['lift', 'gamma', 'gain'] as const).map(k => <ColorWheel key={k} label={k[0].toUpperCase() + k.slice(1)} value={wheels[k]} disabled={disabled} onChange={v => put('wheels', {...wheels, [k]: v})}/>)}
      </div>}
    </Section>
    <Section title="3D photo (parallax)" Icon={BoxIcon} on={!!plx} onToggle={on => put('parallax', on ? {...PARALLAX} : null)} disabled={disabled} hint="Gives still photos depth: mark the subject; the background behind it is filled in automatically and the two move at different depths. Render to see it.">
      {plx && <>
        <Pills label="Subject shape" value={plx.shape} options={[['ellipse', 'Oval'], ['rect', 'Box']]} onChange={shape => put('parallax', {...plx, shape})} disabled={disabled}/>
        <Box v={plx} set={p => put('parallax', {...plx, ...p})} disabled={disabled}/>
        <Pills label="Camera move" value={plx.direction} options={[['in', 'Push in'], ['out', 'Pull out'], ['left', 'Drift left'], ['right', 'Drift right']]} onChange={direction => put('parallax', {...plx, direction})} disabled={disabled}/>
        <Row label="Depth" value={plx.amount} min={0} max={100} unit="%" onChange={amount => put('parallax', {...plx, amount})} disabled={disabled}/>
        <p className="hint">Applies to photos in this scene (not video clips). The subject box shows on the preview.</p>
      </>}
    </Section>
    <Section title="Split screen" Icon={LayoutGrid} on={!!layout} onToggle={on => put('layout', on ? {...LAYOUT} : null)} disabled={disabled || videoOrImages < 2} hint={videoOrImages < 2 ? `Split screen shows several pictures at once, so this scene needs at least two. It has ${videoOrImages}.` : "Show the scene's pictures at the same time, e.g. then-and-now. They fill the panels in order and the preview shows the layout."}>
      {layout && <>
        <Pills label="Layout" value={layout.type} options={[['split2', 'Side by side'], ['split2v', 'Top & bottom'], ['split3', 'Three'], ['grid4', '2 × 2 grid']]} onChange={type => put('layout', {...layout, type})} disabled={disabled}/>
        <Row label="Gap" value={layout.gap} min={0} max={40} unit="px" onChange={gap => put('layout', {...layout, gap})} disabled={disabled}/>
        <div className="adjust-row changed"><label>Background</label><input type="color" aria-label="Split screen background" value={layout.bg} disabled={disabled} onChange={e => put('layout', {...layout, bg: e.target.value.toUpperCase()})}/><span/><span/></div>
      </>}
    </Section>
    {videoOrImages < 2 && onAddMedia && <div className="split-add"><button className="btn primary" disabled={disabled} onClick={onAddMedia}><Plus size={14}/> Add another image or video to this scene</button></div>}
    <Section title="Map route" Icon={RouteIcon} on={!!route} onToggle={on => {onDraft({route: on ? {...ROUTE, points: [[20, 70], [50, 45], [78, 35]]} : null} as any); onRouteEditing?.(on);}} disabled={disabled} hint="A line that draws itself across the picture, with pins at each stop, like an army's march or a trade route.">
      {route && <>
        <button className={`btn ${routeEditing ? 'primary' : ''}`} aria-pressed={!!routeEditing} disabled={disabled} onClick={() => onRouteEditing?.(!routeEditing)}><MousePointerClick size={14}/> {routeEditing ? 'Done editing points' : 'Edit points on the preview'}</button>
        <p className="hint">{routeEditing ? 'Click the preview to add a stop; drag a stop to move it.' : `${route.points.length} stops.`}</p>
        <div className="button-row"><button className="text-btn" disabled={disabled || route.points.length <= 2} onClick={() => onDraft({route: {...route, points: route.points.slice(0, -1)}} as any)}><Undo2 size={12}/> Remove last stop</button></div>
        <div className="adjust-row changed"><label>Colour</label><input type="color" aria-label="Route colour" value={route.color} disabled={disabled} onChange={e => onDraft({route: {...route, color: e.target.value.toUpperCase()}} as any)}/><span/><span/></div>
        <Row label="Line width" value={route.width} min={2} max={30} unit="px" onChange={width => onDraft({route: {...route, width}} as any)} disabled={disabled}/>
        <Pills label="Line" value={route.style} options={[['solid', 'Solid'], ['dashed', 'Dashed']]} onChange={style => onDraft({route: {...route, style}} as any)} disabled={disabled}/>
        <label className="switch-label finishing-toggle"><input type="checkbox" aria-label="Route pins" checked={route.pins} disabled={disabled} onChange={e => onDraft({route: {...route, pins: e.target.checked}} as any)}/> Pins at each stop</label>
        <div className="audio-times">
          <label>Start (s)<input aria-label="Route start seconds" type="number" min={0} step={0.1} value={(route.start_ms / 1000).toFixed(1)} disabled={disabled} onChange={e => onDraft({route: {...route, start_ms: Math.max(0, Math.round(Number(e.target.value) * 1000) || 0)}} as any)}/></label>
          <label>Draw time (s)<input aria-label="Route draw seconds" type="number" min={0.3} max={20} step={0.1} value={(route.draw_ms / 1000).toFixed(1)} disabled={disabled} onChange={e => onDraft({route: {...route, draw_ms: Math.max(300, Math.min(20000, Math.round(Number(e.target.value) * 1000) || 3000))}} as any)}/></label>
        </div>
      </>}
    </Section>
    <Section title="Camera shake" Icon={Vibrate} on={!!shake} onToggle={on => put('shake', on ? {...SHAKE} : null)} disabled={disabled} hint="Handheld wobble for tension or action, with an optional impact zoom at the start. Render to see it.">
      {shake && <>
        <Row label="Shake" value={shake.amount} min={0} max={100} unit="%" onChange={amount => put('shake', {...shake, amount})} disabled={disabled}/>
        <Row label="Speed" value={shake.speed} min={0} max={100} unit="%" onChange={speed => put('shake', {...shake, speed})} disabled={disabled}/>
        <label className="switch-label finishing-toggle"><input type="checkbox" aria-label="Impact zoom" checked={shake.impact} disabled={disabled} onChange={e => put('shake', {...shake, impact: e.target.checked})}/> Impact zoom at the start</label>
      </>}
    </Section>
    <Section title="Spotlight" Icon={Focus} on={!!sp} onToggle={on => put('spotlight', on ? {...SPOT} : null)} disabled={disabled} hint="Darken everything except one area, to point at a face, a place on a map or a line in a document.">
      {sp && <>
        <Pills label="Shape" value={sp.shape} options={[['ellipse', 'Oval'], ['rect', 'Box']]} onChange={shape => put('spotlight', {...sp, shape})} disabled={disabled}/>
        <Box v={sp} set={p => put('spotlight', {...sp, ...p})} disabled={disabled}/>
        <Row label="Darken" value={sp.dim} min={0} max={100} unit="%" onChange={dim => put('spotlight', {...sp, dim})} disabled={disabled}/>
        <Row label="Soft edge" value={sp.feather} min={0} max={100} unit="%" onChange={feather => put('spotlight', {...sp, feather})} disabled={disabled}/>
        <Timing v={sp} set={p => put('spotlight', {...sp, ...p})} disabled={disabled} name="Spotlight"/>
      </>}
    </Section>
    <Section title="Blur or pixelate areas" Icon={EyeOff} on={redact.length > 0} onToggle={on => put('redact', on ? [{...REDACT}] : [])} disabled={disabled} hint="Hide faces, names or number plates. Up to 6 areas.">
      {redact.map((r: Redact, i: number) => <fieldset key={i} className="adjust-group"><legend>Area {i + 1}</legend>
        <Pills label="Style" value={r.mode} options={[['blur', 'Blur'], ['pixelate', 'Pixelate']]} onChange={mode => put('redact', redact.map((x: Redact, k: number) => k === i ? {...x, mode} : x))} disabled={disabled}/>
        <Box v={r} set={p => put('redact', redact.map((x: Redact, k: number) => k === i ? {...x, ...p} : x))} disabled={disabled}/>
        <Row label="Strength" value={r.strength} min={1} max={100} unit="%" onChange={strength => put('redact', redact.map((x: Redact, k: number) => k === i ? {...x, strength} : x))} disabled={disabled}/>
        <Timing v={r} set={p => put('redact', redact.map((x: Redact, k: number) => k === i ? {...x, ...p} : x))} disabled={disabled} name={`Area ${i + 1}`}/>
        <button className="text-btn" disabled={disabled} onClick={() => put('redact', redact.filter((_: Redact, k: number) => k !== i))}><Trash2 size={12}/> Remove area {i + 1}</button>
      </fieldset>)}
      {redact.length > 0 && redact.length < 6 && <button className="text-btn" disabled={disabled} onClick={() => put('redact', [...redact, {...REDACT, x: Math.min(90, 50 + redact.length * 8)}])}><Plus size={12}/> Add another area</button>}
    </Section>
    <Section title="Light leaks" Icon={Sun} on={!!leak} onToggle={on => put('leak', on ? {...LEAK} : null)} disabled={disabled} hint="Soft coloured light drifting in from the edges, like old film or a vintage lens.">
      {leak && <>
        <Pills label="Colour" value={leak.color} options={[['warm', 'Warm'], ['cool', 'Cool'], ['rainbow', 'Rainbow']]} onChange={color => put('leak', {...leak, color})} disabled={disabled}/>
        <Row label="Amount" value={leak.amount} min={0} max={100} unit="%" onChange={amount => put('leak', {...leak, amount})} disabled={disabled}/>
        <Row label="Speed" value={leak.speed} min={0} max={100} unit="%" onChange={speed => put('leak', {...leak, speed})} disabled={disabled}/>
      </>}
    </Section>
  </div>;
}

/** Live approximations over the editor preview. */
export function SceneFxPreview({look, shots = []}: {look: any; shots?: {asset_id: string; asset?: {type?: string}}[]}) {
  if (!look) return null;
  const layout: Layout | undefined = look.layout;
  const sp: Spot | undefined = look.spotlight, redact: Redact[] = look.redact || [], leak: Leak | undefined = look.leak;
  const plx: Parallax | undefined = look.parallax, route: RouteFx | undefined = look.route;
  const hole = sp ? (sp.shape === 'ellipse' ? `radial-gradient(ellipse ${sp.w / 2}% ${sp.h / 2}% at ${sp.x}% ${sp.y}%, transparent ${Math.max(0, 100 - sp.feather)}%, rgba(0,0,0,${sp.dim / 100}) 100%)` : undefined) : undefined;
  const leakColors = {warm: ['255,140,40', '255,70,30'], cool: ['80,170,255', '140,90,255'], rainbow: ['255,80,60', '70,150,255']};
  const cells: [number, number, number, number][] = !layout ? [] : ({
    split2: [[0, 0, 50, 100], [50, 0, 50, 100]], split2v: [[0, 0, 100, 50], [0, 50, 100, 50]],
    split3: [[0, 0, 33.34, 100], [33.33, 0, 33.34, 100], [66.66, 0, 33.34, 100]],
    grid4: [[0, 0, 50, 50], [50, 0, 50, 50], [0, 50, 50, 50], [50, 50, 50, 50]]} as Record<string, [number, number, number, number][]>)[layout.type];
  const gapPct = layout ? layout.gap / 1080 * 100 / 2 : 0;
  return <div className="scenefx-preview" aria-hidden="true">
    {layout && shots.length >= 2 && <div className="fx-layout" style={{background: layout.bg}}>
      {cells.slice(0, shots.length).map(([x, y, w, h], i) => <div key={i} className="fx-cell" style={{left: `calc(${x}% + ${x > 0 ? gapPct : 0}%)`, top: `calc(${y}% + ${y > 0 ? gapPct * 16 / 9 : 0}%)`,
        width: `calc(${w}% - ${gapPct}%)`, height: `calc(${h}% - ${gapPct * 16 / 9}%)`, backgroundImage: `url(/api/assets/${shots[i].asset_id}/thumbnail?w=640)`}}/>)}
    </div>}
    {plx && <div className={`fx-subject ${plx.shape}`} style={{left: `${plx.x - plx.w / 2}%`, top: `${plx.y - plx.h / 2}%`, width: `${plx.w}%`, height: `${plx.h}%`}}><span>Subject</span></div>}
    {route && route.points.length > 1 && <svg className="fx-route" viewBox="0 0 100 100" preserveAspectRatio="none">
      <polyline points={route.points.map(p => p.join(',')).join(' ')} fill="none" stroke={route.color} strokeWidth={route.width / 10} vectorEffect="non-scaling-stroke" style={{strokeWidth: `${route.width / 3}px`}} strokeDasharray={route.style === 'dashed' ? '6 4' : undefined} strokeLinecap="round" strokeLinejoin="round"/>
    </svg>}
    {sp && sp.shape === 'ellipse' && <div className="fx-layer" style={{background: hole}}/>}
    {sp && sp.shape === 'rect' && <div className="fx-spot-rect" style={{left: `${sp.x - sp.w / 2}%`, top: `${sp.y - sp.h / 2}%`, width: `${sp.w}%`, height: `${sp.h}%`, boxShadow: `0 0 ${sp.feather / 4}cqw ${sp.feather / 8}cqw rgba(0,0,0,${sp.dim / 100}), 0 0 0 200cqw rgba(0,0,0,${sp.dim / 100})`}}/>}
    {redact.map((r, i) => <div key={i} className="fx-redact" style={{left: `${r.x - r.w / 2}%`, top: `${r.y - r.h / 2}%`, width: `${r.w}%`, height: `${r.h}%`, backdropFilter: `blur(${r.mode === 'pixelate' ? 3 : 2 + r.strength / 8}px)`}}/>)}
    {leak && leak.amount > 0 && <div className="fx-layer fx-leak" style={{opacity: 0.2 + 0.6 * leak.amount / 100, animationDuration: `${12 - 9 * leak.speed / 100}s`,
      background: `radial-gradient(40% 70% at 0% 40%, rgba(${leakColors[leak.color][0]},0.9), transparent 70%), radial-gradient(35% 60% at 100% 70%, rgba(${leakColors[leak.color][1]},0.8), transparent 70%)`}}/>}
  </div>;
}


/** Route point editing on the preview: click to add a stop, drag to move. */
export function RouteCanvas({route, onChange}: {route: RouteFx; onChange: (r: RouteFx, save: boolean) => void}) {
  const box = React.useRef<HTMLDivElement>(null);
  const pct = (e: {clientX: number; clientY: number}) => {const r = box.current!.getBoundingClientRect(); return [+(Math.max(0, Math.min(100, (e.clientX - r.left) / r.width * 100))).toFixed(2), +(Math.max(0, Math.min(100, (e.clientY - r.top) / r.height * 100))).toFixed(2)];};
  function add(e: React.PointerEvent) {
    if (e.target !== box.current || route.points.length >= 20) return;
    onChange({...route, points: [...route.points, pct(e)]}, true);
  }
  function drag(i: number, e: React.PointerEvent) {
    e.preventDefault(); e.stopPropagation();
    let latest = route;
    const move = (ev: PointerEvent) => {latest = {...route, points: route.points.map((p, k) => k === i ? pct(ev) : p)}; onChange(latest, false);};
    const up = () => {window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); onChange(latest, true);};
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up);
  }
  return <div ref={box} className="route-canvas" aria-label="Route editor: click to add a stop" onPointerDown={add}>
    {route.points.map((p, i) => <span key={i} className="route-point" role="button" aria-label={`Route stop ${i + 1}`} tabIndex={0} style={{left: `${p[0]}%`, top: `${p[1]}%`, background: route.color}} onPointerDown={e => drag(i, e)}>{i + 1}</span>)}
  </div>;
}
