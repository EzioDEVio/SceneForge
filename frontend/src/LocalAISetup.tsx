import React,{useEffect,useState} from 'react';
import {Captions, CheckCircle2, Cpu, Download, Loader2, Mic, Play, Sparkles} from 'lucide-react';

type Component='whisper'|'kokoro'|'stable_diffusion'|'chatterbox';
const ENGINES:{id:Component;name:string;does:string;size:string;Icon:typeof Cpu}[]=[
 {id:'whisper',name:'Whisper',does:'Automatic captions from speech and songs',size:'about 145 MB',Icon:Captions},
 {id:'kokoro',name:'Kokoro',does:'Narration voices built into SceneForge: English, Spanish, French, Hindi, Italian, Portuguese',size:'about 120 MB',Icon:Sparkles},
 {id:'stable_diffusion',name:'Stable Diffusion',does:'Pictures from a text description',size:'about 6 GB',Icon:Cpu},
 {id:'chatterbox',name:'Chatterbox',does:'Natural narration voices in Arabic and 22 more languages',size:'about 3 GB',Icon:Mic},
];
type State={status:string;completed:number;total:number;current:string;log:string[];error:string;supported:boolean;
 settings:{autostart:boolean;components:string[];gpu:boolean};running?:Partial<Record<Component,boolean>>;
 builds?:Partial<Record<Component,'gpu'|'cpu'>>;nvidia?:boolean};
async function request(url:string,options:RequestInit={}){
 const r=await fetch(url,{...options,headers:{'Content-Type':'application/json',...options.headers}});
 const data=await r.json();if(!r.ok)throw Error(data.detail||'Local AI setup failed.');return data;
}

/** One click per engine: SceneForge downloads the engine into its own folder (no Docker), fetches
 *  its model, starts it and connects it. Nothing to configure. */
