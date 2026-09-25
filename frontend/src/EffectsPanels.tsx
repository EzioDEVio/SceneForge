import React, {useEffect, useState} from 'react';
import {Vibrate, Focus, EyeOff, Sun, Blend, Plus, Trash2} from 'lucide-react';
import type {Look, Scene} from './api';

export type Shake = {amount: number; speed: number; impact: boolean};
export type Spot = {x: number; y: number; w: number; h: number; shape: 'rect' | 'ellipse'; dim: number; feather: number; start_ms: number; end_ms: number | null};
export type Redact = {x: number; y: number; w: number; h: number; mode: 'blur' | 'pixelate'; strength: number; start_ms: number; end_ms: number | null};
export type Leak = {amount: number; speed: number; color: 'warm' | 'cool' | 'rainbow'};
export type Tone = {shadow: string; highlight: string; amount: number; balance: number};

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
export function SceneEffectsPanel({scene, disabled, onDraft}: {scene: Scene; disabled: boolean; onDraft: (look: Look) => void}) {
  const look = (scene.look_json || {}) as any;
  const [st, setSt] = useState({shake: look.shake || null, spotlight: look.spotlight || null, redact: look.redact || [], leak: look.leak || null, tone: look.tone || null});
  useEffect(() => {const l = (scene.look_json || {}) as any; setSt({shake: l.shake || null, spotlight: l.spotlight || null, redact: l.redact || [], leak: l.leak || null, tone: l.tone || null});}, [scene.id]);
  const put = (key: string, value: any) => {setSt(s => ({...s, [key]: value})); onDraft({[key]: value === null || (Array.isArray(value) && !value.length) ? null : value} as any);};
  const {shake, spotlight: sp, redact, leak, tone} = st;
  return <div className="look-panel scene-fx-panel">
    <Section title="Split toning" Icon={Blend} on={!!tone} onToggle={on => put('tone', on ? {...TONE} : null)} disabled={disabled} hint="Tint shadows and highlights with two colours, like a film grade. Shows in the preview.">
      {tone && <>
        <div className="adjust-row changed"><label>Shadows</label><input type="color" aria-label="Shadow colour" value={tone.shadow} disabled={disabled} onChange={e => put('tone', {...tone, shadow: e.target.value.toUpperCase()})}/><span/><span/></div>
        <div className="adjust-row changed"><label>Highlights</label><input type="color" aria-label="Highlight colour" value={tone.highlight} disabled={disabled} onChange={e => put('tone', {...tone, highlight: e.target.value.toUpperCase()})}/><span/><span/></div>
        <Row label="Amount" value={tone.amount} min={0} max={100} unit="%" onChange={amount => put('tone', {...tone, amount})} disabled={disabled}/>
        <Row label="Balance" value={tone.balance} min={-100} max={100} onChange={balance => put('tone', {...tone, balance})} disabled={disabled}/>
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
export function SceneFxPreview({look}: {look: any}) {
  if (!look) return null;
  const sp: Spot | undefined = look.spotlight, redact: Redact[] = look.redact || [], leak: Leak | undefined = look.leak;
  const hole = sp ? (sp.shape === 'ellipse' ? `radial-gradient(ellipse ${sp.w / 2}% ${sp.h / 2}% at ${sp.x}% ${sp.y}%, transparent ${Math.max(0, 100 - sp.feather)}%, rgba(0,0,0,${sp.dim / 100}) 100%)` : undefined) : undefined;
  const leakColors = {warm: ['255,140,40', '255,70,30'], cool: ['80,170,255', '140,90,255'], rainbow: ['255,80,60', '70,150,255']};
  return <div className="scenefx-preview" aria-hidden="true">
    {sp && sp.shape === 'ellipse' && <div className="fx-layer" style={{background: hole}}/>}
    {sp && sp.shape === 'rect' && <div className="fx-spot-rect" style={{left: `${sp.x - sp.w / 2}%`, top: `${sp.y - sp.h / 2}%`, width: `${sp.w}%`, height: `${sp.h}%`, boxShadow: `0 0 ${sp.feather / 4}cqw ${sp.feather / 8}cqw rgba(0,0,0,${sp.dim / 100}), 0 0 0 200cqw rgba(0,0,0,${sp.dim / 100})`}}/>}
    {redact.map((r, i) => <div key={i} className="fx-redact" style={{left: `${r.x - r.w / 2}%`, top: `${r.y - r.h / 2}%`, width: `${r.w}%`, height: `${r.h}%`, backdropFilter: `blur(${r.mode === 'pixelate' ? 3 : 2 + r.strength / 8}px)`}}/>)}
    {leak && leak.amount > 0 && <div className="fx-layer fx-leak" style={{opacity: 0.2 + 0.6 * leak.amount / 100, animationDuration: `${12 - 9 * leak.speed / 100}s`,
      background: `radial-gradient(40% 70% at 0% 40%, rgba(${leakColors[leak.color][0]},0.9), transparent 70%), radial-gradient(35% 60% at 100% 70%, rgba(${leakColors[leak.color][1]},0.8), transparent 70%)`}}/>}
  </div>;
}
