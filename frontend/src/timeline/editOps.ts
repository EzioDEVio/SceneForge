// Pure edit operations for timeline audio clips (tracks A3–A8).
// Every operation returns a new clip array or an error message; nothing mutates input.
// Times are milliseconds. Callers quantize deltas to frames before calling.
import {AudioTrackId, TimelineAudioClip, clipTrack} from './timeline.types';

export const MIN_CLIP_MS = 100;
export type EditResult = {ok: true; clips: TimelineAudioClip[]; selected?: string[]} | {ok: false; error: string};

const len = (c: TimelineAudioClip) => c.source_out_ms - c.source_in_ms;
export const clipEnd = (c: TimelineAudioClip) => c.start_ms + len(c);
const sourceMax = (c: TimelineAudioClip) => c.source_duration_ms || c.source_out_ms;

/** Keep fades inside the clip after its length changes (fade-in wins). */
export function clampFades(c: TimelineAudioClip): TimelineAudioClip {
  const d = Math.max(0, len(c)), fadeIn = Math.min(c.fade_in_ms, d);
  return {...c, fade_in_ms: fadeIn, fade_out_ms: Math.min(c.fade_out_ms, Math.max(0, d - fadeIn))};
}

function replace(clips: TimelineAudioClip[], changed: Record<string, TimelineAudioClip>) {
  return clips.map(c => changed[c.id] ? clampFades(changed[c.id]) : c);
}

const find = (clips: TimelineAudioClip[], id: string) => clips.find(c => c.id === id);
const sameTrack = (a: TimelineAudioClip, b: TimelineAudioClip) => clipTrack(a) === clipTrack(b);

/** Clips on the same track that touch `clip`'s edges (within a tolerance, usually one frame). */
export function neighbours(clips: TimelineAudioClip[], clip: TimelineAudioClip, tolerance = 1) {
  const others = clips.filter(c => c.id !== clip.id && sameTrack(c, clip));
  return {
    before: others.find(c => Math.abs(clipEnd(c) - clip.start_ms) <= tolerance) ?? null,
    after: others.find(c => Math.abs(c.start_ms - clipEnd(clip)) <= tolerance) ?? null,
  };
}

let idSeq = 0;
export const newClipId = () => (globalThis.crypto?.randomUUID?.() ?? `clip-${Date.now().toString(36)}-${(idSeq++).toString(36)}`);

/** Blade: cut one clip at timeline time `at`. */
export function blade(clips: TimelineAudioClip[], id: string, at: number, frame = 1, makeId = newClipId): EditResult {
  const clip = find(clips, id);
  if (!clip) return {ok: false, error: 'Select an audio clip to cut.'};
  const rel = Math.round((at - clip.start_ms) / frame) * frame;
  if (rel < frame || rel > len(clip) - frame) return {ok: false, error: 'Cut at least one frame inside the clip.'};
  const cut = clip.source_in_ms + rel;
  const left = clampFades({...clip, source_out_ms: cut, fade_out_ms: 0});
  const right = clampFades({...clip, id: makeId(), name: `${clip.name} · B`, start_ms: clip.start_ms + rel, source_in_ms: cut, fade_in_ms: 0});
  const out: TimelineAudioClip[] = [];
  for (const c of clips) out.push(...(c.id === id ? [left, right] : [c]));
  return {ok: true, clips: out, selected: [right.id]};
}

/** Razor all: cut every clip under `at` on the given (unlocked) tracks. */
export function bladeAll(clips: TimelineAudioClip[], at: number, tracks: AudioTrackId[], frame = 1, makeId = newClipId): EditResult {
  let current = clips, cuts = 0;
  const targets = clips.filter(c => tracks.includes(clipTrack(c)) && at - c.start_ms >= frame && clipEnd(c) - at >= frame);
  const selected: string[] = [];
  for (const t of targets) {
    const r = blade(current, t.id, at, frame, makeId);
    if (r.ok) {current = r.clips; cuts++; selected.push(...(r.selected || []));}
  }
  return cuts ? {ok: true, clips: current, selected} : {ok: false, error: 'No unlocked audio clip crosses the playhead.'};
}

