import React from 'react';
import {Cloud, Download, Loader2, Mic, Play, Sparkles, Waves} from 'lucide-react';
import type {ProviderProfile} from './api';

type Kokoro = {installed: boolean; state: string; done: number; total: number; error: string; download_mb: number};
type Chatter = {reachable: boolean; state: string; docker: string; message: string};
async function getJson(url: string, init?: RequestInit) {
  const r = await fetch(url, init); const data = await r.json().catch(() => ({}));
  if (!r.ok) throw Error(data.detail || 'Request failed'); return data;
}
const openEngines = (section: string) => window.dispatchEvent(new CustomEvent('sceneforge-open-ai-engines', {detail: section}));

/** Voice engines as cards (0.9.4-beta.3): nothing here needs Docker. */
export function VoiceEngines({busy, providers, onUse, onSelectProvider}: {busy: boolean; providers: ProviderProfile[];
  onUse: (engine: 'kokoro_builtin' | 'chatterbox' | 'voicebox') => void; onSelectProvider: (id: string) => void}) {
  const [kokoro, setKokoro] = React.useState<Kokoro | null>(null);
  const [chatter, setChatter] = React.useState<Chatter | null>(null);
  const [voicebox, setVoicebox] = React.useState(false);
  const [note, setNote] = React.useState('');
  const refresh = React.useCallback(async () => {
    const [k, c, v] = await Promise.allSettled([getJson('/api/local-speech/kokoro_builtin/status'), getJson('/api/local-speech/chatterbox/status'), getJson('/api/local-speech/voicebox/status')]);
    if (k.status === 'fulfilled') setKokoro(k.value); if (c.status === 'fulfilled') setChatter(c.value); if (v.status === 'fulfilled') setVoicebox(!!v.value.running);
  }, []);
  React.useEffect(() => {void refresh();}, [refresh]);
  const downloading = kokoro?.state === 'downloading' && !kokoro.installed;
  const starting = !chatter?.reachable && (chatter?.state === 'starting' || chatter?.state === 'started');
  React.useEffect(() => {if (!downloading && !starting) return; const t = setInterval(() => void refresh(), 1500); return () => clearInterval(t);}, [downloading, starting, refresh]);
  // Select Kokoro by itself once a download started here finishes.
  const fetched = React.useRef(false);
  React.useEffect(() => {if (downloading) fetched.current = true; else if (fetched.current && kokoro?.installed) {fetched.current = false; onUse('kokoro_builtin');}}, [downloading, kokoro?.installed]);
  async function downloadKokoro() {setNote(''); try {setKokoro(await getJson('/api/local-speech/kokoro_builtin/download', {method: 'POST'}));} catch (e: any) {setNote(e.message);}}
  async function startChatterbox() {setNote(''); try {await getJson('/api/local-speech/chatterbox/start', {method: 'POST'}); await refresh();} catch (e: any) {setNote(e.message);}}
  const gemini = providers.find(p => p.name === 'gemini_tts' && p.configured);
  const chatterInstalled = !!chatter && (chatter.reachable || chatter.docker === 'ready');
  const pct = kokoro && kokoro.total ? Math.round(kokoro.done / kokoro.total * 100) : 0;
  return <section className="voice-engines" aria-label="Voice engines">
    <h3>Voices</h3>
    <ul className="voice-engine-list">
      <li className={`voice-engine ${kokoro?.installed ? 'ready' : ''}`} aria-label="Kokoro">
        <span className="voice-engine-icon" aria-hidden><Sparkles size={17}/></span>
        <span className="voice-engine-text"><b>Kokoro <em>built in</em></b><small>English, Spanish, French, Hindi, Italian, Portuguese · works offline</small>
          {downloading && <span className="voice-engine-progress"><progress max={100} value={pct} aria-label="Kokoro download"/> {pct}%</span>}
          {kokoro?.error && <small className="form-error" role="alert">{kokoro.error}</small>}</span>
        {kokoro?.installed
          ? <button className="btn btn-primary" disabled={busy} onClick={() => onUse('kokoro_builtin')}>Use Kokoro</button>
          : <button className="btn" disabled={busy || downloading} onClick={() => void downloadKokoro()}>{downloading ? <Loader2 size={14} className="spin" aria-hidden/> : <Download size={14} aria-hidden/>} {downloading ? 'Downloading…' : `Download voices (${kokoro?.download_mb ?? 120} MB)`}</button>}
      </li>
      <li className={`voice-engine ${chatter?.reachable ? 'ready' : ''}`} aria-label="Chatterbox">
        <span className="voice-engine-icon" aria-hidden><Mic size={17}/></span>
        <span className="voice-engine-text"><b>Chatterbox</b><small>Arabic and 22 more languages · natural, expressive · runs on this computer, no Docker</small>
          {starting && <small role="status">Starting… the first start loads the voice model and can take a few minutes.</small>}</span>
        {chatter?.reachable
          ? <button className="btn btn-primary" disabled={busy} onClick={() => onUse('chatterbox')}>Use Chatterbox</button>
          : chatterInstalled
            ? <button className="btn" disabled={busy || starting} onClick={() => void startChatterbox()}><Play size={14} aria-hidden/> {starting ? 'Starting…' : 'Start Chatterbox'}</button>
            : <button className="btn" disabled={busy} onClick={() => openEngines('sd')}><Download size={14} aria-hidden/> Install (about 3 GB)</button>}
      </li>
      <li className={`voice-engine ${gemini ? 'ready' : ''}`} aria-label="Gemini voices">
        <span className="voice-engine-icon" aria-hidden><Cloud size={17}/></span>
        <span className="voice-engine-text"><b>Gemini voices <em>cloud</em></b><small>100+ languages including Arabic · free Google AI Studio key · needs internet</small></span>
        {gemini
          ? <button className="btn btn-primary" disabled={busy} onClick={() => onSelectProvider(gemini.id)}>Use Gemini voices</button>
          : <button className="btn" disabled={busy} onClick={() => openEngines('cloud')}>Add free key</button>}
      </li>
      <li className={`voice-engine ${voicebox ? 'ready' : ''}`} aria-label="Voicebox">
        <span className="voice-engine-icon" aria-hidden><Waves size={17}/></span>
        <span className="voice-engine-text"><b>Voicebox <em>optional app</em></b><small>{voicebox ? 'Running on this computer · uses your Voicebox voice profiles and clones' : 'If you use the free Voicebox app (voicebox.sh), open it and connect here'}</small></span>
        <button className="btn" disabled={busy} onClick={() => voicebox ? onUse('voicebox') : void refresh()}>{voicebox ? 'Use Voicebox' : 'Check again'}</button>
      </li>
    </ul>
    {note && <p className="form-error" role="alert">{note}</p>}
  </section>;
}
