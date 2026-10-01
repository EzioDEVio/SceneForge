// Local engine helpers: check/repair local Whisper, and start the Docker voice engines
// (Chatterbox, Kokoro) from inside the app instead of a separate .bat file.
import React from 'react';
import {api} from './api';

type Check = {name: string; ok: boolean; detail: string};
export function WhisperCheck() {
  const [report, setReport] = React.useState<{ok: boolean; model_dir: string; checks: Check[]} | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [note, setNote] = React.useState('');
  async function run() {
    setBusy(true); setNote('');
    try {setReport(await api.whisperCheck());} catch (e: any) {setNote(e.message || String(e));} finally {setBusy(false);}
  }
  async function reset() {
    setBusy(true);
    try {const r = await api.whisperReset(); setNote(r.message); setReport(await api.whisperCheck());} catch (e: any) {setNote(e.message || String(e));} finally {setBusy(false);}
  }
  return <div className="local-check" aria-label="Local captions check">
    <div className="button-row"><button className="text-btn" disabled={busy} onClick={() => void run()}>{busy ? 'Checking…' : 'Check local captions'}</button>
      {report && <button className="text-btn" disabled={busy} onClick={() => void reset()}>Re-download the Whisper model</button>}</div>
    {report && <ul className="local-check-list">{report.checks.map(c => <li key={c.name} className={c.ok ? 'ok' : 'bad'}><b>{c.ok ? '✓' : '✗'} {c.name}</b> <span>{c.detail}</span></li>)}</ul>}
    {note && <p className="hint" role="status">{note}</p>}
  </div>;
}

type EngineStatus = {engine: string; reachable: boolean; state: string; docker: string; message: string; log: string; services_bundled: boolean};
export function LocalEngineStarter({engine, label, onReady}: {engine: 'chatterbox' | 'kokoro'; label: string; onReady?: () => void}) {
  const [status, setStatus] = React.useState<EngineStatus | null>(null);
  const [error, setError] = React.useState('');
  const [showLog, setShowLog] = React.useState(false);
  const timer = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const readyCalled = React.useRef(false);
  async function refresh(poll = false) {
    try {
      const s = await api.localEngineStatus(engine); setStatus(s); setError('');
      if (s.reachable && !readyCalled.current) {readyCalled.current = true; onReady?.();}
      if (poll && !s.reachable && (s.state === 'starting' || s.state === 'started')) timer.current = setTimeout(() => void refresh(true), 4000);
    } catch (e: any) {setError(e.message || String(e));}
  }
  React.useEffect(() => () => {if (timer.current) clearTimeout(timer.current);}, []);
  async function start() {
    setError(''); readyCalled.current = false;
    try {await api.startLocalEngine(engine); await refresh(true);} catch (e: any) {setError(e.message || String(e)); void refresh();}
  }
  const text = !status ? '' : status.reachable ? `${label} is running.` : status.state === 'starting' ? `Starting ${label}… The first start downloads the engine and can take 10–30 minutes.` : status.state === 'started' ? `${label} container started; waiting for it to answer…` : status.state === 'failed' ? `${label} failed to start. Open the log below.` : status.docker !== 'ready' ? status.message : `${label} is not running.`;
  return <div className="engine-starter" aria-label={`${label} engine`}>
    <div className="button-row"><button className="btn" disabled={status?.state === 'starting' || !!status?.reachable} onClick={() => void start()}>Start {label}</button><button className="text-btn" onClick={() => void refresh()}>Check {label}</button>{status?.log && <button className="text-btn" onClick={() => setShowLog(v => !v)}>{showLog ? 'Hide' : 'Show'} log</button>}</div>
    {(text || error) && <p className="hint" role="status">{error || text}</p>}
    {showLog && status?.log && <pre className="engine-log">{status.log}</pre>}
  </div>;
}
