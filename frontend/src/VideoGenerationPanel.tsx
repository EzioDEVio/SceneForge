import {useEffect,useMemo,useRef,useState} from 'react';
import {CheckCircle2,Clapperboard,Download,ExternalLink,Film,HelpCircle,LoaderCircle,Plus,Settings,Sparkles,Subtitles,Upload,X} from 'lucide-react';
import {api,type Asset,type Job,type Project,type ProviderProfile,type VideoGenerationRequest,type VideoModel} from './api';

type Props={project:Project;selectedSceneId:string|null;onClose:()=>void;onOpenSettings:()=>void;onAdd:(assetId:string,placement:'after'|'inside')=>Promise<string|void>;onCaptions:(sceneId:string)=>Promise<void>};
const ratioSize:Record<string,[number,number]>={'16:9':[1280,720],'9:16':[720,1280],'1:1':[1024,1024]};
const money=(n:number)=>'$'+n.toFixed(2);
const modelRates=(model:VideoModel)=>{
  if(model.kind==='local')return 'No provider fee';
  const entries=typeof model.price_per_second==='number'?[['all',model.price_per_second] as [string,number]]:Object.entries(model.price_per_second);
  return entries.map(([resolution,rate])=>`${resolution==='all'?'':resolution+' '}${money(rate)}/sec`).join(' · ');
};

