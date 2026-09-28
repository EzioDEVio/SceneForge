import React,{useLayoutEffect,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import {Info,X} from 'lucide-react';

/** Small, click-to-open guide used beside editor tools and controls. */
export function FeatureHelp({title,description,steps,compact=false}:{title:string;description:string;steps:string;compact?:boolean}) {
  const [open,setOpen]=useState(false);
  const [position,setPosition]=useState<{left:number;top:number}>({left:12,top:12});
  const trigger=useRef<HTMLButtonElement>(null);
  useLayoutEffect(()=>{
    if(!open)return;
    const place=()=>{const r=trigger.current?.getBoundingClientRect();if(!r)return;const width=Math.min(320,window.innerWidth-24);const rightSpace=window.innerWidth-r.right;const left=rightSpace>=width+12?r.right+10:r.left-width-10;setPosition({left:Math.max(12,Math.min(window.innerWidth-width-12,left)),top:Math.max(12,Math.min(window.innerHeight-210,r.top-18))});};
    place();window.addEventListener('resize',place);window.addEventListener('scroll',place,true);return()=>{window.removeEventListener('resize',place);window.removeEventListener('scroll',place,true);};
  },[open]);
  React.useEffect(()=>{if(!open)return;const key=(e:KeyboardEvent)=>{if(e.key==='Escape')setOpen(false);};window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key);},[open]);
  return <span className={`feature-help ${compact?'compact':''}`}>
    <button ref={trigger} type="button" className="feature-help-trigger" aria-label={`How to use ${title}`} aria-expanded={open} title={`What is ${title}?`} onClick={e=>{e.stopPropagation();setOpen(v=>!v);}}><Info size={14}/></button>
    {open&&createPortal(<div className="feature-help-popover" style={{...position,position:'fixed'}} role="dialog" aria-label={`${title} help`}>
      <span className="feature-help-top"><strong>{title}</strong><button type="button" aria-label={`Close ${title} help`} onClick={()=>setOpen(false)}><X size={12}/></button></span>
      <span><b>What it does</b><br/>{description}</span><span><b>How to use it</b><br/>{steps}</span>
    </div>,document.body)}
  </span>;
}
