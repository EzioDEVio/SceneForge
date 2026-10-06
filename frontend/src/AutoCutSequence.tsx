import React,{useState} from 'react';
import {api} from './api';
export function AutoCutSequence({plan}:{plan:any}){
 const [time,setTime]=useState(0);
 if(!plan?.shots?.length)return null;
 let cursor=0;const clips=plan.shots.map((s:any)=>{const start=cursor;cursor+=s.duration_ms;return {...s,start,end:cursor};});
 const active=clips.find((s:any)=>time>=s.start&&time<s.end)||clips.at(-1);
 return <section className="autocut-sequence" aria-label="AutoCut storyboard"><h3>Picture sequence preview</h3><p className="hint">Static source thumbnails at the listed times. Render after Apply to check movement and sound.</p><img className="autocut-current" src={api.assetThumbUrl(active.asset_id,480,(active.source_in_ms||0)+Math.max(0,time-active.start)*(active.speed_json?.speed||1))} alt="Picture at preview time"/><label>Preview time · {(time/1000).toFixed(2)} s<input aria-label="AutoCut preview time" type="range" min={0} max={plan.duration_ms} step={1} value={time} onChange={e=>setTime(+e.target.value)}/></label><div className="autocut-thumbnails">{clips.map((s:any,i:number)=><button key={i} aria-label={`Preview AutoCut picture ${i+1}`} aria-pressed={s===active} onClick={()=>setTime(s.start)}><img src={api.assetThumbUrl(s.asset_id,160,s.source_in_ms||0)} alt={`Picture ${i+1}`}/><span>{(s.start/1000).toFixed(2)}–{(s.end/1000).toFixed(2)} s</span>{s.source_in_ms>0&&<small>Video starts at {(s.source_in_ms/1000).toFixed(2)} s</small>}</button>)}</div></section>;
}
