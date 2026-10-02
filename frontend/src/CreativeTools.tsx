// RC7 creative tools: AI subject cutout ("text behind subject", background removal) and
// textured text titles (procedural presets, a Media Pool image, or a generated texture).
import React from 'react';
import {Scissors, Type, Sparkles} from 'lucide-react';
import {api, Asset, ProviderProfile, Scene, SubjectVideoEstimate, SubjectVideoJob} from './api';

const PRESETS: [string, string][] = [['lava', 'Lava'], ['neon', 'Neon'], ['gold', 'Gold'], ['chrome', 'Chrome'], ['marble', 'Marble'],
  ['ice', 'Ice'], ['fire', 'Fire'], ['pixel', 'Pixel blocks'], ['galaxy', 'Galaxy']];
const FONTS = ['Anton', 'Bebas Neue', 'Poppins', 'Noto Sans', 'Pacifico', 'Lalezar', 'Tajawal', 'Noto Naskh Arabic'];

export function SubjectCutoutPanel({scene, disabled, onDone}: {scene: Scene; disabled: boolean; onDone: () => void | Promise<void>}) {
  const [model, setModel] = React.useState<'human' | 'isnet' | 'u2netp'>('isnet');
  const [shift, setShift] = React.useState(0);
  const [previewId, setPreviewId] = React.useState('');
  const [edge, setEdge] = React.useState<'soft' | 'crisp'>('soft');
  const [busy, setBusy] = React.useState(false);
  const [msg, setMsg] = React.useState('');
  const [status, setStatus] = React.useState<{models: {id: string; downloaded: boolean; approx_mb: number}[]} | null>(null);
  React.useEffect(() => {api.cutoutStatus().then(setStatus).catch(() => setStatus(null));}, []);
  const shot = scene.shots[0];
  const isImage = shot?.asset?.type === 'image';
  const hasSubject = (scene.overlays_json || []).some(o => (o as any).kind === 'subject');
  const needsDownload = status?.models.find(m => m.id === model && !m.downloaded);
  // Video: "text behind a moving subject" runs as a background job with frame progress.
  const isVideo = shot?.asset?.type === 'video';
  const [estimate, setEstimate] = React.useState<SubjectVideoEstimate | null>(null);
  const [vjob, setVjob] = React.useState<SubjectVideoJob | null>(null);
  const vjobId = React.useRef('');
  React.useEffect(() => {if (isVideo) setModel('u2netp');}, [isVideo, shot?.id]);
  React.useEffect(() => {
    if (!isVideo) {setEstimate(null); return;}
    let live = true;
    api.subjectVideoEstimate(scene.id, model).then(e => {if (live) setEstimate(e);}).catch(() => live && setEstimate(null));
    return () => {live = false;};
  }, [isVideo, scene.id, model, shot?.id, shot?.source_in_ms, shot?.source_out_ms, scene.revision]);
  React.useEffect(() => () => {vjobId.current = '';}, []);
  async function followVideoJob(jobId: string) {
    vjobId.current = jobId;
    while (vjobId.current === jobId) {
      let j: SubjectVideoJob;
      try {j = await api.subjectVideoJob(jobId);} catch (e: any) {setMsg(e.message || String(e)); break;}
      setVjob(j);
      if (j.status === 'succeeded') {
        setMsg(['Moving subject layer added above captions and titles. Render the scene to see text behind the subject.', ...(j.notes || [])].join(' '));
        await onDone(); break;
      }
      if (j.status === 'failed' || j.status === 'cancelled') {setMsg(j.status === 'cancelled' ? 'Cutout cancelled. Nothing was changed.' : (j.error || 'The cutout failed.')); break;}
      await new Promise(r => setTimeout(r, 700));
    }
    if (vjobId.current === jobId) vjobId.current = '';
    setVjob(null); setBusy(false);
  }
  React.useEffect(() => {
    if (estimate?.running_job_id && !vjobId.current) {setBusy(true); void followVideoJob(estimate.running_job_id);}
  }, [estimate?.running_job_id]);
  async function runVideo() {
    setBusy(true);
    setMsg(needsDownload ? `Downloading the background-removal model (~${needsDownload.approx_mb} MB, once)… then cutting out the moving subject.` : 'Cutting out the moving subject frame by frame…');
    try {
      const r = await api.subjectVideoLayer(scene.id, {model, edge, shift});
      if (r.status === 'done') {
        setMsg(['Moving subject layer added (reused the earlier cutout). Render the scene to see text behind the subject.', ...(r.notes || [])].join(' '));
        await onDone(); setBusy(false); return;
      }
      await followVideoJob(r.job_id!);
      setStatus(await api.cutoutStatus().catch(() => status));
    } catch (e: any) {setMsg(e.message || String(e)); setBusy(false);}
  }
  const fmtTime = (s: number) => s < 90 ? `~${Math.max(1, Math.round(s))} s` : `~${Math.round(s / 60)} min`;
  const videoLeft = vjob && vjob.ms_per_frame ? (vjob.frames_total - vjob.frames_done) * vjob.ms_per_frame / 1000 : null;
  async function run(kind: 'layer' | 'asset') {
    if (!shot) return;
    setBusy(true); setMsg(needsDownload ? `Downloading the background-removal model (~${needsDownload.approx_mb} MB, once)… then cutting out the subject.` : 'Cutting out the subject…');
    try {
      if (kind === 'layer') {
        const r = await api.subjectLayer(scene.id, {model, edge, shift});
        if ((r as any).cutout_asset?.id) setPreviewId((r as any).cutout_asset.id);
        setMsg(['Subject layer added above captions and titles. Render the scene to see text behind the subject.', ...(r.notes || [])].join(' '));
      } else {
        const a = await api.cutoutAsset(shot.asset_id, {model, edge, shift});
        setPreviewId(a.id);
        setMsg(`Saved “${a.original_filename}” (transparent PNG) to the Media Pool. Use it as a sticker or overlay.`);
      }
      await onDone();
      setStatus(await api.cutoutStatus().catch(() => status));
    } catch (e: any) {setMsg(e.message || String(e));} finally {setBusy(false);}
  }
  return <section className="creative-card" aria-label="Subject cutout">
    <header><Scissors size={15}/><strong>Subject cutout · AI beta</strong></header>
    <p className="hint">Removes the background on this computer with a local AI model. “Text behind subject” keeps captions and titles behind the person or object. Works on scenes with one still image or one video clip (up to 20 s, normal speed) and no camera movement.</p>
    <div className="acc-grid">
      <label className="control-label">Model<select aria-label="Cutout model" value={model} disabled={busy} onChange={e => setModel(e.target.value as any)}><option value="isnet">Best general · IS-Net (~170 MB)</option><option value="human">People (whole body) · U²-Net human (~176 MB)</option><option value="u2netp">Fast · U²-Net small (included)</option></select></label>
      <label className="control-label">Edges<select aria-label="Cutout edges" value={edge} disabled={busy} onChange={e => setEdge(e.target.value as any)}><option value="soft">Soft (hair, fur)</option><option value="crisp">Crisp (objects, products)</option></select></label>
    </div>
    <label className="control-label">Edge {shift > 0 ? `grow ${shift}px` : shift < 0 ? `shrink ${-shift}px (removes halos)` : 'as detected'}<input aria-label="Cutout edge shift" type="range" min={-10} max={10} value={shift} disabled={busy} onChange={e => setShift(Number(e.target.value))}/></label>
    {isVideo ? <>
      <div className="button-row">
        <button className="btn btn-primary" disabled={disabled || busy || !estimate?.ok} onClick={() => void runVideo()}>{hasSubject ? 'Update text behind moving subject' : 'Put text behind moving subject'}{estimate?.ok && !busy ? ` (${fmtTime(estimate.estimate_s || 0)})` : ''}</button>
        {vjob && <button className="btn" onClick={() => void api.cancelJob(vjob.job_id).catch(() => {})}>Cancel</button>}
      </div>
      {estimate?.ok && !busy && <p className="hint">{estimate.frames} frames ({estimate.seconds_of_video} s) at {Math.round(estimate.ms_per_frame || 0)} ms per frame{estimate.measured ? ' (measured on this computer)' : ' (estimate)'}.{model !== 'u2netp' ? ' This model is much slower on video; Fast · U²-Net small is recommended.' : ''}</p>}
      {estimate && !estimate.ok && <p className="hint">{estimate.reason}</p>}
      {vjob && <div className="cutout-progress"><progress aria-label="Cutout progress" max={vjob.frames_total || 1} value={vjob.frames_done}/><span>Frame {vjob.frames_done} of {vjob.frames_total}{videoLeft != null ? ` · ${fmtTime(videoLeft)} left` : ''}</span></div>}
    </> : <div className="button-row">
      <button className="btn btn-primary" disabled={disabled || busy || !isImage} onClick={() => void run('layer')}>{hasSubject ? 'Update text behind subject' : 'Put text behind subject'}</button>
      <button className="btn" disabled={disabled || busy || !isImage} onClick={() => void run('asset')}>Remove background → Media Pool</button>
    </div>}
    {!isImage && !isVideo && <p className="hint">Add a still image or a video to this scene to use subject cutout.</p>}
    {msg && <p className="info-status" role="status">{msg}</p>}
    {previewId && <figure className="cutout-preview"><img alt="Cutout result on a checkerboard" src={api.assetStreamUrl(previewId)}/><figcaption>Result: check the edges. For people try the People model; if a halo of background remains, shrink the edge 1–3 px.</figcaption></figure>}
  </section>;
}

