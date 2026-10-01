import React, {useEffect, useRef, useState} from 'react';
import {Download, Package, Save, Trash2, Upload} from 'lucide-react';
import {api, lookPresetApi, type LookPack, type LookPreset, type Scene} from './api';
import {askConfirm, askText} from './dialogs';
import {FeatureHelp} from './FeatureHelp';

const PACK_EXT = /\.(json|sflook)$/i;
const MAX_PACK_BYTES = 1024 * 1024;
const FALLBACK_KEYS = ['adjust', 'tone', 'wheels', 'film', 'glitch', 'focus', 'mosaic', 'rgbsplit', 'leak', 'flare', 'wiggle', 'shake', 'fx_order', 'fx_bypass'];

/** JSON with sorted object keys, so server echoes compare equal regardless of key order. */
function stable(v: unknown): string {
  if (Array.isArray(v)) return `[${v.map(stable).join(',')}]`;
  if (v && typeof v === 'object') return `{${Object.keys(v as object).sort().map(k => `${JSON.stringify(k)}:${stable((v as any)[k])}`).join(',')}}`;
  return JSON.stringify(v ?? null);
}
type LookState = {effect_preset: string; effect_intensity: number; look: Record<string, unknown>};
const signature = (s: LookState, keys: string[]) => stable({p: s.effect_preset, i: s.effect_intensity, l: keys.map(k => s.look?.[k] ?? null)});

