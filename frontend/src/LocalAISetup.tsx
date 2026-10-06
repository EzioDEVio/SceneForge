import React,{useEffect,useState} from 'react';
const LABELS={whisper:'Whisper · automatic captions',stable_diffusion:'Stable Diffusion · local pictures',chatterbox:'Chatterbox · multilingual voices'};
type State={status:string;completed:number;total:number;current:string;log:string[];error:string;supported:boolean;settings:{autostart:boolean;components:string[];gpu:boolean}};
async function request(url:string,options:RequestInit={}){
 const r=await fetch(url,{...options,headers:{'Content-Type':'application/json',...options.headers}});
 const data=await r.json();if(!r.ok)throw Error(data.detail||'Local AI setup failed.');return data;
}
export function LocalAISetup({onReady}:{onReady?:()=>void}){
 const [state,setState]=useState<State|null>(null),[selected,setSelected]=useState<string[]>(Object.keys(LABELS)),[terms,setTerms]=useState(false),[gpu,setGpu]=useState(false),[message,setMessage]=useState(''),[starting,setStarting]=useState(false);
 useEffect(()=>{let active=true,last='';const check=async()=>{try{const s=await request('/api/local-ai/setup');if(active){setState(s);if(s.status==='done'&&last!=='done')onReady?.();last=s.status;}}catch(e:any){if(active)setMessage(e.message);}};void check();const timer=setInterval(check,2000);return()=>{active=false;clearInterval(timer);};},[]);
 const busy=starting||state?.status==='running';
 async function install(){setStarting(true);setMessage('');try{await request('/api/local-ai/setup',{method:'POST',body:JSON.stringify({components:selected,accept_terms:terms,gpu})});setState(await request('/api/local-ai/setup'));}catch(e:any){setMessage(e.message);}finally{setStarting(false);}}
 return <section className="engine-install" aria-label="Install local AI"><h3>Set up free local AI</h3><p className="hint">Install here or during Windows setup. Models stay on this computer. First setup downloads several GB; allow at least 15 GB of free space. Keep SceneForge open until setup finishes.</p>
 {Object.entries(LABELS).map(([id,label])=><label key={id}><input type="checkbox" aria-label={label} checked={selected.includes(id)} disabled={busy} onChange={e=>setSelected(e.target.checked?[...selected,id]:selected.filter(c=>c!==id))}/>{label}</label>)}
 <label><input type="checkbox" checked={gpu} disabled={busy} onChange={e=>setGpu(e.target.checked)}/>Use my NVIDIA GPU for images</label><p className="hint">Requires a compatible NVIDIA driver and Docker GPU support. Leave off for CPU mode; CPU image generation is slow.</p>
 <details><summary>Downloads and component terms</summary><p className="hint">Whisper base: about 145 MB. Voice/image engines and runtimes: several GB. Images and voices use Docker Desktop; Windows may require approval, first-run setup or a restart. Docker’s terms and eligibility apply. Whisper runs directly in SceneForge.</p><p><a href="https://www.docker.com/legal/docker-subscription-service-agreement/" target="_blank" rel="noreferrer">Docker terms</a> · <a href="https://huggingface.co/spaces/CompVis/stable-diffusion-license" target="_blank" rel="noreferrer">Image model terms</a> · <a href="https://github.com/resemble-ai/chatterbox/blob/master/LICENSE" target="_blank" rel="noreferrer">Chatterbox license</a></p></details>
 <label><input type="checkbox" aria-label="Accept local AI component terms" checked={terms} disabled={busy} onChange={e=>setTerms(e.target.checked)}/>I reviewed the component terms and agree to install the selected software and models.</label>
 <button className="btn btn-primary" disabled={busy||!state?.supported||!terms||!selected.length} onClick={()=>void install()}>{busy?'Installing…':state?.status==='error'?'Retry local AI setup':'Install selected AI'}</button>
 {state&&!state.supported&&<p className="hint">Automatic installation is available on Windows. Existing local connections remain available here.</p>}
 {state?.total? <><progress aria-label="Completed AI installation stages" max={state.total} value={state.completed}/><p role="status">{state.completed} of {state.total} components checked{state.current?' · '+state.current:''}. {state.status==='done'?'Ready':state.status==='running'?'Setup in progress':''}</p></>:null}
 {(state?.error||message)&&<p role="alert">{state?.error||message}</p>}
 {!!state?.log.length&&<details open={state.status==='running'||state.status==='error'}><summary>Installation progress</summary><pre>{state.log.join('\n')}</pre></details>}
 {state&&<label><input type="checkbox" aria-label="Start installed AI with SceneForge" checked={state.settings.autostart} disabled={busy} onChange={async e=>{try{const settings=await request('/api/local-ai/startup',{method:'PUT',body:JSON.stringify({autostart:e.target.checked})});setState({...state,settings});}catch(e:any){setMessage(e.message);}}}/>Start installed image and voice engines with SceneForge</label>}
 </section>;
}
