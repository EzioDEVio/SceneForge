import React, {useEffect, useRef, useState} from 'react';
import {RotateCcw, Upload, SlidersHorizontal, Palette, Zap, X} from 'lucide-react';
import {api, Asset, Scene, Look, Adjust} from './api';

// Slider definitions mirror backend ADJUST_RANGES (render/filters.py).
export const ADJUSTMENTS: {key: keyof Adjust; label: string; min: number; group: 'Light' | 'Color' | 'Detail'}[] = [
  {key: 'exposure', label: 'Exposure', min: -100, group: 'Light'},
  {key: 'contrast', label: 'Contrast', min: -100, group: 'Light'},
  {key: 'highlights', label: 'Highlights', min: -100, group: 'Light'},
  {key: 'shadows', label: 'Shadows', min: -100, group: 'Light'},
  {key: 'temperature', label: 'Temperature', min: -100, group: 'Color'},
  {key: 'tint', label: 'Tint', min: -100, group: 'Color'},
  {key: 'saturation', label: 'Saturation', min: -100, group: 'Color'},
  {key: 'vibrance', label: 'Vibrance', min: -100, group: 'Color'},
  {key: 'sharpen', label: 'Sharpen', min: 0, group: 'Detail'},
  {key: 'vignette', label: 'Vignette', min: 0, group: 'Detail'},
  {key: 'grain', label: 'Grain', min: 0, group: 'Detail'},
];
const BLOCKS: {key: 'small' | 'medium' | 'large'; label: string}[] = [
  {key: 'small', label: 'Fine'}, {key: 'medium', label: 'Medium'}, {key: 'large', label: 'Chunky'},
];

/** Short cache key for a scene's colour grade, so preview URLs change
 *  exactly when the grade changes. */
export function gradeKey(look?: Look): string {
  const text = JSON.stringify({a: look?.adjust || {}, l: look?.lut || null});
  let h = 5381; for (let i = 0; i < text.length; i++) h = ((h << 5) + h + text.charCodeAt(i)) | 0;
  return (h >>> 0).toString(36);
}

/** CSS approximation of the adjustments for the editing preview. The exact
 *  result comes from the renderer's baked grade LUT. */
export function adjustPreviewFilter(a: Adjust | undefined, wbFilterId: string): string {
  if (!a) return '';
  const v = (k: keyof Adjust) => (a[k] || 0) / 100;
  const parts: string[] = [];
  if (a.exposure) parts.push(`brightness(${Math.pow(2, 1.5 * v('exposure') * 0.6).toFixed(3)})`);
  if (a.contrast) parts.push(`contrast(${(1 + v('contrast')).toFixed(3)})`);
  const sat = (1 + v('saturation')) * (1 + 0.5 * v('vibrance'));
  if (a.saturation || a.vibrance) parts.push(`saturate(${Math.max(0, sat).toFixed(3)})`);
  if (a.temperature || a.tint) parts.push(`url(#${wbFilterId})`);
  if (a.sharpen) parts.push(`contrast(${(1 + 0.08 * v('sharpen')).toFixed(3)})`);
  return parts.join(' ');
}

export function WhiteBalanceFilter({id, adjust}: {id: string; adjust?: Adjust}) {
  const t = (adjust?.temperature || 0) / 100, g = (adjust?.tint || 0) / 100;
  const r = 1 + 0.28 * t, gr = 1 - 0.22 * g, b = 1 - 0.28 * t;
  const norm = 0.2126 * r + 0.7152 * gr + 0.0722 * b;
  const m = `${r / norm} 0 0 0 0  0 ${gr / norm} 0 0 0  0 0 ${b / norm} 0 0  0 0 0 1 0`;
  return <svg width="0" height="0" style={{position: 'absolute'}} aria-hidden="true"><filter id={id} colorInterpolationFilters="sRGB"><feColorMatrix type="matrix" values={m}/></filter></svg>;
}

/** Vignette and grain drawn over the preview (they are overlays, not colour). */
export function PreviewFinish({adjust}: {adjust?: Adjust}) {
  if (!adjust?.vignette && !adjust?.grain) return null;
  const vig = (adjust.vignette || 0) / 100;
  return <>
    {vig > 0 && <div className="preview-vignette" aria-hidden="true" style={{background: `radial-gradient(ellipse at center, transparent ${Math.round(70 - 40 * vig)}%, rgba(0,0,0,${(0.35 + 0.55 * vig).toFixed(2)}) 100%)`}}/>}
    {(adjust.grain || 0) > 0 && <div className="preview-grain" aria-hidden="true" style={{opacity: Math.min(0.5, (adjust.grain || 0) / 180)}}/>}
  </>;
}