export default function VideoGenerationPanel({project,selectedSceneId,onClose,onOpenSettings,onAdd,onCaptions}:Props){
  const [models,setModels]=useState<VideoModel[]>([]),[pricesChecked,setPricesChecked]=useState(''),[providerProfiles,setProviderProfiles]=useState<ProviderProfile[]>([]);
  const [provider,setProvider]=useState('local_comfy'),[modelId,setModelId]=useState('ltx-2.5-fast');
  const [prompt,setPrompt]=useState(''),[negative,setNegative]=useState('');
  const [ratio,setRatio]=useState(project.aspect),[customW,setCustomW]=useState(720),[customH,setCustomH]=useState(1280);
  const [resolution,setResolution]=useState('720p'),[duration,setDuration]=useState(5),[seed,setSeed]=useState('');
  const [localStatus,setLocalStatus]=useState<{ready:boolean;message:string}>({ready:false,message:'Checking local engine…'});
  const [jobId,setJobId]=useState<string|null>(null),[job,setJob]=useState<Job|null>(null),[asset,setAsset]=useState<Asset|null>(null);
  const [error,setError]=useState(''),[busy,setBusy]=useState(false),[placement,setPlacement]=useState<'after'|'inside'>('after');
  const [addedSceneId,setAddedSceneId]=useState(''),[captionBusy,setCaptionBusy]=useState(false),[workflowBusy,setWorkflowBusy]=useState(false),[paidConfirm,setPaidConfirm]=useState(false);
  const workflowRef=useRef<HTMLInputElement>(null);
  useEffect(()=>{api.videoGenerationCatalog().then(data=>{setModels(data.models);setPricesChecked(data.prices_checked);}).catch(e=>setError(e.message));void refreshProviders();void checkLocalEngine();const refresh=()=>{void refreshProviders();void checkLocalEngine();};window.addEventListener('sceneforge:providers-changed',refresh);return()=>window.removeEventListener('sceneforge:providers-changed',refresh);},[]);
  async function refreshProviders(){try{setProviderProfiles(await api.listProviders());}catch{setProviderProfiles([]);}}
  async function checkLocalEngine(){try{setLocalStatus(await api.localVideoStatus());}catch{setLocalStatus({ready:false,message:'Could not check local ComfyUI.'});}}
  const providerModels=useMemo(()=>models.filter(m=>m.provider===provider),[models,provider]);
  const model=providerModels.find(m=>m.id===modelId)||providerModels[0];
  const cloudProfile=providerProfiles.find(p=>p.capability==='video'&&p.name===provider);
  useEffect(()=>{if(!models.length)return;const first=models.find(m=>m.provider===provider);if(first&&!models.some(m=>m.id===modelId&&m.provider===provider))setModelId(first.id);},[models,provider,modelId]);
  useEffect(()=>{if(!model)return;
    if(!model.ratios.includes(ratio))setRatio(model.ratios.includes(project.aspect)?project.aspect:model.ratios[0]);
    if(!model.resolutions.includes(resolution))setResolution(model.resolutions[0]);
    if(model.durations.length){if(!model.durations.includes(duration))setDuration(model.durations[0]);}
    else setDuration(Math.max(model.duration_min,Math.min(model.duration_max,duration)));
  },[model?.id]);
  const outputDims=useMemo(()=>{
    if(ratio==='custom')return [customW,customH];
    if(model?.kind==='local'){
      const tier=resolution==='480p'?480:resolution==='1080p'?1088:resolution==='4k'?2160:720;
      if(ratio==='1:1')return [tier,tier];
      if(ratio==='9:16')return [tier===480?480:tier===1088?1088:tier,tier===480?832:tier===1088?1920:1280];
      return [tier===480?832:tier===1088?1920:tier,tier===480?480:tier===1088?1088:720];
    }
    return ratioSize[ratio]||ratioSize[project.aspect]||ratioSize['16:9'];
  },[ratio,customW,customH,model?.kind,resolution,project.aspect]);
  const cost=useMemo(()=>{
    if(!model)return null;const rate=typeof model.price_per_second==='number'?model.price_per_second:model.price_per_second[resolution];
    return rate===undefined?null:{total:rate*duration,rate};
  },[model,resolution,duration]);
  const customDimensionsValid=ratio!=='custom'||(Number.isInteger(customW)&&Number.isInteger(customH)&&customW>=256&&customH>=256&&customW<=4096&&customH<=4096&&customW%16===0&&customH%16===0);
  const seedValid=seed.trim()===''||(Number.isInteger(Number(seed))&&Number(seed)>=0&&Number(seed)<=4294967295);
  useEffect(()=>{if(!jobId){setJob(null);return;}
    let stop=false;let timer:ReturnType<typeof setInterval>;
    const check=()=>api.getJob(jobId).then(next=>{if(stop)return;setJob(next);if(next.status==='succeeded'&&next.artifact_asset_id){api.getAsset(next.artifact_asset_id).then(setAsset).catch(()=>{});clearInterval(timer);}if(['failed','cancelled'].includes(next.status))clearInterval(timer);}).catch(()=>{});
    void check();timer=setInterval(()=>void check(),1800);return()=>{stop=true;clearInterval(timer);};
  },[jobId]);
  const active=!!job&&['queued','running','cancelling'].includes(job.status);
  const costLabel=model?.kind==='local'?'No provider fee':cost?`Estimated ${money(cost.total)} USD${model?.provider==='runway'?` · ${Math.round(cost.total/0.01)} credits`:''}`:'Choose a supported quality';
  const canGenerate=!!model&&prompt.trim().length>0&&!active&&!busy&&customDimensionsValid&&seedValid&&(!model.workflow_imported||model.kind!=='local'||localStatus.ready)&&(model.kind==='local'?model.workflow_imported:!!cost&&paidConfirm&&!!cloudProfile?.configured);
  function chooseProvider(next:string){setProvider(next);setPaidConfirm(false);setError('');}
  async function importWorkflow(file?:File){if(!file||!model||model.kind!=='local')return;setWorkflowBusy(true);setError('');try{await api.importLocalVideoWorkflow(model.id,file);setModels(ms=>ms.map(m=>m.id===model.id?{...m,workflow_imported:true}:m));}catch(e:any){setError(e.message);}finally{setWorkflowBusy(false);if(workflowRef.current)workflowRef.current.value='';}}
  async function generate(){if(!model||!canGenerate)return;setError('');setAsset(null);setAddedSceneId('');setBusy(true);
    try{const [width,height]=outputDims;const request:VideoGenerationRequest={provider,model:model.id,prompt:prompt.trim(),negative_prompt:negative.trim(),aspect_ratio:ratio,width,height,duration_seconds:duration,resolution,seed:seed.trim()?Number(seed):null,confirm_paid:model.kind==='cloud'&&paidConfirm};const started=await api.generateVideo(project.id,request);setJobId(started.job_id);}
    catch(e:any){setError(e.message);}finally{setBusy(false);}
  }
  async function addGenerated(){if(!asset)return;setBusy(true);setError('');try{const sceneId=await onAdd(asset.id,placement);if(sceneId)setAddedSceneId(sceneId);}catch(e:any){setError(e.message);}finally{setBusy(false);}}
  async function createCaptions(){if(!addedSceneId)return;setCaptionBusy(true);setError('');try{await onCaptions(addedSceneId);onClose();}catch(e:any){setError(e.message);}finally{setCaptionBusy(false);}}
  const progressMessage=job?.stage||'Preparing request…';
  return <div className="drawer-backdrop video-gen-backdrop" onClick={()=>!active&&onClose()}>
    <section className="drawer video-gen-panel" role="dialog" aria-modal="true" aria-label="Generate video from text" onClick={e=>e.stopPropagation()}>
      <header className="video-gen-header"><div className="video-gen-brand"><span className="video-gen-icon"><Clapperboard size={19}/></span><div><span className="eyebrow">SCENEFORGE STUDIO</span><h2>Generate video</h2><p>Create a clip from a written prompt, then edit it on your timeline.</p></div></div><button className="icon-btn" aria-label="Close video generation" disabled={active} onClick={onClose}><X size={17}/></button></header>

      <section className="video-gen-section"><div className="video-gen-section-title"><span>01</span><div><h3>Choose an engine</h3><p>Local models run on your computer. Cloud models are billed by their provider.</p></div></div>
        <div className="video-gen-provider-row" role="tablist" aria-label="Video provider">
          {[['local_comfy','Local'],['google_veo','Google Veo'],['runway','Runway']].map(([id,label])=><button type="button" key={id} role="tab" aria-selected={provider===id} className={provider===id?'active':''} onClick={()=>chooseProvider(id)}>{id==='local_comfy'?<Film size={15}/>:<Sparkles size={15}/>} {label}</button>)}
        </div>
        {providerModels.length>0&&<label className="control-label video-gen-model">Model<select aria-label="Video model" value={model?.id||''} onChange={e=>{setModelId(e.target.value);setPaidConfirm(false);}}>{providerModels.map(m=><option value={m.id} key={m.id}>{m.name} · {modelRates(m)}</option>)}</select></label>}
        {model&&<div className={`video-gen-model-card ${model.kind}`}><div className="video-gen-model-top"><strong>{model.name}</strong><span className={model.kind==='local'?'local-price':''}>{costLabel}</span></div><p>{model.requirements}</p><small className="video-gen-rate-list">{model.kind==='cloud'?'Published rates: ':'Provider cost: '}{modelRates(model)}{model.kind==='cloud'?` · checked ${pricesChecked||'recently'}`:''}</small><div className="video-gen-model-links"><a href={model.workflow_url} target="_blank" rel="noreferrer">Setup guide <ExternalLink size={12}/></a>{model.terms_url&&<a href={model.terms_url} target="_blank" rel="noreferrer">Model terms <ExternalLink size={12}/></a>}</div>{model.kind==='cloud'&&<small>{model.cost_note} Estimate is not a guarantee of the provider's final charge.</small>}</div>}
        {model?.kind==='cloud'&&!cloudProfile?.configured&&<div className="video-gen-local-setup"><p className="hint">Connect {provider==='google_veo'?'Google AI Studio':'Runway'} in Settings before generating. The API key stays in your operating system's credential store.</p><button className="btn" onClick={onOpenSettings}><Settings size={14}/> Open provider settings</button></div>}
        {provider==='local_comfy'&&<div className="video-gen-local-setup"><div className={`video-gen-engine-status ${localStatus.ready?'ready':''}`}><span className="status-dot"/>{localStatus.message}<button className="text-btn" onClick={()=>void checkLocalEngine()}>Check again</button><button className="text-btn" onClick={onOpenSettings}><Settings size={13}/> Settings</button></div>
          <div className="video-gen-setup-steps"><strong>Connect a local model</strong><ol><li>Install and start ComfyUI. Set its address under Settings → Providers.</li><li>Open the setup guide and download the model files plus the matching text-to-video workflow.</li><li>In ComfyUI, open the workflow and choose <b>Save (API Format)</b>.</li><li>Import that JSON below. Use trusted workflows; custom nodes run inside ComfyUI with your user permissions. Model weights stay outside the SceneForge installer.</li></ol></div>
          <input ref={workflowRef} hidden type="file" accept=".json,application/json" onChange={e=>void importWorkflow(e.target.files?.[0])}/>
          <div className="video-gen-workflow-state"><span>{model?.workflow_imported?<><CheckCircle2 size={15}/> Workflow imported for this model</>:'No workflow imported for this model'}</span><button className="btn" disabled={!model||workflowBusy} onClick={()=>workflowRef.current?.click()}>{workflowBusy?<LoaderCircle size={14} className="spin"/>:<Upload size={14}/>} {workflowBusy?'Importing…':'Import API workflow'}</button></div>
        </div>}
        {model?.kind==='cloud'&&<label className="video-gen-paid-confirm"><input type="checkbox" checked={paidConfirm} onChange={e=>setPaidConfirm(e.target.checked)}/><span>I understand this generation may cost <b>{cost?.total!==undefined?money(cost.total)+' USD':'the estimate shown above'}</b>. The provider's final billing and taxes may differ.</span></label>}
      </section>

      <section className="video-gen-section"><div className="video-gen-section-title"><span>02</span><div><h3>Describe the clip</h3><p>Specify the subject, movement, camera and visual style. Avoid asking the model to draw exact text.</p></div></div>
        <label className="control-label">Prompt<textarea value={prompt} onChange={e=>setPrompt(e.target.value)} maxLength={5000} placeholder="A close-up of a ceramic cup on a rainy windowsill. The camera slowly pushes in as raindrops slide down the glass; soft morning light, natural colors, cinematic depth of field…"/></label>
        {model?.kind==='local'&&<label className="control-label">Negative prompt <textarea className="video-gen-negative" value={negative} onChange={e=>setNegative(e.target.value)} maxLength={1000} placeholder="Optional: visual elements to avoid"/></label>}
        <div className="video-gen-controls">
          <label className="control-label">Aspect ratio<select value={ratio} onChange={e=>setRatio(e.target.value)}>{model?.ratios.map(r=><option value={r} key={r}>{r==='custom'?'Custom dimensions':r+(r===project.aspect?' · project':'' )}</option>)}</select></label>
          <label className="control-label">Duration {model?.durations.length?'(seconds)':''}{model?.durations.length?<select value={duration} onChange={e=>setDuration(Number(e.target.value))}>{model.durations.map(d=><option key={d} value={d}>{d} seconds</option>)}</select>:<input type="number" min={model?.duration_min||1} max={model?.duration_max||30} step={1} value={duration} onChange={e=>setDuration(Number(e.target.value))}/>}</label>
          <label className="control-label">Quality<select value={resolution} onChange={e=>setResolution(e.target.value)}>{model?.resolutions.map(r=><option key={r} value={r}>{r}</option>)}</select></label>
          <label className="control-label">Seed <input type="number" min={0} max={4294967295} value={seed} placeholder="Random" onChange={e=>setSeed(e.target.value)}/></label>
        </div>
        {ratio==='custom'&&model?.kind==='local'&&<div className="video-gen-custom-dimensions"><label className="control-label">Width<input type="number" min={256} max={4096} step={16} value={customW} aria-invalid={!customDimensionsValid} onChange={e=>setCustomW(Number(e.target.value))}/></label><span>×</span><label className="control-label">Height<input type="number" min={256} max={4096} step={16} value={customH} aria-invalid={!customDimensionsValid} onChange={e=>setCustomH(Number(e.target.value))}/></label><small>{customDimensionsValid?'Use multiples of 16, from 256 to 4096 px.':'Enter whole pixel sizes from 256 to 4096, each divisible by 16.'}</small></div>}
        <div className="video-gen-audio-note"><HelpCircle size={14}/>{model?.native_audio===true?'This model can generate sound with the video. Use Text → Auto captions after adding it to transcribe spoken audio.':model?.native_audio===false?'This model normally generates picture only. Add or record audio in the existing Audio panel.':'Audio depends on the imported workflow. SceneForge will keep any audio track the workflow outputs; you can also add audio in the Audio panel.'}</div>
      </section>

      {error&&<div className="error-box" role="alert">{error}<button className="text-btn" onClick={()=>setError('')}>Dismiss</button></div>}
      {active&&<div className="video-gen-progress" role="status"><div className="video-gen-progress-head"><LoaderCircle size={17} className="spin"/><div><strong>{job?.status==='queued'?'Waiting for the engine': 'Generating your clip'}</strong><span>{progressMessage}</span></div><button className="btn" onClick={()=>void api.cancelJob(jobId!).catch(e=>setError(e.message))}>Cancel</button></div><div className="video-gen-indeterminate"><span/></div><small>Provider progress is not exposed by this model; the bar indicates that the job is active.</small></div>}
      {job?.status==='failed'&&<div className="error-box" role="alert">Generation failed: {job.error||'The selected provider returned an error.'}</div>}
      {job?.status==='cancelled'&&<p className="hint" role="status">Generation cancelled.</p>}
      {asset&&<section className="video-gen-result"><div className="video-gen-result-heading"><CheckCircle2 size={17}/><div><strong>Generated video is ready</strong><span>{asset.original_filename} · {asset.width||'—'} × {asset.height||'—'} · {asset.duration_ms?`${(asset.duration_ms/1000).toFixed(1)} s`:''}</span></div><a className="text-btn" href={api.assetDownloadUrl(asset.id)} download><Download size={14}/> Download</a></div><video controls playsInline src={api.assetStreamUrl(asset.id)}/>
        {!addedSceneId?<div className="video-gen-add-row"><label className="control-label">Add to timeline<select value={placement} onChange={e=>setPlacement(e.target.value as 'after'|'inside')}><option value="after">Create new scene after selected</option><option value="inside" disabled={!selectedSceneId}>Add inside selected scene</option></select></label><button className="btn btn-primary" disabled={busy} onClick={()=>void addGenerated()}><Plus size={15}/>{busy?'Adding…':'Add to timeline'}</button></div>:<div className="video-gen-caption-next"><span><CheckCircle2 size={15}/> Added to timeline. You can still edit the clip and its sound.</span><button className="btn" disabled={captionBusy} onClick={()=>void createCaptions()}>{captionBusy?<LoaderCircle size={14} className="spin"/>:<Subtitles size={14}/>} {captionBusy?'Generating captions…':'Generate captions & open Text'}</button></div>}
        {addedSceneId&&<p className="hint">Captions use local speech recognition by default, transcribing scene narration when present or video sound otherwise. This closes the generator and opens Text so you can edit each timed phrase, apply a caption style, and continue with the existing effects and overlays.</p>}
      </section>}
      {model?.kind==='local'&&model.native_audio&&<p className="video-gen-license-note">Model weights are downloaded separately and may have their own license and hardware requirements. Review the model terms before publishing generated work.</p>}
      <footer className="video-gen-footer"><button className="btn" disabled={active} onClick={onClose}>Close</button><span>{costLabel}</span><button className="btn btn-primary" disabled={!canGenerate} onClick={()=>void generate()}><Sparkles size={15}/>{busy?'Starting…':model?.kind==='cloud'?'Generate and confirm charge':'Generate video'}</button></footer>
    </section>
  </div>;
}