export function TexturedTitlePanel({scene, disabled, onDone}: {scene: Scene; disabled: boolean; onDone: () => void | Promise<void>}) {
  const [text, setText] = React.useState('');
  const [source, setSource] = React.useState<'preset' | 'pool' | 'prompt'>('preset');
  const [preset, setPreset] = React.useState('lava');
  const [poolId, setPoolId] = React.useState('');
  const [prompt, setPrompt] = React.useState('');
  const [providerId, setProviderId] = React.useState('');
  const [font, setFont] = React.useState('Anton');
  const [size, setSize] = React.useState(160);
  const [glow, setGlow] = React.useState(30);
  const [outline, setOutline] = React.useState(0);
  const [images, setImages] = React.useState<Asset[]>([]);
  const [providers, setProviders] = React.useState<ProviderProfile[]>([]);
  const [busy, setBusy] = React.useState(false);
  const [msg, setMsg] = React.useState('');
  React.useEffect(() => {
    api.listAssets(scene.project_id).then(a => setImages(a.filter(x => x.type === 'image'))).catch(() => {});
    api.listProviders().then(p => setProviders(p.filter(x => x.capability === 'image'))).catch(() => {});
  }, [scene.project_id]);
  async function add() {
    setBusy(true); setMsg(source === 'prompt' ? 'Generating the texture with your image engine, then building the title…' : 'Building the title…');
    try {
      const texture = source === 'preset' ? {preset} : source === 'pool' ? {asset_id: poolId} : {prompt, provider_id: providerId || undefined};
      await api.texturedTitle(scene.id, {text, texture, font, font_size: size, glow, outline});
      setMsg('Textured title added as a sticker layer. Move, resize and animate it in Overlays; render to see it in the video.');
      await onDone();
    } catch (e: any) {setMsg(e.message || String(e));} finally {setBusy(false);}
  }
  const ready = text.trim() && (source === 'preset' || (source === 'pool' && poolId) || (source === 'prompt' && prompt.trim()));
  return <section className="creative-card" aria-label="Textured title">
    <header><Type size={15}/><strong>Textured title</strong></header>
    <p className="hint">Fills big title letters with a texture: a built-in pattern, an image from your Media Pool, or a texture generated from a prompt with your image engine (cloud engines may charge).</p>
    <label className="control-label">Title text<input aria-label="Textured title text" maxLength={80} value={text} onChange={e => setText(e.target.value)} placeholder="e.g. LAVA"/></label>
    <div className="acc-grid">
      <label className="control-label">Texture from<select aria-label="Texture source" value={source} onChange={e => setSource(e.target.value as any)}><option value="preset">Built-in pattern</option><option value="pool">Media Pool image</option><option value="prompt">Prompt (image engine)</option></select></label>
      {source === 'preset' && <label className="control-label">Pattern<select aria-label="Texture pattern" value={preset} onChange={e => setPreset(e.target.value)}>{PRESETS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>}
      {source === 'pool' && <label className="control-label">Image<select aria-label="Texture image" value={poolId} onChange={e => setPoolId(e.target.value)}><option value="">Choose an image…</option>{images.map(a => <option key={a.id} value={a.id}>{a.original_filename}</option>)}</select></label>}
      {source === 'prompt' && <label className="control-label">Image engine<select aria-label="Texture image engine" value={providerId} onChange={e => setProviderId(e.target.value)}><option value="">Default engine</option>{providers.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>}
      <label className="control-label">Font<select aria-label="Textured title font" value={font} onChange={e => setFont(e.target.value)}>{FONTS.map(f => <option key={f}>{f}</option>)}</select></label>
    </div>
    {source === 'prompt' && <label className="control-label">Texture prompt<input aria-label="Texture prompt" maxLength={400} value={prompt} onChange={e => setPrompt(e.target.value)} placeholder="e.g. glowing molten lava with dark crust"/></label>}
    <label className="control-label">Size · {size}px<input aria-label="Textured title size" type="range" min={48} max={320} step={8} value={size} onChange={e => setSize(Number(e.target.value))}/></label>
    <label className="control-label">Glow · {glow}<input aria-label="Textured title glow" type="range" min={0} max={100} value={glow} onChange={e => setGlow(Number(e.target.value))}/></label>
    <label className="control-label">Outline · {outline}px<input aria-label="Textured title outline" type="range" min={0} max={20} value={outline} onChange={e => setOutline(Number(e.target.value))}/></label>
    <button className="btn btn-primary" disabled={disabled || busy || !ready} onClick={() => void add()}><Sparkles size={14}/> {busy ? 'Working…' : 'Add textured title'}</button>
    {msg && <p className="info-status" role="status">{msg}</p>}
  </section>;
}

/** 0.9.1 "Video inside text": a colour card with the letters cut out, so the scene's own video or
 *  picture plays through the title (the classic documentary "1942" / place-name look).
 *  0.9.2: the title shrinks to fit the frame, the preview shows the real proportions, and an
 *  optional step puts the person or object in front of the card (AI subject cutout). */
export function VideoInTextPanel({scene, disabled, onDone}: {scene: Scene; disabled: boolean; onDone: () => void | Promise<void>}) {
  const [text, setText] = React.useState('');
  const [font, setFont] = React.useState('Anton');
  const [size, setSize] = React.useState(260);
  const [background, setBackground] = React.useState('#E10600');
  const [opacity, setOpacity] = React.useState(100);
  const [outline, setOutline] = React.useState(6);
  const [outlineColor, setOutlineColor] = React.useState('#FFFFFF');
  const [y, setY] = React.useState(55);
  const [subjectFront, setSubjectFront] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [msg, setMsg] = React.useState('');
  const [fitted, setFitted] = React.useState(false);
  const box = React.useRef<HTMLDivElement>(null);
  const label = React.useRef<HTMLSpanElement>(null);
  const hasMedia = scene.shots.length > 0;
  const shot = scene.shots.find(s => s.is_selected) || scene.shots[0];
  const isVideo = shot?.asset?.type === 'video';
  // Preview at the real proportions: letter size is px at 1080p, shrunk to fit 92% of the width (as the render does).
  React.useLayoutEffect(() => {
    let live = true;
    const fit = () => {
      const b = box.current, l = label.current;
      if (!live || !b || !l || !b.clientWidth) return;
      const base = size / 1080 * b.clientHeight;
      l.style.fontSize = `${base}px`;
      const room = b.clientWidth * 0.92;
      let px = base, w = l.getBoundingClientRect().width;
      setFitted(w > room);
      for (let i = 0; i < 4 && w > room; i++) {   // letter spacing does not scale, so settle in a few steps
        px = px * room / w; l.style.fontSize = `${px}px`; w = l.getBoundingClientRect().width;
      }
    };
    fit();
    document.fonts?.ready.then(fit).catch(() => {});   // the web font may arrive after the first measure
    return () => {live = false;};
  }, [size, text, font, outline]);
  async function putSubjectInFront() {
    if (!isVideo) {
      await api.subjectLayer(scene.id, {model: 'isnet', edge: 'soft', shift: 0});
      return 'The subject now stands in front of the title. Render the scene to see it.';
    }
    const r = await api.subjectVideoLayer(scene.id, {model: 'u2netp', edge: 'soft', shift: 0});
    if (r.status !== 'done' && r.job_id) {
      for (;;) {
        await new Promise(res => setTimeout(res, 800));
        const j = await api.subjectVideoJob(r.job_id);
        if (j.status === 'succeeded') break;
        if (j.status === 'failed' || j.status === 'cancelled') throw new Error(j.error || 'The subject cutout did not finish.');
        setMsg(`Cutting the subject out of the video: frame ${j.frames_done} of ${j.frames_total}…`);
      }
    }
    return 'The moving subject now stands in front of the title. Render the scene to see it.';
  }
  async function add() {
    setBusy(true); setMsg('Cutting the letters out of the colour card…');
    try {
      await api.knockoutTitle(scene.id, {text, font, font_size: size, background, opacity, outline, outline_color: outlineColor, y});
      let done = 'Added as a full-screen layer in Overlays. Your video plays inside the letters; render the scene to see it move. Tip: give the picture a slow zoom in Motion.';
      if (subjectFront) {
        setMsg('Title added. Now cutting out the subject so it stands in front…');
        try {done = await putSubjectInFront();}
        catch (e: any) {done = `Title added, but the subject could not be put in front: ${e.message || e}. You can try again under Subject cutout.`;}
      }
      setMsg(done);
      await onDone();
    } catch (e: any) {setMsg(e.message || String(e));} finally {setBusy(false);}
  }
  return <section className="creative-card" aria-label="Video inside text">
    <header><Type size={15}/><strong>Video inside text</strong></header>
    <p className="hint">Covers the screen with a solid colour and cuts your title out of it, so this scene's video or picture shows through the letters, like a documentary place or year title.</p>
    <div ref={box} className="ko-preview" style={{background, opacity: Math.max(.35, opacity / 100)}} aria-hidden="true">
      <span ref={label} style={{fontFamily: font === 'Bebas Neue' ? "'Bebas Neue'" : font, WebkitTextStroke: outline ? `${Math.max(1, outline / 4)}px ${outlineColor}` : undefined, top: `${y}%`}}>{text.trim() || 'NORWAY'}</span>
    </div>
    <label className="control-label">Title text<input aria-label="Video inside text title" maxLength={80} value={text} onChange={e => setText(e.target.value)} placeholder="e.g. 1942 or NORWAY"/></label>
    <div className="acc-grid">
      <label className="control-label">Font<select aria-label="Video inside text font" value={font} onChange={e => setFont(e.target.value)}>{FONTS.map(f => <option key={f}>{f}</option>)}</select></label>
      <label className="control-label">Card colour<input aria-label="Video inside text background colour" type="color" value={background} onChange={e => setBackground(e.target.value.toUpperCase())}/></label>
    </div>
    <label className="control-label">Letter size · {size}px{fitted ? ' (shrunk to fit the screen)' : ''}<input aria-label="Video inside text size" type="range" min={80} max={600} step={10} value={size} onChange={e => setSize(Number(e.target.value))}/></label>
    <label className="control-label">Up–down · {y}%<input aria-label="Video inside text position" type="range" min={10} max={90} value={y} onChange={e => setY(Number(e.target.value))}/></label>
    <label className="control-label">Outline · {outline}px<input aria-label="Video inside text outline" type="range" min={0} max={30} value={outline} onChange={e => setOutline(Number(e.target.value))}/></label>
    {outline > 0 && <label className="control-label">Outline colour<input aria-label="Video inside text outline colour" type="color" value={outlineColor} onChange={e => setOutlineColor(e.target.value.toUpperCase())}/></label>}
    <label className="control-label">Card opacity · {opacity}%<input aria-label="Video inside text card opacity" type="range" min={10} max={100} step={5} value={opacity} onChange={e => setOpacity(Number(e.target.value))}/></label>
    <label className="switch-label finishing-toggle"><input type="checkbox" aria-label="Put the subject in front of the title" checked={subjectFront} disabled={!hasMedia} onChange={e => setSubjectFront(e.target.checked)}/> Put the person or object in front of the title (AI cutout)</label>
    {subjectFront && <p className="hint">{isVideo ? 'Works on one video clip up to 20 s at normal speed. It takes a little while (frame by frame, on this PC).' : 'Works on one still image with Camera movement set to Static in Motion.'}</p>}
    {!hasMedia && <p className="hint">Add a video or picture to this scene first: it is what shows inside the letters.</p>}
    <button className="btn btn-primary" disabled={disabled || busy || !text.trim() || !hasMedia} onClick={() => void add()}><Sparkles size={14}/> {busy ? 'Working…' : 'Add video-inside-text title'}</button>
    {msg && <p className="info-status" role="status">{msg}</p>}
  </section>;
}
