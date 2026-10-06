import React,{useLayoutEffect,useState,useRef} from 'react';
export function InspectorSections({tab,sceneTitle,media,active}:{tab:string;sceneTitle:string;media:number;active:boolean}){
 const root=useRef<HTMLElement>(null);
 const [sections,setSections]=useState<{id:string;title:string}[]>([]),[selected,setSelected]=useState('');
 useLayoutEffect(()=>{
   const body=root.current?.parentElement?.querySelector('.inspector-body');
   if(!body)return;
   const refresh=()=>{const nodes=Array.from(body.querySelectorAll<HTMLElement>('h3,h4,legend')).filter(el=>el.textContent?.trim()&&el.getBoundingClientRect().height>0);
     const next=nodes.map((node,i)=>{node.dataset.inspectorSection=`section-${tab}-${i}`;node.tabIndex=-1;node.setAttribute('aria-label',node.textContent!.trim());node.dataset.scope=tab==='Audio'&&/music|timeline|finishing/i.test(node.textContent||'')?'Entire project':tab==='Motion'||tab==='Media'||tab==='Clip Audio'?`Selected media ${media}`:'Selected scene';return {id:node.dataset.inspectorSection,title:node.textContent!.trim()};});
     setSections(old=>JSON.stringify(old)===JSON.stringify(next)?old:next);
   };refresh();const observer=new window.MutationObserver(refresh);observer.observe(body,{childList:true,subtree:true});return()=>observer.disconnect();
 },[tab,media,active]);
 function go(){const body=root.current?.parentElement?.querySelector('.inspector-body') as HTMLElement;const target=Array.from(body?.querySelectorAll<HTMLElement>('[data-inspector-section]')||[]).find(n=>n.dataset.inspectorSection===(sections.find(s=>s.id===selected)?.id||sections[0]?.id));if(body&&target){body.scrollTo({top:body.scrollTop+target.getBoundingClientRect().top-body.getBoundingClientRect().top-8,behavior:'smooth'});target.focus({preventScroll:true});}}
 return <nav ref={root} className="inspector-sections" aria-label="Inspector sections"><p>{tab==='Audio'?'Narration: selected scene · music/audio tracks: entire project':tab==='Motion'||tab==='Media'||tab==='Clip Audio'?`Selected media ${media} · ${sceneTitle}`:`Selected scene · ${sceneTitle}`}</p><label>Jump to section<select aria-label="Jump to section" value={sections.some(s=>s.id===selected)?selected:sections[0]?.id||''} onChange={e=>setSelected(e.target.value)}>{sections.map(s=><option value={s.id} key={s.id}>{s.title}</option>)}</select></label><button className="btn" disabled={!sections.length} onClick={go}>Go</button></nav>;
}