/** Move one or more clips in time, optionally to another track. Clips never start before 0. */
export function moveClips(clips: TimelineAudioClip[], ids: string[], delta: number, track?: AudioTrackId): EditResult {
  const moving = clips.filter(c => ids.includes(c.id));
  if (!moving.length) return {ok: false, error: 'Select a clip to move.'};
  const earliest = Math.min(...moving.map(c => c.start_ms));
  const d = Math.max(-earliest, delta);
  const changed: Record<string, TimelineAudioClip> = {};
  for (const c of moving) changed[c.id] = {...c, start_ms: c.start_ms + d, ...(track ? {track} : {})};
  return {ok: true, clips: replace(clips, changed), selected: ids};
}

/** Plain trim of one edge. `delta` > 0 moves the edge later. */
export function trim(clips: TimelineAudioClip[], id: string, edge: 'in' | 'out', delta: number): EditResult {
  const c = find(clips, id);
  if (!c) return {ok: false, error: 'Select a clip to trim.'};
  if (edge === 'in') {
    const nextIn = Math.max(0, Math.max(c.source_in_ms - c.start_ms, Math.min(c.source_out_ms - MIN_CLIP_MS, c.source_in_ms + delta)));
    return {ok: true, clips: replace(clips, {[id]: {...c, source_in_ms: nextIn, start_ms: c.start_ms + nextIn - c.source_in_ms}}), selected: [id]};
  }
  const nextOut = Math.max(c.source_in_ms + MIN_CLIP_MS, Math.min(sourceMax(c), c.source_out_ms + delta));
  return {ok: true, clips: replace(clips, {[id]: {...c, source_out_ms: nextOut}}), selected: [id]};
}

/**
 * Ripple trim (B): trim an edge and shift every later clip on the same track by the
 * change in length, so no gap opens or overlap forms. The in-edge keeps the clip's start.
 */
export function rippleTrim(clips: TimelineAudioClip[], id: string, edge: 'in' | 'out', delta: number): EditResult {
  const c = find(clips, id);
  if (!c) return {ok: false, error: 'Select a clip to ripple trim.'};
  let next: TimelineAudioClip;
  if (edge === 'in') {
    const nextIn = Math.max(0, Math.min(c.source_out_ms - MIN_CLIP_MS, c.source_in_ms + delta));
    next = {...c, source_in_ms: nextIn};
  } else {
    next = {...c, source_out_ms: Math.max(c.source_in_ms + MIN_CLIP_MS, Math.min(sourceMax(c), c.source_out_ms + delta))};
  }
  const shift = len(next) - len(c), end = clipEnd(c);
  const changed: Record<string, TimelineAudioClip> = {[id]: next};
  for (const o of clips) if (o.id !== id && sameTrack(o, c) && o.start_ms >= end - 1) changed[o.id] = {...o, start_ms: Math.max(0, o.start_ms + shift)};
  return {ok: true, clips: replace(clips, changed), selected: [id]};
}

/** Ripple delete: remove clips and pull later clips on each affected track left by the removed length. */
export function rippleDelete(clips: TimelineAudioClip[], ids: string[]): EditResult {
  const removed = clips.filter(c => ids.includes(c.id));
  if (!removed.length) return {ok: false, error: 'Select a clip to ripple delete.'};
  const remaining = clips.filter(c => !ids.includes(c.id));
  return {ok: true, selected: [], clips: remaining.map(o => {
    const shift = removed.filter(r => sameTrack(r, o) && o.start_ms >= clipEnd(r) - 1).reduce((s, r) => s + len(r), 0);
    return shift ? {...o, start_ms: Math.max(0, o.start_ms - shift)} : o;
  })};
}

