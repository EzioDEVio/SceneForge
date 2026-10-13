// Workspace presets: named arrangements of the existing panels. They only drive the
// layout state that already exists (inspector width via InspectorResizer, the timeline
// height inside ProjectTimeline, the active inspector tab in each scene editor and the
// inspector's hidden class); the choice itself is stored with the other preferences.
export type WorkspaceId = 'edit' | 'color' | 'audio' | 'review';
export type InspectorTabName = 'Media' | 'Motion' | 'Effects' | 'Overlays' | 'Text' | 'Audio' | 'Clip Audio';

export type WorkspacePreset = {
  id: WorkspaceId; label: string; description: string;
  /** Inspector tab to open, or null to leave the current tab. */
  tab: InspectorTabName | null;
  /** Inspector width in px, or null for the user's own (remembered) width. */
  inspectorWidth: number | null;
  inspectorHidden: boolean;
  /** Timeline height as a share of the window height (clamped by the timeline). */
  timelineShare: number | null;
};

export const WORKSPACES: WorkspacePreset[] = [
  {id: 'edit', label: 'Edit', description: 'The standard layout: scenes, preview, scene settings and timeline.', tab: null, inspectorWidth: null, inspectorHidden: false, timelineShare: null},
  {id: 'color', label: 'Color', description: 'Wider scene settings on the Effects tab, shorter timeline.', tab: 'Effects', inspectorWidth: 440, inspectorHidden: false, timelineShare: 0.27},
  {id: 'audio', label: 'Audio', description: 'Taller timeline and the Audio tab; the preview gets smaller.', tab: 'Audio', inspectorWidth: null, inspectorHidden: false, timelineShare: 0.55},
  {id: 'review', label: 'Review', description: 'Large preview with scene settings hidden.', tab: null, inspectorWidth: null, inspectorHidden: true, timelineShare: 0.27},
];

export const WORKSPACE_EVENT = 'sceneforge-workspace';
export const workspacePreset = (id: string | undefined): WorkspacePreset => WORKSPACES.find(w => w.id === id) || WORKSPACES[0];
export const isWorkspaceId = (v: unknown): v is WorkspaceId => WORKSPACES.some(w => w.id === v);

/** Default timeline height (the Edit layout). */
export const defaultTimelineHeight = () => {const h = typeof window === 'undefined' ? 900 : window.innerHeight; return Math.round(Math.min(310, Math.max(h < 700 ? 160 : 180, h * (h < 700 ? .26 : .3))));};
export const timelineHeightFor = (preset: WorkspacePreset) =>
  preset.timelineShare === null ? defaultTimelineHeight() : Math.max(timelineBounds().min, Math.round((typeof window === 'undefined' ? 900 : window.innerHeight) * preset.timelineShare));

/** Timeline height limits for the current window. The editor above it (preview, narration,
 *  Scene settings) always keeps at least ~360 px, so "Maximize timeline" and small windows
 *  never squeeze the preview into a sliver (owner report 2026-10-12, laptop at 1366×768). */
export const timelineBounds = () => {
  const h = typeof window === 'undefined' ? 900 : window.innerHeight;
  const min = h < 700 ? 160 : h < 800 ? 180 : 250;
  // Preview + narration + scene/preview bars need ~420 px to stay useful (layout audit).
  const reserve = Math.min(440, Math.round(h * .56));
  return {min, max: Math.max(min, Math.round(Math.min(h * .7, h - 83 - reserve)))};
};
export const clampTimeline = (value: number) => {const {min, max} = timelineBounds(); return Math.max(min, Math.min(max, value));};
