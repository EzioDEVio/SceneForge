import {WorkspaceId, isWorkspaceId} from './workspaces';

export type AppPreferences = {
  theme: 'desk'|'graphite'|'light'|'midnight'|'warm';
  accent: 'cyan'|'violet'|'blue'|'teal';
  density: 'compact'|'comfortable';
  reduceMotion: boolean;
  /** Workspace preset (View → Workspace, or the switcher in the top bar). */
  workspace: WorkspaceId;
};

export const DEFAULT_PREFERENCES: AppPreferences = {
  theme:'desk',accent:'cyan',density:'compact',reduceMotion:false,workspace:'edit',
};
const STORAGE_KEY='sceneforge.preferences.v1';
const ACCENT:Record<AppPreferences['accent'],string>={cyan:'#57C7DD',violet:'#9783ff',blue:'#62a8ff',teal:'#43c8b5'};
/** 2 = Director's Desk look. Older saved preferences still on the old defaults move to it once. */
const LOOK_VERSION=2;

export function readPreferences(storage:Pick<Storage,'getItem'>|undefined=typeof localStorage==='undefined'?undefined:localStorage):AppPreferences {
  try {
    const parsed=JSON.parse(storage?.getItem(STORAGE_KEY)||'{}') as Partial<AppPreferences>&{look?:number};
    const upgrading=(parsed.look||1)<LOOK_VERSION;
    const themes:AppPreferences['theme'][]=['desk','graphite','light','midnight','warm'];
    const accents:AppPreferences['accent'][]=['cyan','violet','blue','teal'];
    return {
      theme:upgrading&&(!parsed.theme||parsed.theme==='graphite')?'desk':themes.includes(parsed.theme as AppPreferences['theme'])?parsed.theme as AppPreferences['theme']:'desk',
      accent:upgrading&&(!parsed.accent||parsed.accent==='violet')?'cyan':accents.includes(parsed.accent as AppPreferences['accent'])?parsed.accent as AppPreferences['accent']:'cyan',
      density:parsed.density==='comfortable'?'comfortable':'compact',
      reduceMotion:parsed.reduceMotion===true,
      workspace:isWorkspaceId(parsed.workspace)?parsed.workspace:'edit',
    };
  } catch {return {...DEFAULT_PREFERENCES};}
}

export function writePreferences(value:AppPreferences,storage:Pick<Storage,'setItem'>|undefined=typeof localStorage==='undefined'?undefined:localStorage):void {
  try {storage?.setItem(STORAGE_KEY,JSON.stringify({...value,look:LOOK_VERSION}));} catch {/* Preferences must not block editing when storage is unavailable. */}
}

export function applyPreferences(value:AppPreferences,root:HTMLElement|undefined=typeof document==='undefined'?undefined:document.documentElement):void {
  if(!root)return;
  root.dataset.theme=value.theme;
  root.dataset.density=value.density;
  root.dataset.reduceMotion=String(value.reduceMotion);
  root.dataset.accent=value.accent;
  // Cyan comes from desk.css so each theme can tune it (Daylight needs a deeper teal for readable text).
  if(value.accent==='cyan')root.style.removeProperty('--sf-user-accent');
  else root.style.setProperty('--sf-user-accent',ACCENT[value.accent]);
}
