import React, {useMemo, useState} from 'react';
import {Check, Clipboard, Download, ExternalLink, FolderOpen, Share2, X} from 'lucide-react';
import {api} from './api';

type Destination = {name:string; url:string; steps:string; note?:string};
const DESTINATIONS:Destination[] = [
  {name:'YouTube',url:'https://studio.youtube.com',steps:'Open Create → Upload videos. Add a title, description, audience and visibility before publishing.',note:'Direct API uploads require your authorization. Unverified API projects have upload restrictions.'},
  {name:'TikTok',url:'https://www.tiktok.com/upload',steps:'Choose the exported video, add a caption and cover, then review audience and posting options.',note:'Direct posting requires a developer app and TikTok audit approval.'},
  {name:'Instagram',url:'https://www.instagram.com/',steps:'Open Create → Post, select the video, choose a cover and add your caption.',note:'Direct publishing is limited to eligible Professional accounts.'},
  {name:'Facebook',url:'https://www.facebook.com/',steps:'Create a video post or Reel, choose the destination Page/profile, add a caption and publish.',note:'Direct publishing requires Meta app setup and account permissions.'},
];

export function ShareDialog({assetId,fileName,onClose,onReveal}:{assetId:string;fileName:string;onClose:()=>void;onReveal?:(assetId:string)=>Promise<unknown>}) {
  const [copied,setCopied]=useState(false),[error,setError]=useState('');
  const downloadUrl=api.assetDownloadUrl(assetId);
  const fileUrl=useMemo(()=>new URL(downloadUrl,window.location.href).href,[downloadUrl]);
  async function shareFile(){
    setError('');
    try {
      const response=await fetch(api.assetStreamUrl(assetId));
      if(!response.ok)throw new Error('Could not read the exported video.');
      const file=new File([await response.blob()],fileName,{type:response.headers.get('content-type')||'video/mp4'});
      if(navigator.share&&(!navigator.canShare||navigator.canShare({files:[file]}))){await navigator.share({files:[file],title:fileName});return;}
      const clipboard=navigator.clipboard;
      if(clipboard?.writeText){await clipboard.writeText(fileUrl);setCopied(true);setTimeout(()=>setCopied(false),2500);return;}
      throw new Error('This browser cannot share files directly. Download the video, then use a platform below.');
    } catch(e:any){if(e?.name==='AbortError')return;setError(e?.message||'Sharing is unavailable here. Download the video and choose a platform below.');}
  }
  function open(url:string){const d=(window as any).sceneforgeDesktop;if(d?.openExternal)void d.openExternal(url);else window.open(url,'_blank','noopener,noreferrer');}
  async function reveal(){
    if(onReveal){try{await onReveal(assetId);return;}catch(e:any){setError(e?.message||'Could not open the export folder.');}}
    // Browser mode: the SceneForge server runs on this computer and can open the folder.
    try{
      const r=await fetch(`/api/assets/${assetId}/reveal`,{method:'POST',headers:{'X-SceneForge-Action':'reveal'}});
      if(r.ok)return;
      const body=await r.json().catch(()=>({}));
      setError(body?.detail||'Could not open the export folder. Use Download instead.');
    }catch{setError('Could not reach SceneForge to open the folder. Use Download instead.');}
  }
  return <div className="info-backdrop share-backdrop" onMouseDown={e=>e.target===e.currentTarget&&onClose()}>
    <section className="info-panel wide share-dialog" role="dialog" aria-modal="true" aria-label="Share exported video">
      <header><span className="info-title"><Share2 size={18}/> Your video is ready to share</span><button className="icon-reset info-close" aria-label="Close share dialog" onClick={onClose}><X size={16}/></button></header>
      <div className="info-body">
        <div className="share-export-file"><div className="share-file-icon"><Share2 size={20}/></div><div><strong>{fileName}</strong><small>Export is saved in this SceneForge project.</small></div></div>
        <div className="share-primary-actions">
          <a className="btn btn-primary" href={downloadUrl} download><Download size={15}/> Download video</a>
          <button className="btn" onClick={()=>void reveal()}><FolderOpen size={15}/> Open file location</button>
          <button className="btn" onClick={()=>void shareFile()}><Share2 size={15}/> {copied?<><Check size={14}/> Link copied</>:'Share file…'}</button>
        </div>
        <p className="hint">The exported file stays on your computer until you choose a destination. SceneForge does not upload it automatically.</p>
        <h3 className="share-destinations-title">Choose a platform</h3>
        <div className="share-destinations">{DESTINATIONS.map(p=><article key={p.name} className="share-destination">
          <div><strong>{p.name}</strong><button className="text-btn" onClick={()=>open(p.url)}>Open {p.name} <ExternalLink size={12}/></button></div>
          <p>{p.steps}</p>{p.note&&<small>{p.note}</small>}
        </article>)}</div>
        {error&&<p className="form-error" role="status">{error}</p>}
        <div className="button-row"><button className="text-btn" onClick={async()=>{try{await navigator.clipboard.writeText(fileUrl);setCopied(true);setTimeout(()=>setCopied(false),2500);}catch{setError('Clipboard access is unavailable. Use Download video instead.');}}}><Clipboard size={13}/> Copy local video link</button><button className="btn" onClick={onClose}>Done</button></div>
      </div>
    </section>
  </div>;
}
