// RC7 creative tools: AI subject cutout ("text behind subject", background removal) and
// textured text titles (procedural presets, a Media Pool image, or a generated texture).
import React from 'react';
import {Scissors, Type, Sparkles} from 'lucide-react';
import {api, Asset, ProviderProfile, Scene} from './api';

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
    <p className="hint">Removes the background on this computer with a local AI model. “Text behind subject” keeps captions and titles behind the person or object. Works on scenes with one still image and no camera movement.</p>
    <div className="acc-grid">
      <label className="control-label">Model<select aria-label="Cutout model" value={model} disabled={busy} onChange={e => setModel(e.target.value as any)}><option value="isnet">Best general · IS-Net (~170 MB)</option><option value="human">People (whole body) · U²-Net human (~176 MB)</option><option value="u2netp">Fast · U²-Net small (included)</option></select></label>
      <label className="control-label">Edges<select aria-label="Cutout edges" value={edge} disabled={busy} onChange={e => setEdge(e.target.value as any)}><option value="soft">Soft (hair, fur)</option><option value="crisp">Crisp (objects, products)</option></select></label>
    </div>
    <label className="control-label">Edge {shift > 0 ? `grow ${shift}px` : shift < 0 ? `shrink ${-shift}px (removes halos)` : 'as detected'}<input aria-label="Cutout edge shift" type="range" min={-10} max={10} value={shift} disabled={busy} onChange={e => setShift(Number(e.target.value))}/></label>
    <div className="button-row">
      <button className="btn btn-primary" disabled={disabled || busy || !isImage} onClick={() => void run('layer')}>{hasSubject ? 'Update text behind subject' : 'Put text behind subject'}</button>
      <button className="btn" disabled={disabled || busy || !isImage} onClick={() => void run('asset')}>Remove background → Media Pool</button>
    </div>
    {!isImage && <p className="hint">Add a still image to this scene to use subject cutout. Video cutout is not available yet.</p>}
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
