import React, {useEffect, useState} from 'react';
import {Check, ChevronDown, ExternalLink, KeyRound} from 'lucide-react';
import {api, type ProviderProfile} from './api';
import {PROVIDER_NOTES, PROVIDER_OPTIONS} from './providerCatalog';

const CAPABILITY: Record<string, string> = {image: 'Images', speech: 'Voice', video: 'Video'};

// Same provider API and credential store as the existing Settings drawer.
export function ProviderConnection({name, profile, onSaved, accountUrl, onOpenAccount}: {name:string; profile?:ProviderProfile; onSaved:()=>Promise<unknown>; accountUrl?:string; onOpenAccount?:(url:string)=>void}) {
  const option = PROVIDER_OPTIONS.find(p=>p.name===name)!;
  const [key,setKey]=useState(''), [model,setModel]=useState(profile?.model||option.model),
    [url,setUrl]=useState(profile?.base_url||option.url), [busy,setBusy]=useState(false), [message,setMessage]=useState(''), [open,setOpen]=useState(false);
  useEffect(()=>{setModel(profile?.model||option.model);setUrl(profile?.base_url||option.url);},[profile?.model,profile?.base_url,name]);
  async function save(e:React.FormEvent) {
    e.preventDefault();if(busy||!key.trim())return;setBusy(true);setMessage('');
    try {await api.upsertProvider(option.capability,name,key,model,url);setKey('');await onSaved();window.dispatchEvent(new Event('sceneforge:providers-changed'));setMessage('Saved. Choose it when generating an image, voice or video.');}
    catch(e:any){setMessage(e.message||'Could not save this provider.');}finally{setBusy(false);}
  }
  const [label, kind] = option.label.split(' · ');
  const connected = !!profile?.configured;
  return <details className={`provider-connection ${connected ? 'connected' : ''}`} onToggle={e=>{const o=e.currentTarget.open;setOpen(o);if(!o){setKey('');setMessage('');}}}>
    <summary aria-label={`${label}: ${connected ? 'connected' : 'not connected'}. ${open ? 'Collapse' : 'Expand'} to ${connected ? 'replace the key' : 'add a key'}.`}>
      <span className="provider-badge" aria-hidden>{label.slice(0, 1)}</span>
      <span className="provider-title"><strong>{label}</strong><small>{kind || CAPABILITY[option.capability]} · {connected ? `key ${profile?.masked_key || 'saved'}` : 'add your API key'}</small></span>
      <span className={`provider-state ${connected ? 'ok' : ''}`}>{connected ? <><Check size={13} aria-hidden/> Connected</> : 'Not connected'}</span>
      <span className="provider-chevron" aria-hidden><ChevronDown size={16}/></span>
    </summary>
    <form onSubmit={save} aria-label={`${label} provider settings`}>
      <p className="hint">{PROVIDER_NOTES[name]}</p>
      <fieldset disabled={busy}>
        <label className="control-label">{label} API key<input aria-label={`${label} API key`} type="password" autoComplete="off" value={key} onChange={e=>setKey(e.target.value)} placeholder={connected?'Enter a key to replace the saved key':'Paste your provider API key'}/></label>
        <label className="control-label">Model<input aria-label={`${label} model`} value={model} disabled={name==='cloudflare'||option.capability==='video'} onChange={e=>setModel(e.target.value)}/></label>
        {(name==='elevenlabs'||name==='cloudflare')&&<label className="control-label">{name==='cloudflare'?'Cloudflare account ID':'ElevenLabs API URL'}<input aria-label={`${label} connection`} value={url} onChange={e=>setUrl(e.target.value)}/></label>}
        <p className="hint">Saving connects the settings only; it does not generate content or spend credits. Keys use the existing system credential store.</p>
        <div className="provider-actions">
          <button className="btn primary" type="submit" disabled={busy||!key.trim()}><KeyRound size={14} aria-hidden/> {busy?'Saving…':`Save ${label} key`}</button>
          {accountUrl&&onOpenAccount&&<button type="button" className="text-btn" onClick={()=>onOpenAccount(accountUrl)}><ExternalLink size={12} aria-hidden/> {connected?`${label} account`:"Get an API key"}</button>}
        </div>
      </fieldset>
      {message&&<p role="status">{message}</p>}
    </form>
  </details>;
}
