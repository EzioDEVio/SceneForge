import React, {useEffect, useState} from 'react';
import {ArrowDown, ArrowUp, Layers, RotateCcw} from 'lucide-react';
import type {Look} from './api';
import {FeatureHelp} from './FeatureHelp';

/** Scene-level effects that can be reordered (backend render/fx_stack.py STACK_IDS, default order). */
export const STACK_IDS = ['spotlight', 'leak', 'flare', 'wiggle', 'shake'] as const;
export type StackId = typeof STACK_IDS[number];
export const STACK_LABELS: Record<StackId, string> = {spotlight: 'Spotlight', leak: 'Light leaks', flare: 'Lens flare', wiggle: 'Wiggle', shake: 'Camera shake'};

/** Same rules as fx_stack.is_enabled: the effect has settings that change the picture. */
export function stackEnabled(look: any, id: StackId): boolean {
  const v = look?.[id];
  if (!v) return false;
  if (id === 'spotlight') return true;
  if (id === 'shake') return (v.amount ?? 0) > 0 || !!v.impact;
  return (v.amount ?? 0) > 0;
}
/** Same rules as fx_stack.resolved_order: listed ids first, the rest in default order. */
export function stackOrder(order?: string[] | null): StackId[] {
  const listed = (order || []).filter((i): i is StackId => (STACK_IDS as readonly string[]).includes(i));
  return [...listed, ...STACK_IDS.filter(i => !listed.includes(i))];
}

export const STACK_CSS = `
.sf-stack-chain{display:flex;flex-direction:column;align-items:stretch;gap:2px;margin:8px 0 10px}
.sf-stack-io{align-self:center;font-size:10px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:var(--muted);border:1px dashed var(--line);border-radius:12px;padding:2px 10px}
.sf-stack-arrow{align-self:center;color:var(--muted);line-height:1;font-size:12px}
.sf-stack-node{display:flex;align-items:center;gap:6px;border:1px solid var(--line);border-radius:8px;padding:6px 8px;background:color-mix(in srgb,var(--blue) 7%,transparent);cursor:grab}
.sf-stack-node.bypassed{opacity:.55;background:transparent;border-style:dashed}
.sf-stack-node.bypassed .sf-stack-name{text-decoration:line-through}
.sf-stack-node.drop-target{border-color:var(--blue);box-shadow:0 0 0 1px var(--blue)}
.sf-stack-pos{font-size:10px;color:var(--muted);min-width:14px}
.sf-stack-name{flex:1;font-size:12px;font-weight:600;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sf-stack-node .icon-btn{width:24px;height:24px;border-radius:6px}
.sf-stack-bypass{display:flex;align-items:center;gap:4px;font-size:10px;color:var(--muted);white-space:nowrap}
`;

/** "Effect stack": the scene-level FX as a short chain of nodes (Input → … → Output).
 *  Reorder with drag-and-drop or ▲▼, bypass per node, reset to the default order.
 *  Writes look.fx_order / look.fx_bypass through the normal scene draft. */
