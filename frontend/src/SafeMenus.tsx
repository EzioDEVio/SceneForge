import {useEffect} from 'react';
export function useSafeMenus(){
 useEffect(()=>{
  const place=()=>document.querySelectorAll<HTMLElement>('.clip-menu').forEach(menu=>{const rect=menu.getBoundingClientRect();menu.style.position='fixed';menu.style.left=Math.max(8,Math.min(rect.left,window.innerWidth-rect.width-8))+'px';menu.style.top=Math.max(8,Math.min(rect.top,window.innerHeight-rect.height-8))+'px';});
  const observer=new window.MutationObserver(place);observer.observe(document.body,{childList:true,subtree:true});window.addEventListener('resize',place);
  const keyboard=(e:KeyboardEvent)=>{const menu=(e.target as HTMLElement).closest?.('.clip-menu')||document.querySelector('.clip-menu');if(!menu)return;const nodes=Array.from(menu.querySelectorAll<HTMLButtonElement>('button:not(:disabled)'));const at=nodes.indexOf(document.activeElement as HTMLButtonElement);let next=-1;if(e.key==='ArrowDown')next=(at+1)%nodes.length;if(e.key==='ArrowUp')next=(at-1+nodes.length)%nodes.length;if(e.key==='Home')next=0;if(e.key==='End')next=nodes.length-1;if(next>=0){e.preventDefault();e.stopImmediatePropagation();nodes[next]?.focus();nodes[next]?.scrollIntoView?.({block:'nearest'});}};
  window.addEventListener('keydown',keyboard,true);return()=>{observer.disconnect();window.removeEventListener('resize',place);window.removeEventListener('keydown',keyboard,true);};
 },[]);
}
