// Drag-and-drop onto the timeline: files from Explorer/Finder (including whole
// folders) and items dragged out of the Media Pool.
export const ASSET_DRAG_TYPE = 'application/x-sceneforge-assets';
export type DraggedAsset = {id: string; type: string; original_filename: string; duration_ms?: number | null};
export type MediaKind = 'image' | 'video' | 'audio';

// Mirrors backend ALLOWED_*_EXT (app/config.py).
const EXT: Record<MediaKind, string[]> = {
  image: ['.png', '.jpg', '.jpeg', '.webp', '.bmp'],
  video: ['.mp4', '.mov', '.mkv', '.webm', '.avi'],
  audio: ['.wav', '.mp3', '.m4a', '.aac', '.ogg', '.flac'],
};

export function mediaKind(name: string): MediaKind | null {
  const dot = name.lastIndexOf('.');
  const ext = dot >= 0 ? name.slice(dot).toLowerCase() : '';
  return (Object.keys(EXT) as MediaKind[]).find(k => EXT[k].includes(ext)) || null;
}

export type DropPlan = {
  audio: File | null;          // attached to the target scene's narration lane
  extraAudio: string[];        // more audio than one scene can take
  visuals: File[];             // images/videos, in name order
  rejected: string[];          // unsupported files
};

/** Sort dropped files by kind. Files are ordered by name so a folder of
 *  "01.jpg, 02.jpg…" lands on the timeline in that order. */
export function planFileDrop(files: File[], toScene: boolean): DropPlan {
  const sorted = [...files].sort((a, b) => a.name.localeCompare(b.name, undefined, {numeric: true}));
  const plan: DropPlan = {audio: null, extraAudio: [], visuals: [], rejected: []};
  for (const f of sorted) {
    const kind = mediaKind(f.name);
    if (!kind) plan.rejected.push(f.name);
    else if (kind === 'audio') {
      if (toScene && !plan.audio) plan.audio = f;
      else plan.extraAudio.push(f.name);
    } else plan.visuals.push(f);
  }
  return plan;
}

export function isMediaDrag(e: {dataTransfer: DataTransfer | null}): 'files' | 'assets' | null {
  const types = Array.from(e.dataTransfer?.types || []);
  if (types.includes(ASSET_DRAG_TYPE)) return 'assets';
  if (types.includes('Files')) return 'files';
  return null;
}

/** Read every file from a drop, walking into dropped folders. */
export async function collectDroppedFiles(dt: DataTransfer): Promise<File[]> {
  const items = Array.from(dt.items || []);
  const entries = items.map(i => (i as any).webkitGetAsEntry?.()).filter(Boolean);
  if (!entries.length) return Array.from(dt.files || []);
  const out: File[] = [];
  async function walk(entry: any, depth: number): Promise<void> {
    if (entry.isFile) {out.push(await new Promise<File>((res, rej) => entry.file(res, rej))); return;}
    if (!entry.isDirectory || depth > 4) return;
    const reader = entry.createReader();
    for (;;) {
      const batch: any[] = await new Promise((res, rej) => reader.readEntries(res, rej));
      if (!batch.length) break;
      for (const child of batch) await walk(child, depth + 1);
    }
  }
  for (const entry of entries) await walk(entry, 0);
  return out;
}