/** Roll (N): move the edit point between two touching clips; total length is unchanged. */
export function roll(clips: TimelineAudioClip[], leftId: string, rightId: string, delta: number): EditResult {
  const l = find(clips, leftId), r = find(clips, rightId);
  if (!l || !r || !sameTrack(l, r)) return {ok: false, error: 'Roll needs two touching clips on the same track.'};
  const lo = Math.max(MIN_CLIP_MS - len(l), -r.source_in_ms);
  const hi = Math.min(sourceMax(l) - l.source_out_ms, len(r) - MIN_CLIP_MS);
  if (lo > hi) return {ok: false, error: 'Neither clip has media left to roll into.'};
  const d = Math.max(lo, Math.min(hi, delta));
  return {ok: true, selected: [leftId, rightId], clips: replace(clips, {
    [leftId]: {...l, source_out_ms: l.source_out_ms + d},
    [rightId]: {...r, start_ms: r.start_ms + d, source_in_ms: r.source_in_ms + d},
  })};
}

/** Slip (Y): change which part of the source plays, keeping position and length. */
export function slip(clips: TimelineAudioClip[], id: string, delta: number): EditResult {
  const c = find(clips, id);
  if (!c) return {ok: false, error: 'Select a clip to slip.'};
  const d = Math.max(-c.source_in_ms, Math.min(sourceMax(c) - c.source_out_ms, delta));
  if (!d && delta) return {ok: false, error: 'The clip already uses the start or end of its source.'};
  return {ok: true, selected: [id], clips: replace(clips, {[id]: {...c, source_in_ms: c.source_in_ms + d, source_out_ms: c.source_out_ms + d}})};
}

/**
 * Slide (U): move a clip between its touching neighbours. The previous clip's end and
 * the next clip's start follow it, so the track's total length and the clip's content stay the same.
 */
export function slide(clips: TimelineAudioClip[], id: string, delta: number, tolerance = 1): EditResult {
  const c = find(clips, id);
  if (!c) return {ok: false, error: 'Select a clip to slide.'};
  const {before, after} = neighbours(clips, c, tolerance);
  let lo = -c.start_ms, hi = Number.POSITIVE_INFINITY;
  if (before) {lo = Math.max(lo, MIN_CLIP_MS - len(before)); hi = Math.min(hi, sourceMax(before) - before.source_out_ms);}
  if (after) {lo = Math.max(lo, -after.source_in_ms); hi = Math.min(hi, len(after) - MIN_CLIP_MS);}
  if (lo > hi) return {ok: false, error: 'The neighbouring clips have no media left to slide into.'};
  const d = Math.max(lo, Math.min(hi, delta));
  const changed: Record<string, TimelineAudioClip> = {[id]: {...c, start_ms: c.start_ms + d}};
  if (before) changed[before.id] = {...before, source_out_ms: before.source_out_ms + d};
  if (after) changed[after.id] = {...after, start_ms: after.start_ms + d, source_in_ms: after.source_in_ms + d};
  return {ok: true, clips: replace(clips, changed), selected: [id]};
}

/** Track select forward (A): every clip on the track that starts at or after `at`. */
export function trackSelectForward(clips: TimelineAudioClip[], track: AudioTrackId, at: number) {
  return clips.filter(c => clipTrack(c) === track && c.start_ms >= at - 1).map(c => c.id);
}

/** Stack overlapping clips into rows so touching clips share a row (needed to see rolls/slides). */
export function packRows(clips: TimelineAudioClip[]): Record<string, number> {
  const rows: number[] = [], out: Record<string, number> = {};
  for (const c of [...clips].sort((a, b) => a.start_ms - b.start_ms || a.id.localeCompare(b.id))) {
    let row = rows.findIndex(end => end <= c.start_ms + 0.5);
    if (row < 0) {row = rows.length; rows.push(0);}
    rows[row] = clipEnd(c); out[c.id] = row;
  }
  return out;
}
