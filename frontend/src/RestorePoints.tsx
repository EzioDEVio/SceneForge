// Restore points (0.9.0): automatic and manual project snapshots. Restoring opens a COPY of the
// project as it was, so the current project is never overwritten.
import React, {useCallback, useEffect, useState} from 'react';
import {History, RotateCcw, Save, Trash2} from 'lucide-react';
import {Modal} from './InfoPanels';
import {askConfirm} from './dialogs';
import {api, Project, Snapshot} from './api';

export const AUTO_SNAPSHOT_MS = 5 * 60 * 1000;

function when(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const mins = Math.round((Date.now() - d.getTime()) / 60000);
  const rel = mins < 1 ? 'just now' : mins < 60 ? `${mins} min ago` : mins < 60 * 24 ? `${Math.round(mins / 60)} h ago` : `${Math.round(mins / 1440)} days ago`;
  return `${d.toLocaleString(undefined, {month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'})} · ${rel}`;
}

/** Saves an automatic restore point now and every few minutes while a project is open (only when it changed). */
export function useAutoSnapshots(projectId: string | null | undefined, paused: boolean) {
  useEffect(() => {
    if (!projectId) return;
    const save = () => {if (!paused) void api.saveSnapshot(projectId, {auto: true}).catch(() => {});};
    const first = setTimeout(save, 20000);   // after the project finished loading
    const timer = setInterval(save, AUTO_SNAPSHOT_MS);
    return () => {clearTimeout(first); clearInterval(timer);};
  }, [projectId, paused]);
}

export function RestorePoints({project, onClose, onOpen}: {project: Project; onClose: () => void; onOpen: (id: string) => void}) {
  const [items, setItems] = useState<Snapshot[] | null>(null);
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [label, setLabel] = useState('');
  const load = useCallback(async () => {
    try {setItems((await api.listSnapshots(project.id)).snapshots); setError('');} catch (e: any) {setError(e?.message || String(e));}
  }, [project.id]);
  useEffect(() => {void load();}, [load]);

  async function saveNow() {
    setBusy('save'); setMessage(''); setError('');
    try {const r = await api.saveSnapshot(project.id, {label: label.trim()}); setMessage(r.saved ? 'Restore point saved.' : (r.reason || 'Nothing changed.')); setLabel(''); await load();}
    catch (e: any) {setError(e?.message || String(e));} finally {setBusy('');}
  }
  async function restore(s: Snapshot) {
    if (!(await askConfirm(`Open a copy of “${project.title}” as it was ${when(s.created_at)}? Your current project stays exactly as it is.`))) return;
    setBusy(s.id); setError('');
    try {const copy = await api.restoreSnapshot(project.id, s.id); onOpen(copy.id);}
    catch (e: any) {setError(e?.message || String(e)); setBusy('');}
  }
  async function remove(s: Snapshot) {
    if (!(await askConfirm(`Delete the restore point from ${when(s.created_at)}?`))) return;
    setBusy(s.id);
    try {await api.deleteSnapshot(project.id, s.id); await load();} catch (e: any) {setError(e?.message || String(e));} finally {setBusy('');}
  }

  return <Modal title="Restore points" icon={<History size={18}/>} onClose={onClose} wide>
    <p className="info-lead">SceneForge saves a restore point of this project every few minutes while you edit (only when something changed), and keeps the last 20. Restoring opens a <strong>copy</strong> of the project as it was then, so nothing you have now is lost.</p>
    <div className="restore-save-row">
      <input aria-label="Restore point name" placeholder="Name (optional), e.g. Before recolouring" maxLength={80} value={label} onChange={e => setLabel(e.target.value)}/>
      <button className="btn btn-primary" disabled={!!busy} onClick={() => void saveNow()}><Save size={14}/> Save restore point now</button>
    </div>
    {message && <p className="hint" role="status">{message}</p>}
    {error && <p className="error-box" role="alert">{error}</p>}
    {!items ? <p className="hint">Loading…</p> : !items.length ? <p className="hint">No restore points yet. The first one is saved automatically a few seconds after you open a project.</p> :
      <ul className="restore-list">{items.map(s => <li key={s.id}>
        <div><strong>{s.label || (s.reason === 'auto' ? 'Automatic' : 'Saved by you')}</strong><span>{when(s.created_at)} · {s.scenes} scene{s.scenes === 1 ? '' : 's'}</span></div>
        <button className="btn" disabled={!!busy} aria-label={`Restore ${s.label || 'restore point'} from ${when(s.created_at)}`} onClick={() => void restore(s)}><RotateCcw size={13}/> Open this version</button>
        <button className="icon-reset" disabled={!!busy} aria-label={`Delete restore point from ${when(s.created_at)}`} onClick={() => void remove(s)}><Trash2 size={13}/></button>
      </li>)}</ul>}
  </Modal>;
}
