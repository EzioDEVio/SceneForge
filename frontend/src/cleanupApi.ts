// Clean up endpoints (backend/app/api/cleanup.py).
import {req, type Scene} from './api';

export type CleanupSource = 'narration' | 'clips';
export type SilenceParams = {threshold_db: number; min_silence_ms: number; padding_ms: number};
export const SILENCE_DEFAULTS: SilenceParams = {threshold_db: -38, min_silence_ms: 600, padding_ms: 120};
export type SilenceResult = SilenceParams & {
  asset_id: string; duration_ms: number; ranges: [number, number][]; total_removable_ms: number; cuts: number;
  scene_ranges?: [number, number][]; scene_offset_ms?: number;
};
export type FillerMatch = {
  index: number; text: string; prev: string; next: string; word_start_ms: number; word_end_ms: number;
  /** cut range in scene time (40 ms padding, never into neighbouring words) */
  start_ms: number; end_ms: number;
  /** the same range in the audio a detached timeline clip would play */
  source_start_ms: number; source_end_ms: number;
};
export type FillerResult = {scene_id: string; source: CleanupSource; terms: string[]; scene_offset_ms: number; matches: FillerMatch[]; total_removable_ms: number; language?: string};
export const DEFAULT_FILLERS = ['um', 'uh', 'erm', 'er', 'ah', 'hmm', 'mm', 'uhm', 'you know', 'i mean', 'يعني', 'اه', 'امم'];
export const OPTIONAL_FILLERS = ['like', 'so'];

const post = <T,>(path: string, body: unknown) => req<T>(path, {method: 'POST', body: JSON.stringify(body)});

export const cleanupApi = {
  detectSilence: (target: {asset_id: string} | {scene_id: string; source: CleanupSource}, params: SilenceParams) =>
    post<SilenceResult>('/api/silence/detect', {...target, ...params}),
  detectFillers: (scene_id: string, source: CleanupSource, words?: string[]) =>
    post<FillerResult>('/api/fillers/detect', {scene_id, source, ...(words ? {words} : {})}),
  jumpCutScene: (sceneId: string, cuts: [number, number][]) =>
    post<{scenes: Scene[]; kept_ms: number; removed_ms: number; segments: number}>(`/api/cleanup/scenes/${sceneId}/jump-cut`, {cuts}),
};

// The panel opens from the timeline context menus through a window event.
export const CLEANUP_EVENT = 'sceneforge-cleanup';
/** Move the timeline playhead (and the preview) to an absolute timeline time. */
export const TIMELINE_SEEK_EVENT = 'sceneforge-timeline-seek';
export type CleanupMode = 'silence' | 'fillers';
export type CleanupTarget = {kind: 'clips'; ids: string[]} | {kind: 'scene'; sceneId: string; source: CleanupSource};
export const openCleanup = (mode: CleanupMode, target: CleanupTarget) => window.dispatchEvent(new CustomEvent(CLEANUP_EVENT, {detail: {mode, target}}));
