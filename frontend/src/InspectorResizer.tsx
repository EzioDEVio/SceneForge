import React, {useEffect} from 'react';

const KEY = 'sceneforge.inspectorWidth';
const MIN = 280;
const maxWidth = () => Math.max(MIN, Math.min(760, Math.round(window.innerWidth * 0.55)));

function apply(width: number | null) {
  const shell = document.querySelector<HTMLElement>('.studio-shell');
  if (!shell) return;
  if (width === null) {shell.style.removeProperty('--inspector-width'); return;}
  shell.style.setProperty('--inspector-width', `${Math.round(Math.max(MIN, Math.min(maxWidth(), width)))}px`);
}
function stored(): number | null {
  try {const v = Number(localStorage.getItem(KEY)); return v >= MIN ? v : null;} catch {return null;}
}
function remember(width: number | null) {
  try {width === null ? localStorage.removeItem(KEY) : localStorage.setItem(KEY, String(Math.round(width)));} catch {/* storage unavailable */}
}

/** Drag handle on the left edge of Scene settings. Drag to widen, double-click
 *  to reset, arrow keys for fine steps. The width is remembered. */
export function InspectorResizer() {
  useEffect(() => {apply(stored());}, []);
  const current = () => document.querySelector<HTMLElement>('.inspector')?.getBoundingClientRect().width || 300;
  function drag(e: React.PointerEvent) {
    e.preventDefault();
    const startX = e.clientX, startW = current();
    document.body.classList.add('resizing-inspector');
    const move = (ev: PointerEvent) => apply(startW + (startX - ev.clientX));
    const up = () => {
      window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up);
      document.body.classList.remove('resizing-inspector'); remember(current());
    };
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up);
  }
  return <div className="inspector-resizer" role="separator" aria-orientation="vertical" aria-label="Resize scene settings (double-click to reset)"
    tabIndex={0} title="Drag to resize · double-click to reset" onPointerDown={drag}
    onDoubleClick={() => {apply(null); remember(null);}}
    onKeyDown={e => {if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {e.preventDefault(); const w = current() + (e.key === 'ArrowLeft' ? 20 : -20); apply(w); remember(w);}}}/>;
}
