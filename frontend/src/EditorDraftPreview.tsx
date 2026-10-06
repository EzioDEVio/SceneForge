import React,{useEffect,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import {api} from './api';
import type {EditorEdits} from './editorDraft';

export function EditorDraftPreview({sceneId,edits,dirty,active,busy,onApply,onCancel}:{sceneId:string;edits:EditorEdits;dirty:boolean;active:boolean;busy:boolean;onApply:()=>void;onCancel:()=>void}){
 const [host,setHost]=useState<Element|null>(null),[open,setOpen]=useState(true);
 const [jobId,setJobId]=useState<string|null>(null),[error,setError]=useState(''),[starting,setStarting]=useState(false);
 const generation=useRef(0),signature=JSON.stringify(edits),[renderSignature,setRenderSignature]=useState('');
 const [job,setJob]=useState<any>(null),[connectionError,setConnectionError]=useState(''),[retry,setRetry]=useState(0);
 useEffect(()=>{
  let live=true,failures=0,inFlight=false;const controller=new AbortController();
  setConnectionError('');if(!jobId)return;
  const poll=async()=>{if(inFlight)return;inFlight=true;const timeout=setTimeout(()=>controller.abort(),10000);
   try{const j=await api.getJob(jobId,controller.signal);if(live){setJob(j);setConnectionError('');failures=0;}}
   catch(e:any){if(live&&(++failures>=3||controller.signal.aborted))setConnectionError('Cannot check the render. Retry the connection or stop this preview.');}
   finally{clearTimeout(timeout);inFlight=false;}
  };
  void poll();const timer=setInterval(()=>{if(!controller.signal.aborted)void poll();},1000);
  return()=>{live=false;controller.abort();clearInterval(timer);};
 },[jobId,retry]);
 useEffect(()=>{setHost(document.querySelector('.scene-editor:not([hidden]) [data-companion-preview]'));},[active,dirty]);
 useEffect(()=>{generation.current++;setRenderSignature('');},[signature,dirty]);
 useEffect(()=>()=>{generation.current++;},[]);
 const running=starting||!!jobId&&(!job||['queued','running','cancelling'].includes(job.status));
 async function render(){const ticket=++generation.current;setStarting(true);setError('');setConnectionError('');setOpen(true);try{const result=await api.previewEditorDraft(sceneId,edits);if(ticket!==generation.current){void api.cancelJob(result.job_id).catch(()=>{});return;}setJob(null);setJobId(result.job_id);setRenderSignature(signature);}catch(e:any){if(ticket===generation.current)setError(e.message);}finally{setStarting(false);}}
 async function stop(){if(!jobId)return;try{await api.cancelJob(jobId);setRetry(n=>n+1);}catch(e:any){setError(`Could not stop preview: ${e.message}`);}}
 function cancel(){generation.current++;if(jobId&&running)void stop();setJobId(null);setJob(null);setError('');onCancel();}
 const current=dirty&&renderSignature===signature,ready=current&&job?.status==='succeeded'&&job.artifact_asset_id;
 const status=starting?'Starting render…':connectionError||error||(current&&job?.status==='failed'&&(job.error||'Preview failed. Try rendering again.'))||(current&&job?.status==='cancelled'&&'Preview stopped. You can render again.')||(running?`${job?.stage||'Rendering scene'} · ${Math.round(job?.progress||0)}%`:'Render your draft to see movement, captions and sound.');
 const failure=error||connectionError||current&&job?.status==='failed';
 return <section className="editor-draft-actions" aria-label="Motion and Effects draft">
  <p aria-live="polite">{dirty?'Draft · not saved':'Saved settings'}{dirty&&!current?' · preview outdated':''}</p>
  <div className="button-row"><button className="btn" disabled={!dirty||running||busy} onClick={()=>void render()}>Render draft preview</button><button className="btn btn-primary" disabled={!dirty||busy||running} onClick={onApply}>Apply changes</button><button className="btn" disabled={!dirty||busy} onClick={cancel}>Cancel changes</button>{!open&&<button className="btn" onClick={()=>setOpen(true)}>Open draft companion</button>}</div>
  <p className="hint">Draft render checks this scene. Project music and timeline layers are available in the main timeline preview.</p>
  {running&&<button className="btn" disabled={!jobId} onClick={()=>void stop()}>Stop preview</button>}
  {failure&&<p role="alert">{error||connectionError||job.error}</p>}{connectionError&&<button className="btn" onClick={()=>setRetry(n=>n+1)}>Retry connection</button>}
  {active&&dirty&&open&&host&&createPortal(<section className="companion-preview editor-draft-companion" aria-label="Motion and Effects companion">
   <header><strong>Draft preview</strong><button aria-label="Minimize draft preview" onClick={()=>setOpen(false)}>−</button><button aria-label="Close draft preview" onClick={()=>setOpen(false)}>×</button></header>
   <div className="draft-media-frame">{ready?<video controls preload="auto" poster={api.assetThumbUrl(job.artifact_asset_id,720)} src={api.assetStreamUrl(job.artifact_asset_id)} aria-label="Rendered draft preview" onError={()=>setError('The preview video could not load. Try rendering again.')}/>:<div className="draft-preview-placeholder"><span aria-hidden="true">▶</span><p role="status">{status}</p>{running&&<progress aria-label="Draft preview progress" max={100} value={job?.progress||0}/>}</div>}</div>
   <p className="hint">{ready?'Rendered draft · review before Apply':current?'Your edits are kept while this preview renders.':'Full scene preview · render to update'}</p>
  </section>,host)}
 </section>;
}