type Props = {scene: Scene; disabled: boolean; onDraft: (look: Look) => void; onSaveNow: (look: Look) => Promise<unknown>};

export function LookPanel({scene, disabled, onDraft, onSaveNow}: Props) {
  const look = scene.look_json || {};
  const [adjust, setAdjust] = useState<Adjust>(look.adjust || {});
  const [glitch, setGlitch] = useState({speed: look.glitch?.speed ?? 1, block: look.glitch?.block ?? 'medium'});
  const [luts, setLuts] = useState<Asset[]>([]);
  const [lutError, setLutError] = useState('');
  const [lutBusy, setLutBusy] = useState(false);
  const lutFile = useRef<HTMLInputElement>(null);
  useEffect(() => {setAdjust(scene.look_json?.adjust || {}); setGlitch({speed: scene.look_json?.glitch?.speed ?? 1, block: scene.look_json?.glitch?.block ?? 'medium'});}, [scene.id]);
  useEffect(() => {let live = true; api.listLuts(scene.project_id).then(l => {if (live) setLuts(l);}).catch(() => {}); return () => {live = false;};}, [scene.project_id]);

  function setOne(key: keyof Adjust, value: number) {
    const next = {...adjust, [key]: value};
    if (!value) delete next[key];
    setAdjust(next);
    onDraft({adjust: next});
  }
  function setGlitchOpt(patch: Partial<typeof glitch>) {
    const next = {...glitch, ...patch};
    setGlitch(next);
    onDraft({glitch: next});
  }
  const [lutNote, setLutNote] = useState('');
  const lutFolder = useRef<HTMLInputElement>(null);
  /** Import one or many LUT files (a whole folder works). Only .cube files are
   *  imported; other Resolve formats are listed as skipped. The first imported
   *  LUT is applied to this scene when none is set yet. */
  async function importLuts(list: FileList | null) {
    const files = Array.from(list || []);
    if (!files.length) return;
    setLutError(''); setLutNote(''); setLutBusy(true);
    const cubes = files.filter(f => /\.cube$/i.test(f.name)).sort((a, b) => a.name.localeCompare(b.name, undefined, {numeric: true}));
    const skipped = files.length - cubes.length;
    const failed: string[] = [];
    let first: Asset | null = null, count = 0;
    try {
      for (const file of cubes) {
        try {
          const asset = await api.importLut(scene.project_id, file);
          count++; first = first || asset;
          setLuts(l => l.some(x => x.id === asset.id) ? l : [...l, asset]);
        } catch (e: any) {failed.push(`${file.name}: ${String(e.message || e).replace(/^This LUT could not be read: /, '')}`);}
      }
      if (first && (cubes.length === 1 || !lut)) await onSaveNow({lut: {asset_id: first.id, strength: lut?.strength ?? 100}});
      const parts = [`${count} LUT${count === 1 ? '' : 's'} imported`];
      if (skipped) parts.push(`${skipped} other file${skipped === 1 ? '' : 's'} skipped (only .cube is supported)`);
      if (cubes.length > 1 || skipped) setLutNote(parts.join(' · ') + (count > 1 ? '. Choose one from the list above.' : '.'));
      if (failed.length) setLutError(`Could not import ${failed.length}: ${failed.slice(0, 3).join('; ')}${failed.length > 3 ? '…' : ''}`);
      if (!cubes.length) setLutError('No .cube files were found. SceneForge imports .cube LUTs (3D, 1D, or 1D shaper + 3D).');
    } finally {setLutBusy(false); if (lutFile.current) lutFile.current.value = ''; if (lutFolder.current) lutFolder.current.value = '';}
  }
  const active = ADJUSTMENTS.filter(a => adjust[a.key]).length;
  const lut = look.lut;

  return <div className="look-panel">
    {scene.effect_preset === 'glitch' && <section className="look-section" aria-label="Glitch controls">
      <h3><Zap size={15}/> Glitch</h3>
      <p className="hint">Tears run across the whole frame in bursts. Effect strength above sets how hard it tears.</p>
      <label className="control-label">Speed · {glitch.speed.toFixed(2)}×
        <input aria-label="Glitch speed" type="range" min={0.25} max={4} step={0.25} value={glitch.speed} disabled={disabled} onChange={e => setGlitchOpt({speed: Number(e.target.value)})}/>
      </label>
      <div className="segmented" role="radiogroup" aria-label="Glitch block size">
        {BLOCKS.map(b => <button key={b.key} role="radio" aria-checked={glitch.block === b.key} className={glitch.block === b.key ? 'selected' : ''} disabled={disabled} onClick={() => setGlitchOpt({block: b.key})}>{b.label}</button>)}
      </div>
    </section>}

    <section className="look-section" aria-label="Adjustments">
      <div className="look-heading"><h3><SlidersHorizontal size={15}/> Adjust</h3>
        <button className="text-btn" disabled={disabled || !active} onClick={() => {setAdjust({}); onDraft({adjust: {}});}}><RotateCcw size={12}/> Reset all</button></div>
      {(['Light', 'Color', 'Detail'] as const).map(group => <fieldset key={group} className="adjust-group"><legend>{group}</legend>
        {ADJUSTMENTS.filter(a => a.group === group).map(a => {
          const value = adjust[a.key] || 0;
          return <div key={a.key} className={`adjust-row ${value ? 'changed' : ''}`}>
            <label htmlFor={`adj-${a.key}`}>{a.label}</label>
            <input id={`adj-${a.key}`} className={a.min < 0 ? 'bipolar' : ''} aria-label={a.label} type="range" min={a.min} max={100} step={1} value={value} disabled={disabled}
              onChange={e => setOne(a.key, Number(e.target.value))} onDoubleClick={() => setOne(a.key, 0)}/>
            <input aria-label={`${a.label} value`} type="number" min={a.min} max={100} value={value} disabled={disabled}
              onChange={e => {const n = Math.max(a.min, Math.min(100, Math.round(Number(e.target.value) || 0))); setOne(a.key, n);}}/>
            <button className="icon-reset" aria-label={`Reset ${a.label}`} title={`Reset ${a.label}`} disabled={disabled || !value} onClick={() => setOne(a.key, 0)}><RotateCcw size={11}/></button>
          </div>;
        })}
      </fieldset>)}
      <p className="hint">Double-click a slider to reset it. The preview is approximate; render to see the exact grade.</p>
    </section>

    <section className="look-section" aria-label="Color LUT">
      <h3><Palette size={15}/> Color LUT</h3>
      <p className="hint">Apply a .cube colour grade: 3D, 1D, or DaVinci Resolve’s shaper LUTs. Film looks and camera LUTs (Log to Rec709) expect log footage and look very strong on normal video.</p>
      <div className="lut-row">
        <select aria-label="Color LUT" value={lut?.asset_id || ''} disabled={disabled || lutBusy} onChange={e => void onSaveNow({lut: e.target.value ? {asset_id: e.target.value, strength: lut?.strength ?? 100} : null})}>
          <option value="">None</option>
          {luts.map(l => <option key={l.id} value={l.id}>{l.original_filename.replace(/\.cube$/i, '')}</option>)}
        </select>
        <button className="btn" disabled={disabled || lutBusy} onClick={() => lutFile.current?.click()}><Upload size={14}/> {lutBusy ? 'Importing…' : 'Import .cube'}</button>
        <input ref={lutFile} type="file" accept=".cube" multiple hidden aria-label="Import LUT file" onChange={e => void importLuts(e.target.files)}/>
        <input ref={lutFolder} type="file" hidden aria-label="Import LUT folder" {...{webkitdirectory: '', directory: ''} as any} onChange={e => void importLuts(e.target.files)}/>
      </div>
      <button className="text-btn" disabled={disabled || lutBusy} onClick={() => lutFolder.current?.click()}><Upload size={12}/> Import a whole folder of LUTs</button>
      {lutNote && <p className="hint" aria-live="polite">{lutNote}</p>}
      {lut && <label className="control-label">LUT strength · {lut.strength}%
        <input aria-label="LUT strength" type="range" min={0} max={100} step={5} defaultValue={lut.strength} key={lut.asset_id} disabled={disabled}
          onChange={e => onDraft({lut: {asset_id: lut.asset_id, strength: Number(e.target.value)}})}/></label>}
      {lut && <button className="text-btn" disabled={disabled} onClick={() => void onSaveNow({lut: null})}><X size={12}/> Remove LUT</button>}
      {lutError && <p className="form-error" role="alert">{lutError}</p>}
      {lut && scene.shots[0] && <div className="lut-compare" aria-label="LUT before and after">
        <figure><img src={api.assetThumbUrl(scene.shots[0].asset_id, 320)} alt="Before LUT"/><figcaption>Before</figcaption></figure>
        <figure><img src={api.gradedFrameUrl(scene.id, gradeKey(look), 320)} alt="After LUT"/><figcaption>After · {lut.strength}%</figcaption></figure>
      </div>}
      {lut && <p className="hint">The preview shows the LUT’s colour. Render the scene for the final result with motion and effects.</p>}
    </section>
  </div>;
}
