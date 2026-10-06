import React, {useState} from 'react';
import {api} from './api';
import {STICKER_LIBRARY, stickerMatches} from './StickerLibrary';

export const CAPTION_EMOJI = STICKER_LIBRARY.filter(item=>item.source==='twemoji');
const categories = [...new Set(CAPTION_EMOJI.map(item=>item.category))];

export function CaptionEmojiPicker({index,value,side,onChange,onSide}:{index:number;value:string;side:'left'|'right';onChange:(id:string)=>void;onSide:(side:'left'|'right')=>void}) {
 const [open,setOpen]=useState(false),[query,setQuery]=useState(''),[category,setCategory]=useState('All');
 const shown=CAPTION_EMOJI.filter(item=>(category==='All'||item.category===category)&&stickerMatches(item,query));
 return <div className="caption-emoji-controls">
  <label>Emoji<select aria-label={`Caption ${index} emoji`} value={value} onChange={e=>onChange(e.target.value)}><option value="">None</option>{CAPTION_EMOJI.map(item=><option key={item.id} value={item.id}>{item.emoji} {item.name}</option>)}</select></label>
  {value&&<label>Side<select aria-label={`Caption ${index} emoji side`} value={side} onChange={e=>onSide(e.target.value as 'left'|'right')}><option value="right">Right</option><option value="left">Left</option></select></label>}
  <button type="button" className="btn" aria-expanded={open} aria-controls={`caption-emoji-${index}`} onClick={()=>setOpen(!open)}>{open?'Close emoji browser':`Browse ${CAPTION_EMOJI.length} emoji`}</button>
  {open&&<section id={`caption-emoji-${index}`} className="caption-emoji-browser" aria-label={`Caption ${index} emoji browser`}>
   <div className="emoji-browser-filters"><label>Find emoji<input autoFocus type="search" aria-label={`Search caption ${index} emoji`} placeholder="Smile, plane, heart…" value={query} onChange={e=>setQuery(e.target.value)}/></label><label>Category<select aria-label={`Caption ${index} emoji category`} value={category} onChange={e=>setCategory(e.target.value)}><option>All</option>{categories.map(c=><option key={c}>{c}</option>)}</select></label></div>
   <p className="hint" role="status">{shown.length} emoji · choose one for this caption</p>
   <div className="caption-emoji-grid" role="group" aria-label={`Caption ${index} emoji choices`}>{shown.map(item=><button type="button" key={item.id} aria-label={`Use ${item.name} emoji`} title={item.name} aria-pressed={value===item.id} onClick={()=>onChange(item.id)}><img src={api.stickerImageUrl(item.id)} alt="" loading="lazy"/><span>{item.name}</span></button>)}</div>
   {!shown.length&&<p className="hint">No matches. Clear the search or choose All categories.</p>}
   {value&&<button type="button" className="text-btn" onClick={()=>onChange('')}>Remove caption emoji</button>}
  </section>}
  <small>Colour artwork follows this caption’s timing. Up to 64 caption clips can carry emoji. Emoji: Twemoji, CC-BY 4.0.</small>
 </div>;
}
