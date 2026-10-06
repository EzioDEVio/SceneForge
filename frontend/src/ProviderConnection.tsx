import React, {useEffect, useState} from 'react';
import {api, type ProviderProfile} from './api';
import {PROVIDER_NOTES, PROVIDER_OPTIONS} from './providerCatalog';

// Same provider API and credential store as the existing Settings drawer.
export function ProviderConnection({name, profile, onSaved}: {name:string; profile?:ProviderProfile; onSaved:()=>Promise<unknown>}) {
  const option = PROVIDER_OPTIONS.find(p=>p.name===name)!;
  const [key,setKey]=useState(''), [model,setModel]=useState(profile?.model||option.model),
    [url,setUrl]=useState(profile?.base_url||option.url), [busy,setBusy]=useState(false), [message,setMessage]=useState('');
  useEffect(()=>{setModel(profile?.model||option.model);setUrl(profile?.base_url||option.url);},[profile?.model,profile?.base_url,name]);
  async function save(e:React.FormEvent) {
    e.preventDefault();if(busy||!key.trim())return;setBusy(true);setMessage('');
    try {await api.upsertProvider(option.capability,name,key,model,url);setKey('');await onSaved();window.dispatchEvent(new Event('sceneforge:providers-changed'));setMessage('Provider saved. Choose it when generating an image, voice or video.');}
    catch(e:any){setMessage(e.message||'Could not save this provider.');}finally{setBusy(false);}
  }
  const label=option.label.split(' · ')[0];
  return <details className="provider-connection" onToggle={e=>{if(!e.currentTarget.open){setKey('');setMessage('');}}}>
    <summary><span><strong>{option.label}</strong><small>{profile?.configured?'Configured · '+(profile.masked_key||'key saved'):'Not configured · expand to add your key'}</small></span><span className="provider-expand" aria-hidden="true">⌄</span></summary>
    <form onSubmit={save} aria-label={`${label} provider settings`}>
      <p className="hint">{PROVIDER_NOTES[name]}</p>
      <fieldset disabled={busy}>
        <label className="control-label">{label} API key<input aria-label={`${label} API key`} type="password" autoComplete="off" value={key} onChange={e=>setKey(e.target.value)} placeholder={profile?.configured?'Enter a key to replace the saved key':'Paste your provider API key'}/></label>
        <label className="control-label">Model<input aria-label={`${label} model`} value={model} disabled={name==='cloudflare'||option.capability==='video'} onChange={e=>setModel(e.target.value)}/></label>
        {(name==='elevenlabs'||name==='cloudflare')&&<label className="control-label">{name==='cloudflare'?'Cloudflare account ID':'ElevenLabs API URL'}<input aria-label={`${label} connection`} value={url} onChange={e=>setUrl(e.target.value)}/></label>}
        <p className="hint">Saving connects the settings only; it does not generate content or spend credits. Keys use the existing system credential store.</p>
        <button className="btn primary" type="submit" disabled={busy||!key.trim()}>{busy?'Saving…':`Save ${label} provider`}</button>
      </fieldset>
      {message&&<p role="status">{message}</p>}
    </form>
  </details>;
}
