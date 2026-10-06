import {ScriptStoryboard} from './ScriptStoryboard';
import {AutoCutSequence} from "./AutoCutSequence";
import {StorySceneSetup} from './StorySceneSetup';
import {DEFAULT_SCENE_SETUP,setupImportedScenes,validateSceneSetup,visualPrompt,type SceneSetupOptions} from './scriptSceneSetup';
import { useEffect, useState, useRef } from 'react';
import { api, req, type Project, type Scene, type Asset, type ProviderProfile, type VoiceOption } from './api';
import { sceneDuration } from './duration';
import { askConfirm } from './dialogs';
type Template = {
    id: string;
    name: string;
    scenes: number;
    aspect: string;
};
type CutPlan = {
    preview_token: string;
    video_mode?:string;
    times?: number[];
    cuts_ms: number[];
    duration_ms: number;
    revision: number;
    note: string;
    shots: any[];
};
export type StoryTab = 'Script → Scenes' | 'AutoCut' | 'Stabilize video' | 'Project templates';
export function StoryTools({ project, scene, initialTab, onClose, onRecord, onOpen, disabled,onScenesAdded }:  {
    project?: Project;
    scene?: Scene;
    initialTab: StoryTab;
    onClose: () => void;
    onRecord: (label: string, undo: () => Promise<unknown>, redo: () => Promise<unknown>) => Promise<boolean>;
    onOpen: (id: string) => Promise<void>;
    disabled: boolean;
    onScenesAdded?:(scenes:Scene[],message:string)=>void;
}) {
    const [tab, setTab] = useState(initialTab), [text, setText] = useState(''), [mode, setMode] = useState('paragraphs'), [preview, setPreview] = useState<any | null>(null), [templates, setTemplates] = useState<Template[]>([]), [name, setName] = useState(''), [status, setStatus] = useState(''), [pending, setPending] = useState(false), [cut, setCut] = useState<CutPlan | null>(null), [every, setEvery] = useState(1), [source, setSource] = useState(() => {const markers=project?.finishing_json?.timeline?.markers||[];return markers.some(m=>m.id.startsWith('beat-'))?'markers':markers.length?'timeline':project?.finishing_json?.music?'music':project?.finishing_json?.audio_clips?.[0]?.id||'timeline';}), [strength, setStrength] = useState((scene?.look_json as any)?.stabilize?.strength || 50);
    const [prepare,setPrepare]=useState(false),[setup,setSetup]=useState<SceneSetupOptions>(structuredClone(DEFAULT_SCENE_SETUP)),[assets,setAssets]=useState<Asset[]>([]),[providers,setProviders]=useState<ProviderProfile[]>([]),[voices,setVoices]=useState<VoiceOption[]>([]),[whisperReady,setWhisperReady]=useState(false);
    const stopSetup=useRef(false);
    const [videoMode,setVideoMode]=useState('repeat');
    let readiness='';
    if(prepare&&preview?.scenes){try{validateSceneSetup(setup,preview.scenes,providers,assets);}catch(e:any){readiness=e.message;}}

    useEffect(()=>{let live=true;if(project){void api.listAssets(project.id).then(v=>live&&setAssets(v)).catch(()=>{});void api.listProviders().then(v=>live&&setProviders(v)).catch(()=>{});void api.whisperCheck().then(v=>live&&setWhisperReady(v.ok&&v.checks.some(c=>c.name==='Model downloaded'&&c.ok))).catch(()=>{});}return()=>{live=false;};},[project?.id]);
    async function chooseEngine(id:string){setSetup(v=>({...v,voiceEngine:id,voice:'',paidNarrationConfirmed:false}));setVoices([]);if(['none','diagnostic'].includes(id))return;await run(async()=>{const result=await api.providerVoices(id);const list=result.voices.map(v=>typeof v==='string'?{id:v,name:v}:v);setVoices(list);setSetup(v=>({...v,voice:list[0]?.id||''}));});}
    const blocked = disabled || pending;
    const dialogRef = useRef<HTMLElement>(null);
    useEffect(() => { const previous = document.activeElement as HTMLElement | null; dialogRef.current?.querySelector<HTMLButtonElement>('button')?.focus(); return () => previous?.focus(); }, []);
    async function run(fn: () => Promise<void>) { setPending(true); setStatus(''); try {
        await fn();
    }
    catch (e: any) {
        setStatus(e.message || String(e));
    }
    finally {
        setPending(false);
    } }
    async function loadTemplates() { setTemplates((await req<{
        templates: Template[];
    }>('/api/project-templates')).templates); }
    useEffect(() => { void run(loadTemplates); }, []);
    useEffect(() => {
        const key = (e: KeyboardEvent) => {
            if (e.key === 'Escape' && !blocked) {
                e.preventDefault();
                onClose();
            }
            if (e.key === 'Tab' && !document.querySelector('dialog[open]')) {
                const nodes = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),summary') || []).filter(n => n.getClientRects().length);
                const first = nodes[0], last = nodes[nodes.length - 1];
                if (e.shiftKey && (document.activeElement === first || !dialogRef.current?.contains(document.activeElement))) {
                    e.preventDefault();
                    last?.focus();
                }
                else if (!e.shiftKey && (document.activeElement === last || !dialogRef.current?.contains(document.activeElement))) {
                    e.preventDefault();
                    first?.focus();
                }
            }
        };
        window.addEventListener('keydown', key);
        return () => window.removeEventListener('keydown', key);
    }, [blocked, onClose]);
    const allMarkers = [...(project?.finishing_json?.timeline?.markers || [])].map(m => {
        const clip = m.clip_id ? project?.finishing_json?.audio_clips?.find(c => c.id === m.clip_id) : undefined;
        return {...m,time_ms:clip && m.offset_ms !== undefined ? clip.start_ms + m.offset_ms : m.time_ms};
    }).sort((a,b)=>a.time_ms-b.time_ms);
    const beats = allMarkers.filter(m => m.id.startsWith('beat-'));
    const manualMarkers = allMarkers.filter(m => !m.id.startsWith('beat-'));
    const noMarkers = (source === 'timeline' && !manualMarkers.length) || (source === 'markers' && !beats.length);
    const locked = !!project?.finishing_json?.timeline?.tracks.V1?.locked;
    async function applyScript() {
        if (!project || !preview?.scenes.length)
            return;
        const selectedSetup=structuredClone(setup),useSetup=prepare;
        if(useSetup)validateSceneSetup(selectedSetup,preview.scenes,providers,assets);
        let added: Scene[] = [],notes:string[]=[];
        const scenes=structuredClone(preview.scenes);stopSetup.current=false;
        const ok=await onRecord('Script → Scenes',async()=>{for(const s of [...added].reverse())await api.deleteScene(s.id);},async()=>{
            if(added.length){for(const s of added)await api.restoreScene(s.id,s);}
            else{
                added=await api.importApply(project.id,scenes,false);
                if(useSetup){
                    try{const result=await setupImportedScenes(added.map((s,i)=>({...s,picture_prompt:scenes[i].picture_prompt||visualPrompt(s)})),selectedSetup,assets,setStatus,()=>stopSetup.current);added=result.scenes;notes=result.notes;}
                    catch(e:any){notes.push(`Setup stopped: ${e.message||'Step failed'}. Imported scenes are kept.`);for(let i=0;i<added.length;i++){try{added[i]=await api.getScene(added[i].id);}catch{/* Retain the imported snapshot if the server is unreachable. */}}}
                }
            }
        });
        if(ok){const message=`${added.length} scenes added${useSetup?' with your selected setup':''}. Undo removes this batch; Redo restores it without generating again.${notes.length?' '+notes.join(' | '):useSetup?' Review the result before exporting.':' Add pictures and generate narration when ready.'}`;setPreview(null);setStatus(message);if(onScenesAdded){onScenesAdded(added,message);onClose();}}
        else setStatus('Could not add scenes. See the editor error and retry.');
    }
    async function previewCut() {
        if (!project || !scene)
            return;
        let times: number[];
        if (source === 'markers' || source === 'timeline')
            times = (source === 'timeline' ? manualMarkers : beats).filter((_, i) => i % every === 0).map(m => m.time_ms);
        else
            times = (await api.beatMarkers(project.id, { every, ...(source === 'music' ? {} : { clip_id: source }) })).markers.map(m => m.time_ms);
        const p = await req<CutPlan>(`/api/scenes/${scene.id}/autocut/preview`, { method: 'POST', body: JSON.stringify({ times_ms: times, video_mode:videoMode }) });
        setCut({ ...p, times });
    }
    async function applyCut() {
        if (!scene || !cut)
            return;
        const before = structuredClone(scene);
        let after: Scene | null = null;
        const plan = cut;
        const ok = await onRecord('AutoCut to beats', () => api.restoreScene(before.id, before), async () => { after = after ? await api.restoreScene(after.id, after) : await req<Scene>(`/api/scenes/${scene.id}/autocut`, { method: 'POST', body: JSON.stringify({ times_ms: plan.times, revision: plan.revision, preview_token: plan.preview_token, video_mode:plan.video_mode }) }); });
        if (ok) {
            setCut(null);
            setStatus('AutoCut applied. Render the scene to play the result. Undo restores the original picture sequence.');
        }
        else
            setStatus('AutoCut could not be applied. Preview again if the scene changed.');
    }
    return <div className="story-backdrop"><section ref={dialogRef} role="dialog" aria-modal="true" aria-label="Story tools" className="story-tools"><header><h2>Story tools</h2><button className="btn" disabled={blocked} onClick={onClose} aria-label="Close story tools">Close</button></header><nav aria-label="Story tool sections">{(['Script → Scenes', 'AutoCut', 'Stabilize video', 'Project templates'] as StoryTab[]).map(t => <button className="btn" key={t} aria-pressed={tab === t} disabled={blocked || (!project && t !== 'Project templates')} onClick={() => { setTab(t); setStatus(''); }}>{t}</button>)}</nav>
 {tab === 'Script → Scenes' && <section><p className="story-readiness" role="status">{readiness||(!prepare?"Ready for text-only import: titles, narration text and caption text.":"Selected setup will prepare your chosen media, narration, captions and motion.")}</p><p className="hint">Plain import adds titles, editable narration text and caption text. Optional setup adds only the steps you select. New scenes open for editing; existing scenes remain.</p><h3>Turn your script into scenes</h3><p className="hint">Paste text or open a TXT/Markdown file. Preview first, then append editable scenes to this project. Choose optional scene setup below to prepare pictures, narration, captions and motion.</p><label className="control-label">Open script file<input type="file" accept=".txt,.md,text/plain,text/markdown" disabled={blocked} onChange={e => { const file = e.target.files?.[0]; if (file)
        void run(async () => { if (file.size > 800000)
            throw Error('Choose a script smaller than 800 KB.'); setText(await file.text()); setPreview(null); }); }}/></label><label className="control-label">Script<textarea aria-label="Script to split" disabled={blocked} value={text} onChange={e => { setText(e.target.value); setPreview(null); }}/></label><label className="control-label">Split at<select aria-label="Script split mode" value={mode} disabled={blocked} onChange={e => { setMode(e.target.value); setPreview(null); }}><option value="paragraphs">Blank lines — one scene per paragraph</option><option value="headings">Scene headings — English or Arabic</option></select></label><p className="hint">Headings supports “Scene 1” / “المشهد ١” and Narration, Visual, On-screen Text fields. Citation numbers stay in the original text.</p><button className="btn" disabled={blocked || !text.trim()} onClick={() => void run(async () => { setPreview(await req(`/api/projects/${project!.id}/import`, { method: 'POST', body: JSON.stringify({ text, split_mode: mode }) })); })}>Preview scenes</button><label className="switch-label story-prepare-toggle"><input type="checkbox" aria-label="Prepare imported scenes" checked={prepare} disabled={blocked} onChange={e=>setPrepare(e.target.checked)}/> Prepare pictures, narration, captions & motion</label>{prepare&&<><button className="btn" disabled={blocked} onClick={()=>void run(async()=>{setProviders(await api.listProviders());setStatus("Narration engines refreshed. Configure missing engines in Settings → Providers.");})}>Refresh narration engines</button><StorySceneSetup options={setup} onChange={setSetup} assets={assets} providers={providers} voices={voices} blocked={blocked} whisperReady={whisperReady} onEngine={id=>void chooseEngine(id)}/></>}{preview && <div className="story-preview" aria-label="Script scene preview">{project&&<ScriptStoryboard scenes={preview.scenes} options={setup} prepare={prepare} assets={assets} project={project}/>}{preview.warnings.map((w: string, i: number) => <p key={i}>{w}</p>)}{preview.scenes.map((s: any, i: number) => <article key={i}><strong>{s.title}</strong><label>Narration<textarea aria-label={`Preview scene ${i + 1} narration`} value={s.spoken_text} disabled={blocked} onChange={e => setPreview({ ...preview, scenes: preview.scenes.map((v: any, j: number) => j === i ? { ...v, spoken_text: e.target.value, subtitle_text: e.target.value.replace(/\[\d+(?:,\s*\d+)*\]/g, '') } : v) })}/></label>{prepare&&setup.pictures==='local'&&<label>Image prompt<textarea aria-label={`Preview scene ${i+1} image prompt`} value={s.picture_prompt??visualPrompt(s)} disabled={blocked} onChange={e=>setPreview({...preview,scenes:preview.scenes.map((v:any,j:number)=>j===i?{...v,picture_prompt:e.target.value}:v)})}/></label>}<details><summary>Original text and notes</summary><p>{s.original_text}</p>{s.warnings.map((w: string, k: number) => <p key={k}>{w}</p>)}</details></article>)}<button className="btn btn-primary" disabled={blocked || !preview.scenes.length || !!readiness} onClick={() => void run(applyScript)}>Add {preview.scenes.length} scenes</button></div>}</section>}
 {tab === 'AutoCut' && <section>{cut&&<AutoCutSequence plan={cut}/>} <h3>{source === 'timeline' ? 'Cut pictures at your markers' : 'Cut pictures to the beat'}</h3><p className="hint">Changes the picture sequence in “{scene?.title}” while keeping its length, narration, captions and overlays. Existing images/videos repeat in order.</p><label className="control-label">Beat source<select aria-label="AutoCut beat source" value={source} disabled={blocked} onChange={e => { setSource(e.target.value); setCut(null); }}><option value="timeline" disabled={!manualMarkers.length}>Timeline markers ({manualMarkers.length})</option><option value="markers" disabled={!beats.length}>Existing timeline beat markers ({beats.length})</option>{project?.finishing_json?.music && <option value="music">Detect from music bed</option>}{project?.finishing_json?.audio_clips?.map(c => <option key={c.id} value={c.id}>Detect from {c.name}</option>)}</select></label><label className="control-label">Video cutting<select aria-label="AutoCut video cutting" value={videoMode} disabled={blocked} onChange={e=>{setVideoMode(e.target.value);setCut(null);}}><option value="repeat">Repeat pictures / video excerpts in order</option><option value="continuous">Continue through one video</option></select></label><p className="hint">Continue through one video keeps picture and clip sound moving forward at every cut. It needs one selected video long enough to cover the scene.</p><label className="control-label">Cut frequency<select aria-label="AutoCut frequency" value={every} disabled={blocked} onChange={e => { setEvery(Number(e.target.value)); setCut(null); }}>{[1, 2, 4].map(n => <option key={n} value={n}>Every {n === 1 ? (source === 'timeline' ? 'marker' : 'beat') : `${n} ${source === 'timeline' ? 'markers' : 'beats'}`} </option>)}</select></label><p className="hint">Use Marker on the timeline to place your own cuts, or use music and ♪ Beats for automatic beat detection. Images and videos are the pictures being cut; music/audio provides detected beats. Preview lists cut positions before changing anything. Unlock Picture to edit it.</p>{locked && <p role="alert">Picture track is locked.</p>}<button className="btn" disabled={blocked || !scene || locked || noMarkers} onClick={() => void run(previewCut)}>Preview AutoCut</button>{cut && <div className="story-preview" aria-label="AutoCut preview"><p>{cut.shots.length} picture clips · {(cut.duration_ms / 1000).toFixed(2)} seconds</p><p>Cut at: {cut.cuts_ms.map(t => (t / 1000).toFixed(2) + 's').join(', ')}</p><p className="hint">{cut.note}</p><button className="btn btn-primary" disabled={blocked || locked} onClick={() => void run(applyCut)}>Apply AutoCut</button></div>}</section>}
 {tab === 'Stabilize video' && <section><h3>Reduce camera shake</h3><p className="hint">Stabilizes video clips in “{scene?.title}” using local processing. Images stay unchanged. Render the scene to preview the result; exported video uses the same processing. Mirrored edges fill movement gaps.</p><label className="control-label">Movement range<input aria-label="Stabilization strength" type="range" min="1" max="100" value={strength} disabled={blocked} onChange={e => setStrength(Number(e.target.value))}/><span>{strength} / 100 · larger values search for larger movements</span></label><p className="hint">Start with 50. This corrects small handheld movements; strong blur or fast pans may still need a steadier source clip.</p><div className="button-row">{[true, false].map(enabled => <button key={String(enabled)} className="btn" disabled={blocked || !scene || locked || (enabled && !scene.shots.some(s => s.asset?.type === 'video'))} onClick={() => void run(async () => { const before = (scene!.look_json as any)?.stabilize || null; const ok = await onRecord(enabled ? 'video stabilization' : 'remove stabilization', () => api.updateScene(scene!.id, { look: { stabilize: before } }), () => api.updateScene(scene!.id, { look: { stabilize: enabled ? { strength } : null } })); if (ok)
        setStatus('Saved. Render the scene to preview; Undo restores the previous setting.'); })}>{enabled ? 'Apply stabilization' : 'Turn stabilization off'}</button>)}</div>{scene && <p className="hint">Scene length: {(sceneDuration(scene) / 1000).toFixed(2)} seconds. Stabilization keeps timing and audio in sync.</p>}</section>}
 {tab === 'Project templates' && <section><h3>Reuse a project setup</h3><p className="hint">Save scenes, text, effects, timing and media references as a reusable template. Each use creates a separate project. Media stays on this computer; templates survive deleting the original project.</p><label className="control-label">{project ? 'Template / new project name' : 'New project name'}<input aria-label="Template name" value={name} maxLength={80} disabled={blocked} onChange={e => setName(e.target.value)}/></label>{project && <button className="btn" disabled={blocked || !name.trim()} onClick={() => void run(async () => { await req('/api/project-templates', { method: 'POST', body: JSON.stringify({ project_id: project.id, name }) }); await loadTemplates(); setStatus('Template saved. It is available from the Projects page.'); })}>Save current project as template</button>}<div className="story-preview">{!templates.length && <p>No templates yet. Open a project and save its setup here.</p>}{templates.map(t => <article key={t.id}><strong>{t.name}</strong><span>{t.aspect} · {t.scenes} scenes</span><button className="btn" disabled={blocked} onClick={() => void run(async () => { const p = await req<Project>(`/api/project-templates/${t.id}/create`, { method: 'POST', body: JSON.stringify({ title: name.trim() || `${t.name} (new project)` }) }); await onOpen(p.id); onClose(); })}>Use {t.name}</button><button className="text-btn danger" disabled={blocked} onClick={() => void run(async () => { if (await askConfirm(`Delete template “${t.name}”? Projects already made from it stay available.`)) {
        await req(`/api/project-templates/${t.id}`, { method: 'DELETE' });
        await loadTemplates();
    } })}>Delete template {t.name}</button></article>)}</div></section>}
 {status && <p role="status" className="story-status">{status}</p>}{pending && <p role="status">Working…</p>}{pending&&tab==='Script → Scenes'&&prepare&&<button className="btn" onClick={()=>{stopSetup.current=true;setStatus('Stopping after the current step…');}}>Stop scene setup</button>}
 </section></div>;
}
