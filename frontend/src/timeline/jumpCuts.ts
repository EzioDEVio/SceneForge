// Jump cuts for timeline audio clips (A3–A8): remove source-time ranges (silences or
// filler words) from clips by cutting them into the kept pieces and closing the gaps.
// Pure: returns a new clip array (or an error) like the other edit operations.
//
// Ranges are in SOURCE time (the clip's audio file), the same time base as
// source_in_ms/source_out_ms and the gain envelope, so envelopes stay valid on every piece.
import {TimelineAudioClip, clipTrack} from './timeline.types';
import {EditResult, clampFades, clipEnd, newClipId} from './editOps';

export type Range = [number, number];
export type JumpCutResult = EditResult & {removed_ms?: number; cuts?: number};

/** Sort, clamp to [lo, hi] and merge overlapping or touching ranges. */
export function mergeRanges(ranges: Range[], lo = -Infinity, hi = Infinity): Range[] {
  const sorted = ranges
    .map(([s, e]) => [Math.max(lo, Math.min(s, e)), Math.min(hi, Math.max(s, e))] as Range)
    .filter(([s, e]) => Number.isFinite(s) && Number.isFinite(e) && e > s)
    .sort((a, b) => a[0] - b[0]);
  const out: Range[] = [];
  for (const [s, e] of sorted) {
    const last = out[out.length - 1];
    if (last && s <= last[1]) last[1] = Math.max(last[1], e);
    else out.push([s, e]);
  }
  return out;
}

/**
 * The source ranges of one clip that remain after removing `ranges`. Cut points snap to
 * `frame`; kept pieces shorter than `minKeep` (default one frame) are dropped too.
 */
export function keptPieces(clip: TimelineAudioClip, ranges: Range[], frame = 1, minKeep = frame): Range[] {
  const lo = clip.source_in_ms, hi = clip.source_out_ms;
  const snap = (v: number) => Math.round(Math.round((v - lo) / frame) * frame + lo);
  const keeps: Range[] = [];
  let cursor = lo;
  for (const [s, e] of mergeRanges(ranges, lo, hi)) {
    const cs = Math.max(lo, snap(s)), ce = Math.min(hi, snap(e));
    if (ce - cs < frame) continue;
    if (cs - cursor >= minKeep) keeps.push([cursor, cs]);
    cursor = Math.max(cursor, ce);
  }
  if (hi - cursor >= minKeep) keeps.push([cursor, hi]);
  return keeps;
}

/**
 * Remove `rangesFor(clip)` from each selected clip. Each clip becomes consecutive pieces
 * (the first keeps the clip's id, fade-in and name; the last keeps the fade-out; edges at
 * a cut get no fade, like Blade). With ripple 'track' (default) later clips on the same
 * track move left by the removed time, like Ripple delete; with 'clip' only the pieces
 * close up and other clips stay put.
 */
export function jumpCuts(
  clips: TimelineAudioClip[], ids: string[], rangesFor: (clip: TimelineAudioClip) => Range[],
  options: {frame?: number; ripple?: 'track' | 'clip'; makeId?: () => string} = {},
): JumpCutResult {
  const frame = Math.max(1, options.frame ?? 1), makeId = options.makeId ?? newClipId, ripple = options.ripple ?? 'track';
  const targets = clips.filter(c => ids.includes(c.id));
  if (!targets.length) return {ok: false, error: 'Select an audio clip to clean up.'};
  const pieces: Record<string, TimelineAudioClip[]> = {};
  const removed: {track: string; end: number; ms: number}[] = [];
  let cuts = 0;
  for (const clip of targets) {
    const keeps = keptPieces(clip, rangesFor(clip), frame);
    const length = clip.source_out_ms - clip.source_in_ms;
    const kept = keeps.reduce((sum, [s, e]) => sum + e - s, 0);
    if (!keeps.length) return {ok: false, error: `Removing those ranges would delete all of “${clip.name}”.`};
    if (kept === length) continue;
    let at = clip.start_ms;
    pieces[clip.id] = keeps.map(([s, e], i) => {
      const piece = clampFades({
        ...clip, id: i === 0 ? clip.id : makeId(), name: i === 0 ? clip.name : `${clip.name} · ${i + 1}`,
        start_ms: at, source_in_ms: s, source_out_ms: e,
        fade_in_ms: i === 0 && s === clip.source_in_ms ? clip.fade_in_ms : 0,
        fade_out_ms: i === keeps.length - 1 && e === clip.source_out_ms ? clip.fade_out_ms : 0,
      });
      at += e - s;
      return piece;
    });
    cuts += mergeRanges(rangesFor(clip), clip.source_in_ms, clip.source_out_ms).length;
    removed.push({track: clipTrack(clip), end: clipEnd(clip), ms: length - kept});
  }
  if (!removed.length) return {ok: false, error: 'Nothing to remove: no range is longer than one frame inside the selected clips.'};
  const out: TimelineAudioClip[] = [];
  for (const c of clips) {
    if (pieces[c.id]) {out.push(...pieces[c.id]); continue;}
    if (ripple === 'track') {
      const shift = removed.filter(r => r.track === clipTrack(c) && c.start_ms >= r.end - 1).reduce((s, r) => s + r.ms, 0);
      if (shift) {out.push({...c, start_ms: Math.max(0, c.start_ms - shift)}); continue;}
    }
    out.push(c);
  }
  // A selected clip that sits after another selected clip on its track also moves left.
  if (ripple === 'track') {
    for (const id of Object.keys(pieces)) {
      const original = targets.find(c => c.id === id)!;
      const shift = removed.filter(r => r.track === clipTrack(original) && original.start_ms >= r.end - 1).reduce((s, r) => s + r.ms, 0);
      if (shift) for (const p of out) if (pieces[id].includes(p)) p.start_ms = Math.max(0, p.start_ms - shift);
    }
  }
  const selected = Object.values(pieces).flat().map(p => p.id);
  return {ok: true, clips: out, selected, cuts, removed_ms: removed.reduce((s, r) => s + r.ms, 0)};
}
