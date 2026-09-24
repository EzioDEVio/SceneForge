import type {Asset, Scene} from './api';

// A scene the user has not touched yet: the Part-N rows a new project starts
// with. It has no media, text, narration, or title layers, and its default name.
export function isUntouchedPlaceholder(s: Scene): boolean {
  return !s.shots.length
    && !(s.original_text || '').trim()
    && !(s.spoken_text || '').trim()
    && !(s.subtitle_text || '').trim()
    && !s.voice_takes.length
    && !(s.font_json?.layers?.length)
    && /^Part-\d+$/.test(s.title || '');
}

export type PoolStep = {asset: Asset; sceneId: string | null};

/** Decide where each pool item goes when the user chooses "Add to timeline".
 *  Untouched placeholders at the END of the project are filled first, in
 *  order; remaining items create new scenes (sceneId null). Placeholders that
 *  sit between real scenes are left alone so nothing lands mid-edit. Audio is
 *  skipped: it belongs to a scene's narration lane, not the picture track. */
export function planPoolInsert(scenes: Scene[], assets: Asset[]): PoolStep[] {
  let firstTrailing = scenes.length;
  while (firstTrailing > 0 && isUntouchedPlaceholder(scenes[firstTrailing - 1])) firstTrailing--;
  const free = scenes.slice(firstTrailing).map(s => s.id);
  return assets.filter(a => a.type !== 'audio').map(asset => ({asset, sceneId: free.shift() ?? null}));
}
