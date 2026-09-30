// Time ↔ pixel transform and frame quantization for the timeline surface.
// `scale` is pixels per second (the existing zoom slider value).

export type TimeTransform = {scale: number; msToPx: (ms: number) => number; pxToMs: (px: number) => number; durationToPx: (ms: number) => number};

export const MIN_SCALE = 0.5;
export const MAX_SCALE = 150;

export function clampScale(scale: number) {
  return Math.max(MIN_SCALE, Math.min(MAX_SCALE, Number.isFinite(scale) ? scale : MIN_SCALE));
}

export function timeTransform(scale: number, originPx = 0): TimeTransform {
  const s = clampScale(scale);
  return {
    scale: s,
    msToPx: ms => originPx + ms / 1000 * s,
    pxToMs: px => (px - originPx) / s * 1000,
    durationToPx: ms => ms / 1000 * s,
  };
}

export function frameMs(fps: number) {
  return Math.max(1, Math.round(1000 / Math.max(1, fps || 30)));
}

export function toFrame(ms: number, fps: number) {
  const f = 1000 / Math.max(1, fps || 30);
  return Math.round(ms / f) * f;
}

/** Zoom around an anchor (usually the pointer) so the time under it stays put. */
export function zoomAround(scale: number, nextScale: number, anchorPx: number, scrollLeft: number) {
  const s = clampScale(nextScale), timeAtAnchor = (scrollLeft + anchorPx) / clampScale(scale);
  return {scale: s, scrollLeft: Math.max(0, timeAtAnchor * s - anchorPx)};
}

/** Visible time window with an overscan margin, used to skip rendering off-screen clips. */
export function visibleWindow(scrollLeft: number, width: number, scale: number, overscanPx = 400) {
  const s = clampScale(scale);
  return {from: Math.max(0, (scrollLeft - overscanPx) / s * 1000), to: (scrollLeft + width + overscanPx) / s * 1000};
}

export function intersectsWindow(start: number, end: number, win: {from: number; to: number}) {
  return end >= win.from && start <= win.to;
}

/** Coalesce rapid pointer updates into one callback per animation frame. */
export function rafCoalesce<T>(apply: (value: T) => void, schedule: (cb: () => void) => unknown = cb => requestAnimationFrame(cb)) {
  let pending: {value: T} | null = null;
  let queued = false;
  const flush = () => {queued = false; const p = pending; pending = null; if (p) apply(p.value);};
  return {
    push(value: T) {pending = {value}; if (!queued) {queued = true; schedule(flush);}},
    flush,
    cancel() {pending = null;},
  };
}
