import React,{useLayoutEffect,useState,useRef,useEffect} from 'react';
import {
  Image as ImageIcon, Clock, Crop, Move, Gauge, Palette, Film, SlidersHorizontal, Droplet, Sparkles, Box, Wand2, Layers,
  Smile, Type, Captions, Square, Crosshair, Monitor, Highlighter, Keyboard, Mic, Music, VolumeX, User, Volume2, Server,
  LayoutTemplate, Sun, AudioLines, ListTree, type LucideIcon,
} from 'lucide-react';

// One icon per inspector section, matched on the section's own heading so new
// sections still get a sensible symbol without a lookup table to maintain.
const ICONS:[RegExp,LucideIcon][]=[
  [/duration|timing/i,Clock],[/crop|focal|framing/i,Crop],[/camera|movement|motion/i,Move],[/speed|slow|ramp|freeze/i,Gauge],
  [/old film|film/i,Film],[/lut/i,Box],[/adjust/i,SlidersHorizontal],[/^light/i,Sun],[/colou?r|outline/i,Droplet],[/detail/i,Sparkles],
  [/more effects|creative/i,Wand2],[/look|filter|grade|effect/i,Palette],[/picture in picture|overlay|layer/i,Layers],[/sticker|emoji/i,Smile],
  [/template|title|label/i,LayoutTemplate],[/caption/i,Captions],[/font|text/i,Type],[/background|box/i,Square],[/position/i,Crosshair],
  [/display/i,Monitor],[/highlight/i,Highlighter],[/animation/i,Sparkles],[/typewriter/i,Keyboard],[/censor/i,VolumeX],[/isolat/i,User],
  [/clip sound/i,Volume2],[/engine/i,Server],[/music|finishing/i,Music],[/loud|sound|track|audio/i,AudioLines],[/voice|narration/i,Mic],
  [/media/i,ImageIcon],
];
export const sectionIcon=(title:string):LucideIcon=>ICONS.find(([re])=>re.test(title))?.[1]||ListTree;

export function InspectorSections({tab,sceneTitle,media,active}:{tab:string;sceneTitle:string;media:number;active:boolean}){
 const root=useRef<HTMLElement>(null);
 const [sections,setSections]=useState<{id:string;title:string}[]>([]),[current,setCurrent]=useState('');
 const body=()=>root.current?.parentElement?.querySelector('.inspector-body') as HTMLElement|null;
 useLayoutEffect(()=>{
   const el=body();
   if(!el)return;
   const refresh=()=>{const nodes=Array.from(el.querySelectorAll<HTMLElement>('h3,h4,legend')).filter(n=>n.textContent?.trim()&&n.getBoundingClientRect().height>0);
     const next=nodes.map((node,i)=>{node.dataset.inspectorSection=`section-${tab}-${i}`;node.tabIndex=-1;node.setAttribute('aria-label',node.textContent!.trim());node.dataset.scope=tab==='Audio'&&/music|timeline|finishing/i.test(node.textContent||'')?'Entire project':tab==='Motion'||tab==='Media'||tab==='Clip Audio'?`Selected media ${media}`:'Selected scene';return {id:node.dataset.inspectorSection,title:node.textContent!.trim()};});
     setSections(old=>JSON.stringify(old)===JSON.stringify(next)?old:next);
   };refresh();const observer=new window.MutationObserver(refresh);observer.observe(el,{childList:true,subtree:true});return()=>observer.disconnect();
 },[tab,media,active]);
 // Highlight the section currently at the top of the scrolled panel.
 useEffect(()=>{const el=body();if(!el)return;
   const spy=()=>{const top=el.getBoundingClientRect().top+24;let id=sections[0]?.id||'';for(const s of sections){const n=el.querySelector<HTMLElement>(`[data-inspector-section="${s.id}"]`);if(n&&n.getBoundingClientRect().top<=top)id=s.id;}setCurrent(id);};
   spy();el.addEventListener('scroll',spy,{passive:true});return()=>el.removeEventListener('scroll',spy);},[sections]);
 // Keep the highlighted shortcut visible in the row.
 // Scroll only the shortcut row itself (scrollIntoView would also shift the inspector).
 useEffect(()=>{const row=root.current?.querySelector<HTMLElement>('.section-chips');const chip=row?.querySelector<HTMLElement>(`[data-section-id="${current}"]`);if(!row||!chip)return;
   const left=chip.offsetLeft-row.offsetLeft,right=left+chip.offsetWidth;if(left<row.scrollLeft)row.scrollLeft=left-4;else if(right>row.scrollLeft+row.clientWidth)row.scrollLeft=right-row.clientWidth+4;},[current]);
 function go(id:string){const el=body();const target=el?.querySelector<HTMLElement>(`[data-inspector-section="${id}"]`);if(el&&target){el.scrollTo({top:el.scrollTop+target.getBoundingClientRect().top-el.getBoundingClientRect().top-8,behavior:'smooth'});target.focus({preventScroll:true});setCurrent(id);}}
 function onKey(e:React.KeyboardEvent,i:number){const d={ArrowRight:1,ArrowLeft:-1}[e.key as 'ArrowRight'|'ArrowLeft'];if(!d)return;e.preventDefault();const next=sections[(i+d+sections.length)%sections.length];root.current?.querySelector<HTMLElement>(`[data-section-id="${next.id}"]`)?.focus();}
 return <nav ref={root} className="inspector-sections" aria-label="Inspector sections">
   <p>{tab==='Audio'?'Narration: selected scene · music/audio tracks: entire project':tab==='Motion'||tab==='Media'||tab==='Clip Audio'?`Selected media ${media} · ${sceneTitle}`:`Selected scene · ${sceneTitle}`}</p>
   <div className="section-chips" role="list" aria-label="Jump to section">{sections.map((s,i)=>{const Icon=sectionIcon(s.title);return <span role="listitem" key={s.id}><button type="button" className="section-chip" data-section-id={s.id} aria-current={current===s.id?'true':undefined} title={`Jump to ${s.title}`} onClick={()=>go(s.id)} onKeyDown={e=>onKey(e,i)}><Icon size={13} aria-hidden/>{s.title}</button></span>;})}</div>
 </nav>;
}
