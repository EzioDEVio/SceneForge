// Timeline model shared by the editor surface, edit operations and persistence.
//
// Picture (V1), text (T1), narration (A1) and source-video sound (A2) remain
// scene-based. Timeline audio clips live on independent audio tracks A3–A8 and
// are stored in project.finishing_json.audio_clips. Per-track state, markers
// and the visible track list are stored in project.finishing_json.timeline.
// Projects saved before timeline version 1 have no `timeline` key and clips
// without `track`; normalizeTimeline/clipTrack give them the old meaning (A3).
import type {ProjectAudioClip} from '../api';

export const TIMELINE_VERSION = 1;
export const SCENE_TRACKS = ['T1', 'V1', 'A1', 'A2'] as const;
export const AUDIO_TRACKS = ['A3', 'A4', 'A5', 'A6', 'A7', 'A8'] as const;
export type SceneTrackId = typeof SCENE_TRACKS[number];
export type AudioTrackId = typeof AUDIO_TRACKS[number];
export type TrackId = SceneTrackId | AudioTrackId;

export type TrackState = {locked?: boolean; mute?: boolean; solo?: boolean};
export const MARKER_COLORS = ['amber', 'red', 'green', 'blue', 'purple'] as const;
export type MarkerColor = typeof MARKER_COLORS[number];
/** duration_ms > 0 makes a range marker (e.g. a section or a music cue). */
/** clip_id + offset_ms attach a marker to a timeline audio clip: it moves with the clip. */
export type TimelineMarker = {id: string; time_ms: number; duration_ms: number; label: string; color: MarkerColor; clip_id?: string; offset_ms?: number};
export type TimelineSettings = {
  version: number;
  tracks: Partial<Record<TrackId, TrackState>>;
  /** Audio tracks shown even when empty. A3 is always shown. */
  audio_tracks: AudioTrackId[];
  markers: TimelineMarker[];
};
export type TimelineAudioClip = ProjectAudioClip & {track?: AudioTrackId};

/** V select, A track-select forward, B ripple, N roll, Y slip, U slide, C blade. */
export type TimelineTool = 'select' | 'track_select' | 'ripple' | 'roll' | 'slip' | 'slide' | 'blade';
export const TOOL_KEYS: Record<string, TimelineTool> = {v: 'select', a: 'track_select', b: 'ripple', n: 'roll', y: 'slip', u: 'slide', c: 'blade'};
export const TOOL_LABELS: Record<TimelineTool, [string, string]> = {
  select: ['Select', 'V'], track_select: ['Track select forward', 'A'], ripple: ['Ripple trim', 'B'],
  roll: ['Roll edit', 'N'], slip: ['Slip', 'Y'], slide: ['Slide', 'U'], blade: ['Blade', 'C'],
};

export const MAX_MARKERS = 200;
const isAudioTrack = (v: unknown): v is AudioTrackId => typeof v === 'string' && (AUDIO_TRACKS as readonly string[]).includes(v);
const isTrack = (v: unknown): v is TrackId => isAudioTrack(v) || (typeof v === 'string' && (SCENE_TRACKS as readonly string[]).includes(v));

export function clipTrack(clip: {track?: unknown}): AudioTrackId {
  return isAudioTrack(clip.track) ? clip.track : 'A3';
}

export function emptyTimeline(): TimelineSettings {
  return {version: TIMELINE_VERSION, tracks: {}, audio_tracks: ['A3'], markers: []};
}

function cleanMarker(raw: any, index: number): TimelineMarker | null {
  if (!raw || typeof raw !== 'object') return null;
  // Legacy browser-stored markers used {time,label}; v1 uses time_ms.
  const time = Number(raw.time_ms ?? raw.time);
  if (!Number.isFinite(time) || time < 0) return null;
  const duration = Number(raw.duration_ms ?? 0);
  return {
    id: typeof raw.id === 'string' && raw.id ? raw.id.slice(0, 64) : `m${index}`,
    time_ms: Math.round(time),
    duration_ms: Number.isFinite(duration) && duration > 0 ? Math.round(duration) : 0,
    label: String(raw.label ?? `Marker ${index + 1}`).slice(0, 120),
    color: (MARKER_COLORS as readonly string[]).includes(raw.color) ? raw.color : 'amber',
    ...(typeof raw.clip_id === 'string' && raw.clip_id ? {clip_id: raw.clip_id.slice(0, 64), offset_ms: Math.max(0, Math.round(Number(raw.offset_ms) || 0))} : {}),
  };
}