export function LocalAISetup({onReady}:{onReady?:()=>void}){
 const [state,setState]=useState<State|null>(null),[message,setMessage]=useState(''),[starting,setStarting]=useState<string>('');
 useEffect(()=>{let active=true,last='';const check=async()=>{try{const s=await request('/api/local-ai/setup');if(active){setState(s);if(s.status==='done'&&last!=='done')onReady?.();last=s.status;}}catch(e:any){if(active)setMessage(e.message);}};void check();const timer=setInterval(check,2500);return()=>{active=false;clearInterval(timer);};},[]);
 const installing=state?.status==='running';
 const installed=(id:Component)=>!!state?.settings.components.includes(id)||!!state?.running?.[id];
 const running=(id:Component)=>id==='whisper'?installed(id):!!state?.running?.[id];
 async function install(components:Component[]){
  setStarting(components.join());setMessage('');
  try{await request('/api/local-ai/setup',{method:'POST',body:JSON.stringify({components,accept_terms:true,gpu:!!state?.settings.gpu})});setState(await request('/api/local-ai/setup'));}
  catch(e:any){setMessage(e.message);}finally{setStarting('');}
 }
 async function start(id:Component){
  setStarting(id);setMessage('');
  try{await request('/api/local-ai/start',{method:'POST',body:JSON.stringify({components:[id]})});setMessage(`Starting ${ENGINES.find(e=>e.id===id)!.name}. Loading the model can take a few minutes; this card turns green when it is ready.`);}
  catch(e:any){setMessage(e.message);}finally{setStarting('');}
 }
 async function setting(patch:Partial<State['settings']>){
  if(!state)return;
  setState({...state,settings:{...state.settings,...patch}});   // show the tick at once
  try{const settings=await request('/api/local-ai/startup',{method:'PUT',body:JSON.stringify(patch)});setState(s=>s&&{...s,settings});}
  catch(e:any){setMessage(e.message);setState(s=>s&&{...s,settings:state.settings});}
 }
 const missing=ENGINES.filter(e=>!installed(e.id)).map(e=>e.id);
 const switchable=(['stable_diffusion','chatterbox'] as Component[]).filter(c=>state?.builds?.[c]&&state.builds[c]!==(state.settings.gpu?'gpu':'cpu'));
 const unsupported=state&&!state.supported;
 return <section className="engine-install" aria-label="Install local AI">
  <div className="engine-install-head"><h3>Free AI on this computer</h3>
   {!unsupported&&missing.length>1&&<button className="btn btn-primary" disabled={installing||!!starting} onClick={()=>void install(missing)}><Download size={14} aria-hidden/> Install all</button>}</div>
  <p className="hint">One click each. SceneForge downloads, installs, starts and connects everything for you, inside its own folder: no Docker, no separate programs, no administrator rights. Models stay on this computer; nothing is uploaded.</p>
  <ul className="engine-rows">{ENGINES.map(({id,name,does,size,Icon})=>{
   const busyHere=(installing&&state?.current===id)||starting.split(',').includes(id);
   const status=busyHere?'Installing…':running(id)?'Ready':installed(id)?'Installed · not running':'Not installed';
   return <li key={id} className={`engine-row ${running(id)?'ready':''}`} aria-label={`${name}: ${status}`}>
    <span className="engine-icon" aria-hidden><Icon size={18}/></span>
    <span className="engine-text"><b>{name}</b><small>{does} · {size}</small></span>
    <span className={`engine-status ${running(id)?'ok':''}`}>{busyHere?<Loader2 size={13} className="spin" aria-hidden/>:running(id)?<CheckCircle2 size={13} aria-hidden/>:null}{status}</span>
    {!unsupported&&!running(id)&&(installed(id)
      ?<button className="btn" disabled={installing||!!starting} onClick={()=>void start(id)}><Play size={14} aria-hidden/> Start</button>
      :<button className="btn btn-primary" disabled={installing||!!starting} onClick={()=>void install([id])}><Download size={14} aria-hidden/> Install</button>)}
   </li>;})}</ul>
  {unsupported&&<p className="hint">One-click install is not available on this computer yet. Start your own engines and connect them below.</p>}
  {state&&state.total>0&&installing?<><progress aria-label="Completed AI installation stages" max={state.total} value={state.completed}/><p role="status">{state.completed} of {state.total} done{state.current?` · working on ${ENGINES.find(e=>e.id===state.current)?.name||state.current}`:''}. First setup can take 10–40 minutes; keep SceneForge open.</p></>:null}
  {(state?.error||message)&&<p role={state?.error?'alert':'status'} className={state?.error?'form-error':'hint'}>{state?.error||message}</p>}
  {!!state?.log.length&&<details open={state.status==='error'}><summary>Installation details</summary><pre>{state.log.join('\n')}</pre></details>}
  {state&&!unsupported&&<div className="engine-options">
   <label><input type="checkbox" aria-label="Start installed AI with SceneForge" checked={state.settings.autostart} disabled={installing} onChange={e=>void setting({autostart:e.target.checked})}/>Start installed engines when SceneForge opens</label>
   <label><input type="checkbox" aria-label="Use my NVIDIA graphics card" checked={!!state.settings.gpu} disabled={installing} onChange={e=>void setting({gpu:e.target.checked})}/>Use my NVIDIA graphics card for pictures and voices (much faster; needs a recent NVIDIA driver)</label>
   {state.settings.gpu&&state.nvidia===false&&<p className="hint" role="status">No NVIDIA driver was found on this computer. Install the latest NVIDIA driver first, or leave this off to use the processor.</p>}
   {switchable.length>0&&<p className="hint engine-switch" role="status">{switchable.map(c=>ENGINES.find(e=>e.id===c)!.name).join(' and ')} {switchable.length>1?'are':'is'} installed for the {state.settings.gpu?'processor':'graphics card'}.
     <button className="btn" disabled={installing||!!starting} onClick={()=>void install(switchable)}>Switch to the {state.settings.gpu?'graphics card':'processor'}</button> {state.settings.gpu?'Downloads the NVIDIA build of PyTorch (about 2.5 GB); your models are kept.':'Downloads the processor build of PyTorch (about 200 MB).'}</p>}
  </div>}
  <p className="hint engine-terms">Installing downloads free software and models. By clicking Install you accept their terms: <a href="https://huggingface.co/spaces/CompVis/stable-diffusion-license" target="_blank" rel="noreferrer">Stable Diffusion model</a> · <a href="https://github.com/resemble-ai/chatterbox/blob/master/LICENSE" target="_blank" rel="noreferrer">Chatterbox</a> · <a href="https://huggingface.co/hexgrad/Kokoro-82M" target="_blank" rel="noreferrer">Kokoro</a> · <a href="https://github.com/pytorch/pytorch/blob/main/LICENSE" target="_blank" rel="noreferrer">PyTorch</a>. Allow about 12 GB of free space for everything.</p>
 </section>;
}