export function downloadJson(data: unknown, filename: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'}));
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.style.display = 'none';
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
/** File.text() with a FileReader fallback (older webviews and test DOMs lack Blob.text). */
const readText = (f: File): Promise<string> => typeof (f as any).text === 'function' ? f.text()
  : new Promise((resolve, reject) => {const r = new FileReader(); r.onload = () => resolve(String(r.result ?? '')); r.onerror = () => reject(r.error); r.readAsText(f);});
const fileSafe = (s: string) => s.replace(/[^\w\- ]+/g, '').trim().replace(/\s+/g, '-').toLowerCase() || 'look';

export const PRESETS_CSS = `
.sf-presets.drop-active{outline:2px dashed var(--blue);outline-offset:4px;border-radius:8px}
.sf-presets-drop{font-size:11px;color:var(--blue);font-weight:600;margin:4px 0 8px}
.sf-preset-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;margin:6px 0 12px}
.sf-preset{position:relative;display:flex}
.sf-preset-apply{flex:1;min-width:0;text-align:left;border:1px solid var(--line);border-radius:8px;background:color-mix(in srgb,var(--blue) 6%,transparent);color:var(--text);padding:7px 8px;font-size:11px;font-weight:600;line-height:1.3}
.sf-preset-apply small{display:block;font-weight:400;color:var(--muted);font-size:10px;margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sf-preset-apply:hover:not(:disabled){border-color:var(--blue)}
.sf-preset-delete{position:absolute;top:3px;right:3px;border:0;background:transparent;color:var(--muted);padding:2px;border-radius:4px}
.sf-preset-delete:hover{color:var(--danger,#e5484d)}
.sf-presets-actions{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0}
.sf-presets-actions .btn{font-size:11px;padding:6px 9px}
.sf-presets-msg{font-size:11px;margin:4px 0}
.sf-presets-msg.error{color:var(--danger,#e5484d)}
`;

/** "Look presets": built-in starter pack + the user's own presets (stored by the backend in
 *  the data folder). Click a tile to apply it to this scene (undoable); import packs by
 *  drag-and-drop onto the Effects panel or with "Import pack"; save / export looks as JSON. */
export function LookPresets({scene, disabled, flush, onRecord, onApplied}: {scene: Scene; disabled: boolean; flush: () => Promise<boolean>;
  onRecord: (label: string, undo: () => Promise<unknown>, redo: () => Promise<unknown>) => unknown; onApplied: () => void}) {
  const [mine, setMine] = useState<LookPreset[]>([]);
  const [builtin, setBuiltin] = useState<LookPreset[]>([]);
  const [keys, setKeys] = useState<string[]>(FALLBACK_KEYS);
  const [unavailable, setUnavailable] = useState(false);
  const [msg, setMsg] = useState<{text: string; error?: boolean} | null>(null);
  const [busy, setBusy] = useState(false);
  const [dropActive, setDropActive] = useState(false);
  const root = useRef<HTMLElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const expect = useRef<string | null>(null);
  const alive = useRef(true);
  useEffect(() => () => {alive.current = false;}, []);

  useEffect(() => {
    lookPresetApi.list().then(r => {if (!alive.current) return; setMine(r.presets || []); setBuiltin(r.builtin || []); if (r.look_keys?.length) setKeys(r.look_keys);})
      .catch(() => {if (alive.current) setUnavailable(true);});
  }, []);

  // After a preset is applied, undone or redone, remount the effect panels once the saved scene arrives.
  const current: LookState = {effect_preset: scene.effect_preset, effect_intensity: scene.effect_intensity, look: (scene.look_json || {}) as Record<string, unknown>};
  const currentSig = signature(current, keys);
  useEffect(() => {if (expect.current && expect.current === currentSig) {expect.current = null; onApplied();}}, [currentSig]);

  const apply = async (p: LookPreset) => {
    if (disabled || busy) return;
    if (!(await flush())) return;
    const before = {effect_preset: scene.effect_preset, effect_intensity: scene.effect_intensity, look: Object.fromEntries(keys.map(k => [k, (scene.look_json as any)?.[k] ?? null]))};
    const after = {effect_preset: p.effect_preset, effect_intensity: p.effect_intensity, look: Object.fromEntries(keys.map(k => [k, p.look?.[k] ?? null]))};
    const sigBefore = signature(before as LookState, keys), sigAfter = signature(after as LookState, keys);
    const id = scene.id;
    await onRecord(`look preset “${p.name}”`,
      async () => {expect.current = sigBefore; return api.updateScene(id, before);},
      async () => {expect.current = sigAfter; return api.updateScene(id, after);});
    if (alive.current) setMsg({text: `Applied “${p.name}”. Undo restores the previous look.`});
  };

  const importText = async (text: string, filename: string) => {
    let pack: unknown;
    try {pack = JSON.parse(text);} catch {setMsg({text: `“${filename}” is not valid JSON, so it can't be a look pack.`, error: true}); return;}
    try {
      const r = await lookPresetApi.importPack(pack);
      if (!alive.current) return;
      setMine(r.presets);
      setMsg({text: `Imported ${r.added.length} preset${r.added.length === 1 ? '' : 's'} from “${filename}”: ${r.added.map(p => p.name).join(', ')}.`});
    } catch (e: any) {
      if (alive.current) setMsg({text: `Couldn't import “${filename}”: ${e.message || e}`, error: true});
    }
  };
  const importFiles = async (files: File[]) => {
    const packs = files.filter(f => PACK_EXT.test(f.name));
    if (!packs.length) {setMsg({text: 'Drop a .json or .sflook look pack file.', error: true}); return;}
    setBusy(true);
    try {
      for (const f of packs) {
        if (f.size > MAX_PACK_BYTES) {setMsg({text: `“${f.name}” is larger than 1 MB, which is too big for a look pack.`, error: true}); continue;}
        await importText(await readText(f), f.name);
      }
    } finally {if (alive.current) setBusy(false);}
  };

  // Drag-and-drop a pack anywhere on the Effects panel (the inspector tab panel around this section).
  useEffect(() => {
    const el = (root.current?.closest('[role="tabpanel"]') as HTMLElement | null) ?? root.current;
    if (!el) return;
    const hasFiles = (e: DragEvent) => Array.from(e.dataTransfer?.types || []).includes('Files');
    const over = (e: DragEvent) => {if (!hasFiles(e) || disabled) return; e.preventDefault(); if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy'; setDropActive(true);};
    const leave = (e: DragEvent) => {if (!el.contains(e.relatedTarget as Node | null)) setDropActive(false);};
    const drop = (e: DragEvent) => {
      setDropActive(false);
      if (!hasFiles(e) || disabled) return;
      const files = Array.from(e.dataTransfer?.files || []);
      if (!files.some(f => PACK_EXT.test(f.name))) return;          // not a pack: leave it to other handlers
      e.preventDefault(); e.stopPropagation();
      void importFiles(files);
    };
    el.addEventListener('dragover', over); el.addEventListener('dragleave', leave); el.addEventListener('drop', drop);
    return () => {el.removeEventListener('dragover', over); el.removeEventListener('dragleave', leave); el.removeEventListener('drop', drop);};
  }, [disabled]);

  const saveCurrent = async () => {
    if (!(await flush())) return;
    const name = (await askText('Name this look preset', scene.title ? `${scene.title} look` : 'My look'))?.trim();
    if (!name) return;
    try {
      const pack = await lookPresetApi.fromScene(scene.id, name.slice(0, 60));
      const r = await lookPresetApi.importPack(pack);
      if (!alive.current) return;
      setMine(r.presets); setMsg({text: `Saved “${r.added[0]?.name || name}” to My presets.`});
    } catch (e: any) {if (alive.current) setMsg({text: `Couldn't save the preset: ${e.message || e}`, error: true});}
  };
  const exportScene = async () => {
    if (!(await flush())) return;
    try {
      const pack: LookPack = await lookPresetApi.fromScene(scene.id, scene.title ? `${scene.title} look`.slice(0, 60) : 'My look');
      downloadJson(pack, `${fileSafe(pack.presets[0]?.name || 'look')}.sflook.json`);
      setMsg({text: 'Exported this scene’s look as a look pack.'});
    } catch (e: any) {setMsg({text: `Couldn't export the look: ${e.message || e}`, error: true});}
  };
  const exportMine = async () => {
    try {downloadJson(await lookPresetApi.exportPack(), 'my-sceneforge-looks.json'); setMsg({text: `Exported ${mine.length} preset${mine.length === 1 ? '' : 's'}.`});}
    catch (e: any) {setMsg({text: `Couldn't export: ${e.message || e}`, error: true});}
  };
  const remove = async (p: LookPreset) => {
    if (!p.id || !(await askConfirm(`Delete the preset “${p.name}”? Scenes that already use it keep their look.`))) return;
    try {const r = await lookPresetApi.remove(p.id); if (alive.current) {setMine(r.presets); setMsg({text: `Deleted “${p.name}”.`});}}
    catch (e: any) {if (alive.current) setMsg({text: `Couldn't delete: ${e.message || e}`, error: true});}
  };

  const tile = (p: LookPreset) => <div className="sf-preset" key={p.id || p.name}>
    <button type="button" className="sf-preset-apply" disabled={disabled || busy} title={p.description || p.name}
      aria-label={`Apply look preset ${p.name}${p.description ? `: ${p.description}` : ''}`} onClick={() => void apply(p)}>
      {p.name}<small>{p.effect_preset.replace(/_/g, ' ')} · {p.effect_intensity}%</small>
    </button>
    {!p.builtin && p.id && <button type="button" className="sf-preset-delete" aria-label={`Delete look preset ${p.name}`} title="Delete preset" onClick={() => void remove(p)}><Trash2 size={11}/></button>}
  </div>;

  return <section ref={root} className={`look-section sf-presets ${dropActive ? 'drop-active' : ''}`} aria-label="Look presets">
    <style>{PRESETS_CSS}</style>
    <div className="look-heading"><h3><Package size={15}/> Look presets</h3>
      <FeatureHelp compact title="Look presets" description="A look preset stores the effect, its strength and the portable look settings (colour, tone, wheels, film, grain, flare, leaks, shake, wiggle, focus, mosaic, RGB split and the effect stack order). Media-specific settings — overlays, routes, annotations, blur regions, spotlight and LUT files — are never part of a preset."
        steps="Click a preset to apply it to this scene (Undo puts the previous look back). Drag a .json or .sflook look pack onto the Effects panel, or use Import pack. Save current look adds this scene's look to My presets; Export pack downloads your presets to share."/>
    </div>
    {unavailable
      ? <p className="hint">Look presets need the latest SceneForge backend. Restart SceneForge to use them.</p>
      : <>
        <p className="hint">Apply a ready-made look in one click, or drop a look pack (.json / .sflook) anywhere on this panel to import it.</p>
        {dropActive && <p className="sf-presets-drop" aria-live="polite">Drop the look pack to import it</p>}
        {builtin.length > 0 && <><h4 className="hint" style={{margin: '6px 0 0'}}>Starter pack</h4>
          <div className="sf-preset-grid" role="group" aria-label="Starter pack presets">{builtin.map(tile)}</div></>}
        <h4 className="hint" style={{margin: '6px 0 0'}}>My presets</h4>
        {mine.length ? <div className="sf-preset-grid" role="group" aria-label="My presets">{mine.map(tile)}</div>
          : <p className="hint">None yet — save this scene's look or import a pack.</p>}
        <div className="sf-presets-actions">
          <button type="button" className="btn" disabled={disabled || busy} onClick={() => void saveCurrent()}><Save size={13}/> Save current look as preset</button>
          <button type="button" className="btn" disabled={disabled || busy} onClick={() => fileInput.current?.click()}><Upload size={13}/> Import pack</button>
          <button type="button" className="btn" disabled={busy || !mine.length} onClick={() => void exportMine()}><Download size={13}/> Export pack</button>
          <button type="button" className="btn" disabled={busy} onClick={() => void exportScene()}><Download size={13}/> Export scene look</button>
        </div>
        <input ref={fileInput} type="file" accept=".json,.sflook,application/json" hidden aria-label="Import look pack file"
          onChange={e => {const files = Array.from(e.target.files || []); e.target.value = ''; if (files.length) void importFiles(files);}}/>
      </>}
    {msg && <p className={`sf-presets-msg ${msg.error ? 'error' : 'hint'}`} aria-live={msg.error ? 'assertive' : 'polite'}>{msg.text}</p>}
  </section>;
}