export function EffectStack({look, disabled, onDraft}: {look: Look | Record<string, any>; disabled: boolean; onDraft: (look: Look) => void}) {
  const l = (look || {}) as any;
  const serverKey = JSON.stringify([l.fx_order || null, l.fx_bypass || null]);
  const [local, setLocal] = useState<{order: StackId[]; bypass: StackId[]} | null>(null);
  const [dragging, setDragging] = useState<StackId | null>(null);
  const [over, setOver] = useState<StackId | null>(null);
  const [note, setNote] = useState('');
  useEffect(() => setLocal(null), [serverKey]);       // the saved scene wins once it comes back
  const order = local?.order ?? stackOrder(l.fx_order);
  const bypass = local?.bypass ?? ((l.fx_bypass || []) as StackId[]);
  const nodes = order.filter(id => stackEnabled(l, id));
  const custom = !!(l.fx_order?.length || l.fx_bypass?.length || local);

  const save = (nextNodes: StackId[], nextBypass: StackId[], message: string) => {
    // Keep effects that are off where they were (after the active ones) so turning them back on is predictable.
    const nextOrder = [...nextNodes, ...order.filter(id => !nextNodes.includes(id))];
    setLocal({order: nextOrder, bypass: nextBypass});
    setNote(message);
    onDraft({fx_order: nextNodes.length ? nextNodes : null, fx_bypass: nextBypass.length ? nextBypass : null});
  };
  const move = (id: StackId, to: number) => {
    const from = nodes.indexOf(id);
    if (from < 0 || to < 0 || to >= nodes.length || to === from) return;
    const next = nodes.filter(x => x !== id);
    next.splice(to, 0, id);
    save(next, bypass, `${STACK_LABELS[id]} moved to position ${to + 1} of ${nodes.length}.`);
  };
  const toggleBypass = (id: StackId, on: boolean) =>
    save(nodes, on ? [...bypass.filter(x => x !== id), id] : bypass.filter(x => x !== id), `${STACK_LABELS[id]} ${on ? 'bypassed' : 'active again'}.`);
  const reset = () => {
    setLocal({order: [...STACK_IDS], bypass: []});
    setNote('Effect stack reset to the default order.');
    onDraft({fx_order: null, fx_bypass: null});
  };

  return <section className="look-section" aria-label="Effect stack">
    <style>{STACK_CSS}</style>
    <div className="look-heading"><h3><Layers size={15}/> Effect stack</h3>
      <FeatureHelp compact title="Effect stack" description="The scene-wide effects run one after another, top to bottom, like nodes in a chain. Changing the order changes the picture: Camera shake before Lens flare shakes the picture under a steady flare (it looks attached to the lens); Lens flare before Camera shake makes the flare shake with the picture (it looks attached to the scene). Blur regions, overlays, routes and annotations always come first and keep their place."
        steps="Drag a node, or use the up and down arrows, to change the order. Bypass skips an effect but keeps its settings. Reset returns to the default order. Render the scene to see the result — the live preview does not show the order."/>
    </div>
    <p className="hint">Order matters: e.g. shake before flare keeps the flare steady on the lens; flare before shake shakes it with the picture. Bypass skips an effect but keeps its settings. Render to see the result.</p>
    {nodes.length === 0
      ? <p className="hint">Turn on Spotlight, Light leaks, Lens flare, Wiggle or Camera shake above to build a stack.</p>
      : <ol className="sf-stack-chain" aria-label="Effect order, from input to output" style={{listStyle: 'none', padding: 0}}>
        <li className="sf-stack-io" aria-hidden="true">Input</li>
        {nodes.map((id, i) => <React.Fragment key={id}>
          <li className="sf-stack-arrow" aria-hidden="true">↓</li>
          <li className={`sf-stack-node ${bypass.includes(id) ? 'bypassed' : ''} ${over === id && dragging && dragging !== id ? 'drop-target' : ''}`}
            draggable={!disabled} aria-label={`${i + 1}. ${STACK_LABELS[id]}${bypass.includes(id) ? ' (bypassed)' : ''}`}
            onDragStart={e => {setDragging(id); e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/x-sceneforge-fx', id);}}
            onDragEnd={() => {setDragging(null); setOver(null);}}
            onDragOver={e => {if (dragging) {e.preventDefault(); setOver(id);}}}
            onDragLeave={() => setOver(o => o === id ? null : o)}
            onDrop={e => {e.preventDefault(); if (dragging) move(dragging, i); setDragging(null); setOver(null);}}>
            <span className="sf-stack-pos" aria-hidden="true">{i + 1}</span>
            <span className="sf-stack-name">{STACK_LABELS[id]}</span>
            <label className="sf-stack-bypass"><input type="checkbox" aria-label={`Bypass ${STACK_LABELS[id]}`} checked={bypass.includes(id)} disabled={disabled} onChange={e => toggleBypass(id, e.target.checked)}/>Bypass</label>
            <button type="button" className="icon-btn" aria-label={`Move ${STACK_LABELS[id]} earlier`} title="Move earlier" disabled={disabled || i === 0} onClick={() => move(id, i - 1)}><ArrowUp size={13}/></button>
            <button type="button" className="icon-btn" aria-label={`Move ${STACK_LABELS[id]} later`} title="Move later" disabled={disabled || i === nodes.length - 1} onClick={() => move(id, i + 1)}><ArrowDown size={13}/></button>
          </li>
        </React.Fragment>)}
        <li className="sf-stack-arrow" aria-hidden="true">↓</li>
        <li className="sf-stack-io" aria-hidden="true">Output</li>
      </ol>}
    <button type="button" className="text-btn" disabled={disabled || !custom} onClick={reset}><RotateCcw size={13}/> Reset effect order</button>
    <p aria-live="polite" style={{position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0 0 0 0)'}}>{note}</p>
  </section>;
}
