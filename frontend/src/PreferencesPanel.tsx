import {type CSSProperties} from 'react';
import {Monitor,Palette} from 'lucide-react';
import type {AppPreferences} from './preferences';

type Props={value:AppPreferences;onChange:(patch:Partial<AppPreferences>)=>void};
const ACCENTS:{id:AppPreferences['accent'];name:string;color:string}[]=[
  {id:'violet',name:'Violet',color:'#9783ff'},{id:'blue',name:'Blue',color:'#62a8ff'},{id:'teal',name:'Teal',color:'#43c8b5'},
];

export function PreferencesPanel({value,onChange}:Props) {
  return <div className="preferences-panel">
    <section className="preference-section">
      <h4><Monitor size={15}/> Appearance</h4>
      <p className="hint">Themes are available from the theme control at the top right of the editor. These preferences stay on this computer.</p>
      <div className="preference-row"><span>Accent color</span><div className="preference-accent" role="group" aria-label="Accent color">
        {ACCENTS.map(a=><button key={a.id} type="button" aria-label={a.name+' accent'} aria-pressed={value.accent===a.id} title={a.name} style={{'--swatch':a.color} as CSSProperties} onClick={()=>onChange({accent:a.id})}><span/></button>)}
      </div></div>
      <div className="preference-row"><span>Panel spacing</span><div className="preference-choice" role="group" aria-label="Panel spacing">
        <button type="button" aria-pressed={value.density==='compact'} onClick={()=>onChange({density:'compact'})}>Compact</button>
        <button type="button" aria-pressed={value.density==='comfortable'} onClick={()=>onChange({density:'comfortable'})}>Comfortable</button>
      </div></div>
      <label className="preference-check"><input type="checkbox" checked={value.reduceMotion} onChange={e=>onChange({reduceMotion:e.target.checked})}/><span><b>Reduce interface motion</b><small>Reduces interface animation. Rendered video motion is unchanged.</small></span></label>
    </section>
  </div>;
}
