import React, {useMemo, useState} from 'react';
import {ChevronLeft,ChevronRight,Scissors,Search,Trash2,Type} from 'lucide-react';
import type {CaptionSegment} from './api';
import {FeatureHelp} from './FeatureHelp';

function uid(){return globalThis.crypto?.randomUUID?.()||`cap-${Date.now()}-${Math.random().toString(16).slice(2)}`;}

export type CaptionDirection = 'auto'|'ltr'|'rtl';

export function CaptionSegmentsEditor({segments,onChange,direction='auto',onDirectionChange,activeSegmentId,onFocusSegment}:{
  segments:CaptionSegment[];
  onChange:(segments:CaptionSegment[])=>void;
  direction?:CaptionDirection;
  onDirectionChange?:(direction:CaptionDirection)=>void;
  activeSegmentId?:string|null;
  onFocusSegment?:(id:string)=>void;
}){
  const [query,setQuery]=useState('');
  const [collapsed,setCollapsed]=useState(false);
  const filtered=useMemo(()=>{
    const q=query.trim().toLocaleLowerCase();
    return segments.map((segment,index)=>({segment,index})).filter(({segment,index})=>!q||segment.text.toLocaleLowerCase().includes(q)||`caption ${index+1}`.includes(q));
  },[segments,query]);
  const activeIndex=filtered.findIndex(({segment})=>segment.id===activeSegmentId);
  const navigate=(step:-1|1)=>{
    if(!filtered.length)return;
    const base=activeIndex<0?(step>0?-1:filtered.length):activeIndex;
    const next=filtered[(base+step+filtered.length)%filtered.length].segment;
    setCollapsed(false);
    onFocusSegment?.(next.id);
  };
  const patch=(id:string,values:Partial<CaptionSegment>)=>onChange(segments.map(s=>s.id===id?{...s,...values}:s));
  const split=(segment:CaptionSegment)=>{
    const words=segment.text.trim().split(/\s+/);if(words.length<2)return;
    const at=Math.ceil(words.length/2),mid=Math.round((segment.start_ms+segment.end_ms)/2);
    const left={...segment,text:words.slice(0,at).join(' '),end_ms:Math.max(segment.start_ms+50,mid)};
    const right={id:uid(),text:words.slice(at).join(' '),start_ms:left.end_ms,end_ms:segment.end_ms};
    onChange(segments.flatMap(s=>s.id===segment.id?[left,right]:[s]));
  };
  return <section className="caption-segment-editor" aria-label="Editable caption segments">
    <header className="section-heading"><div><h3>Caption clips · {segments.length}</h3><p className="hint">Each box is a separately timed caption clip. Edit its words and timing, then style all clips above.</p></div>
      <FeatureHelp compact title="Editable caption clips" description="Auto captions are split into timed text clips. Each clip keeps its own wording and timing while sharing the caption style for this scene." steps="Edit a clip's text directly. Adjust its start or end time, split a multiword clip into two, or remove a clip. Choose caption styles above to restyle every clip."/>
    </header>
    <div className="caption-navigation">
      <label className="caption-search"><Search size={13}/><input aria-label="Search captions" type="search" placeholder="Find caption text…" value={query} onChange={e=>setQuery(e.target.value)}/></label>
      <div className="caption-stepper"><button type="button" aria-label="Previous caption" title="Focus previous caption" disabled={!filtered.length} onClick={()=>navigate(-1)}><ChevronLeft size={14}/></button><span aria-live="polite">{activeIndex>=0?activeIndex+1:'—'} / {filtered.length}</span><button type="button" aria-label="Next caption" title="Focus next caption" disabled={!filtered.length} onClick={()=>navigate(1)}><ChevronRight size={14}/></button></div>
      <label className="caption-direction-control">Direction<select aria-label="Caption text direction" value={direction} onChange={e=>onDirectionChange?.(e.target.value as CaptionDirection)}><option value="auto">Auto</option><option value="rtl">Right to left</option><option value="ltr">Left to right</option></select></label>
      <button type="button" className="text-btn caption-collapse-all" aria-label={collapsed?'Expand all captions':'Collapse all captions'} onClick={()=>setCollapsed(v=>!v)}>{collapsed?'Expand all':'Collapse all'}</button>
    </div>
    <div className="caption-segment-list" aria-label="Caption clip list">{filtered.map(({segment:s,index:i})=><article className={`caption-segment-card ${s.id===activeSegmentId?'active':''}`} key={s.id} data-caption-segment-id={s.id} aria-current={s.id===activeSegmentId?'true':undefined}>
      <div className="caption-segment-heading"><strong><Type size={13}/> Caption {i+1}</strong><div>
        {s.text.trim().split(/\s+/).length>1&&<button type="button" className="text-btn" aria-label={`Split caption ${i+1}`} title="Split this caption into two timed clips" onClick={()=>split(s)}><Scissors size={13}/> Split</button>}
        <button type="button" className="text-btn danger" aria-label={`Remove caption ${i+1}`} title="Remove this caption clip" onClick={()=>onChange(segments.filter(x=>x.id!==s.id))}><Trash2 size={13}/></button>
      </div></div>
      {collapsed?<button type="button" className="caption-collapsed-text" dir={direction} onClick={()=>{setCollapsed(false);onFocusSegment?.(s.id);}}>{s.text||'Empty caption'}</button>:<textarea aria-label={`Caption segment ${i+1} text`} dir={direction} value={s.text} onFocus={()=>onFocusSegment?.(s.id)} onChange={e=>patch(s.id,{text:e.target.value})}/>}
      {!collapsed&&<div className="caption-segment-times"><label>Start <span><input aria-label={`Caption ${i+1} start time`} type="number" min={0} max={3600000} step={50} value={s.start_ms} onChange={e=>patch(s.id,{start_ms:Math.max(0,Math.min(s.end_ms-50,Number(e.target.value)||0))})}/> ms</span></label>
        <label>End <span><input aria-label={`Caption ${i+1} end time`} type="number" min={s.start_ms+50} max={3600000} step={50} value={s.end_ms} onChange={e=>patch(s.id,{end_ms:Math.max(s.start_ms+50,Math.min(3600000,Number(e.target.value)||s.start_ms+50))})}/> ms</span></label></div>}
    </article>)}</div>
    {filtered.length===0&&<p className="caption-empty-search">No captions match “{query}”.</p>}
  </section>;
}
