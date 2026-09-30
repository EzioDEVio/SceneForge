export type AppPreferences = {
  theme: 'graphite'|'light';
  accent: 'violet'|'blue'|'teal';
  density: 'compact'|'comfortable';
  reduceMotion: boolean;
  defaultAspect: '16:9'|'9:16'|'1:1';
  defaultFps: 24|25|30|50|60;
};

export const DEFAULT_PREFERENCES: AppPreferences = {
  theme:'graphite',accent:'violet',density:'compact',reduceMotion:false,defaultAspect:'16:9',defaultFps:30,
};
const STORAGE_KEY='sceneforge.preferences.v1';
const ACCENT:Record<AppPreferences['accent'],string>={violet:'#9783ff',blue:'#62a8ff',teal:'#43c8b5'};

export function readPreferences(storage:Pick<Storage,'getItem'>|undefined=typeof localStorage==='undefined'?undefined:localStorage):AppPreferences {
  try {
    const parsed=JSON.parse(storage?.getItem(STORAGE_KEY)||'{}') as Partial<AppPreferences>;
    return {
      theme:parsed.theme==='light'?'light':'graphite',
      accent:parsed.accent==='blue'||parsed.accent==='teal'?parsed.accent:'violet',
      density:parsed.density==='comfortable'?'comfortable':'compact',
      reduceMotion:parsed.reduceMotion===true,
      defaultAspect:parsed.defaultAspect==='9:16'||parsed.defaultAspect==='1:1'?parsed.defaultAspect:'16:9',
      defaultFps:[24,25,30,50,60].includes(Number(parsed.defaultFps))?Number(parsed.defaultFps) as AppPreferences['defaultFps']:30,
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
