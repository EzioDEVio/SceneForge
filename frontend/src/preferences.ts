import {WorkspaceId, isWorkspaceId} from './workspaces';

export type AppPreferences = {
  theme: 'graphite'|'light'|'midnight'|'warm';
  accent: 'violet'|'blue'|'teal';
  density: 'compact'|'comfortable';
  reduceMotion: boolean;
  /** Workspace preset (View → Workspace, or the switcher in the top bar). */
  workspace: WorkspaceId;
};

export const DEFAULT_PREFERENCES: AppPreferences = {
  theme:'graphite',accent:'violet',density:'compact',reduceMotion:false,workspace:'edit',
};
const STORAGE_KEY='sceneforge.preferences.v1';
const ACCENT:Record<AppPreferences['accent'],string>={violet:'#9783ff',blue:'#62a8ff',teal:'#43c8b5'};

export function readPreferences(storage:Pick<Storage,'getItem'>|undefined=typeof localStorage==='undefined'?undefined:localStorage):AppPreferences {
  try {
    const parsed=JSON.parse(storage?.getItem(STORAGE_KEY)||'{}') as Partial<AppPreferences>;
    return {
      theme:parsed.theme==='light'||parsed.theme==='midnight'||parsed.theme==='warm'?parsed.theme:'graphite',
      accent:parsed.accent==='blue'||parsed.accent==='teal'?parsed.accent:'violet',
      density:parsed.density==='comfortable'?'comfortable':'compact',
      reduceMotion:parsed.reduceMotion===true,
      workspace:isWorkspaceId(parsed.workspace)?parsed.workspace:'edit',
    };
  } catch {return {...DEFAULT_PREFERENCES};}
}

export function writePreferences(value:AppPreferences,storage:Pick<Storage,'setItem'>|undefined=typeof localStorage==='undefined'?undefined:localStorage):void {
  try {storage?.setItem(STORAGE_KEY,JSON.stringify(value));} catch {/* Preferences must not block editing when storage is unavailable. */}
}

export function applyPreferences(value:AppPreferences,root:HTMLElement|undefined=typeof document==='undefined'?undefined:document.documentElement):void {
  if(!root)return;
  root.dataset.theme=value.theme;
  root.dataset.density=value.density;
  root.dataset.reduceMotion=String(value.reduceMotion);
  root.style.setProperty('--sf-user-accent',ACCENT[value.accent]);
}