/**
 * Bring any stored timeline (missing, v0 browser data, or v1) to the current version.
 * `legacy` carries the pre-v1 browser-profile markers and locks so they move into the
 * project the first time it is opened; the stored project value wins once it exists.
 */
export function normalizeTimeline(raw: unknown, clips: {track?: unknown}[] = [], legacy?: {markers?: unknown; locks?: unknown}): TimelineSettings {
  const base = emptyTimeline();
  const src: any = raw && typeof raw === 'object' ? raw : null;
  const tracks: Partial<Record<TrackId, TrackState>> = {};
  const rawTracks = src?.tracks && typeof src.tracks === 'object' ? src.tracks : {};
  for (const [key, value] of Object.entries(rawTracks)) {
    if (!isTrack(key) || !value || typeof value !== 'object') continue;
    const v = value as any, state: TrackState = {};
    if (v.locked === true) state.locked = true;
    if (isAudioTrack(key) && v.mute === true) state.mute = true;
    if (isAudioTrack(key) && v.solo === true) state.solo = true;
    if (Object.keys(state).length) tracks[key] = state;
  }
  if (!src && legacy?.locks && typeof legacy.locks === 'object') {
    for (const key of ['T1', 'V1', 'A1', 'A2', 'A3'] as const) if ((legacy.locks as any)[key] === true) tracks[key] = {...tracks[key], locked: true};
  }
  const shown = new Set<AudioTrackId>(['A3']);
  for (const t of Array.isArray(src?.audio_tracks) ? src.audio_tracks : []) if (isAudioTrack(t)) shown.add(t);
  for (const c of clips) shown.add(clipTrack(c));
  const markerSource = src ? src.markers : legacy?.markers;
  const markers = (Array.isArray(markerSource) ? markerSource : [])
    .map(cleanMarker).filter((m): m is TimelineMarker => !!m)
    .slice(0, MAX_MARKERS).sort((a, b) => a.time_ms - b.time_ms);
  return {...base, tracks, audio_tracks: AUDIO_TRACKS.filter(t => shown.has(t)), markers};
}

/** The v1 → v0 direction: what an older build would keep (clips on A3, no timeline key). */
export function downgradeTimeline(clips: TimelineAudioClip[]): ProjectAudioClip[] {
  return clips.map(({track: _track, ...rest}) => rest);
}

export function isTrackLocked(t: TimelineSettings, track: TrackId) {
  return !!t.tracks[track]?.locked;
}

/**
 * Whether a timeline audio track is heard in playback/export. Solo applies among
 * timeline audio tracks A3–A8; scene narration, clip sound and the music bed are
 * not affected by these solo buttons.
 */
export function isAudioTrackAudible(t: TimelineSettings, track: AudioTrackId) {
  if (t.tracks[track]?.mute) return false;
  const soloed = AUDIO_TRACKS.filter(id => t.tracks[id]?.solo);
  return !soloed.length || soloed.includes(track);
}

export function nextAudioTrack(t: TimelineSettings): AudioTrackId | null {
  return AUDIO_TRACKS.find(id => !t.audio_tracks.includes(id)) ?? null;
}

/** Where a marker sits now: attached markers follow their clip; others keep their time. */
export function markerTime(m: TimelineMarker, clips: {id: string; start_ms: number}[]) {
  if (!m.clip_id) return m.time_ms;
  const c = clips.find(x => x.id === m.clip_id);
  return c ? c.start_ms + (m.offset_ms || 0) : m.time_ms;
}
