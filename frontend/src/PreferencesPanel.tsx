import {useState,type CSSProperties} from 'react';
import {Monitor,Palette,Ruler,SlidersHorizontal} from 'lucide-react';
import type {Project} from './api';
import type {AppPreferences} from './preferences';

type Props={value:AppPreferences;onChange:(patch:Partial<AppPreferences>)=>void;project?:Project|null;onProjectSetup?:(aspect:string,fps:number)=>void|Promise<void>;disabled?:boolean};
const ASPECTS:AppPreferences['defaultAspect'][]=['16:9','9:16','1:1'];
const RATES:AppPreferences['defaultFps'][]=[24,25,30,50,60];
const ACCENTS:{id:AppPreferences['accent'];name:string;color:string}[]=[
  {id:'violet',name:'Violet',color:'#9783ff'},{id:'blue',name:'Blue',color:'#62a8ff'},{id:'teal',name:'Teal',color:'#43c8b5'},
];

export function PreferencesPanel({value,onChange,project,onProjectSetup,disabled=false}:Props) {
  const [error,setError]=useState('');
  async function updatePage(aspect:string,fps:number) {
    setError('');
    try {await onProjectSetup?.(aspect,fps);} catch(e:any) {setError(e?.message||'Could not update this project.');}
  }
  return <div className="preferences-panel">
    <section className="preference-section">
      <h4><Monitor size={15}/> Appearance</h4>
      <p className="hint">Choose the editor theme, accent and panel spacing. These preferences stay on this computer.</p>
      <div className="preference-row"><span>Theme</span><div className="preference-choice" role="group" aria-label="Theme">
        <button type="button" aria-pressed={value.theme==='graphite'} onClick={()=>onChange({theme:'graphite'})}><i className="theme-swatch graphite"/>Graphite</button>
        <button type="button" aria-pressed={value.theme==='light'} onClick={()=>onChange({theme:'light'})}><i className="theme-swatch light"/>Light</button>
      </div></div>
      <div className="preference-row"><span>Accent color</span><div className="preference-accent" role="group" aria-label="Accent color">
        {ACCENTS.map(a=><button key={a.id} type="button" aria-label={a.name+' accent'} aria-pressed={value.accent===a.id} title={a.name} style={{'--swatch':a.color} as CSSProperties} onClick={()=>onChange({accent:a.id})}><span/></button>)}
      </div></div>
      <div className="preference-row"><span>Panel spacing</span><div className="preference-choice" role="group" aria-label="Panel spacing">
        <button type="button" aria-pressed={value.density==='compact'} onClick={()=>onChange({density:'compact'})}>Compact</button>
        <button type="button" aria-pressed={value.density==='comfortable'} onClick={()=>onChange({density:'comfortable'})}>Comfortable</button>
      </div></div>
      <label className="preference-check"><input type="checkbox" checked={value.reduceMotion} onChange={e=>onChange({reduceMotion:e.target.checked})}/><span><b>Reduce interface motion</b><small>Reduces interface animation. Rendered video motion is unchanged.</small></span></label>
    </section>
    <section className="preference-section">
      <h4><Ruler size={15}/> New project defaults</h4>
      <p className="hint">Existing projects keep their current page setup.</p>
      <div className="preferences-grid">
        <label className="control-label">Default page setup<select aria-label="Default project page setup" value={value.defaultAspect} onChange={e=>onChange({defaultAspect:e.target.value as AppPreferences['defaultAspect']})}>{ASPECTS.map(x=><option key={x}>{x}</option>)}</select></label>
        <label className="control-label">Default frame rate<select aria-label="Default frame rate" value={value.defaultFps} onChange={e=>onChange({defaultFps:Number(e.target.value) as AppPreferences['defaultFps']})}>{RATES.map(x=><option key={x} value={x}>{x} fps</option>)}</select></label>
      </div>
    </section>
    {project&&onProjectSetup&&<section className="preference-section">
      <h4><SlidersHorizontal size={15}/> Current project page setup</h4>
      <p className="hint">Changing page setup may make rendered scenes stale. Render them again before export.</p>
      <div className="preferences-grid">
        <label className="control-label">Aspect ratio<select aria-label="Current project aspect ratio" disabled={disabled} value={project.aspect} onChange={e=>void updatePage(e.target.value,project.fps)}>{ASPECTS.map(x=><option key={x}>{x}</option>)}</select></label>
        <label className="control-label">Frame rate<select aria-label="Current project frame rate" disabled={disabled} value={project.fps} onChange={e=>void updatePage(project.aspect,Number(e.target.value))}>{RATES.map(x=><option key={x} value={x}>{x} fps</option>)}</select></label>
      </div>
      {error&&<p className="preference-error" role="alert">{error}</p>}
    </section>}
  </div>;
}
