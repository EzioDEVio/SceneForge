import {WhisperCheck} from './LocalServices';
import React from 'react';
import {Bold, Italic, Underline, Type, Palette, Square, Move, Rows3, Highlighter, Sparkles, Wand2} from 'lucide-react';
import {api, type Scene} from './api';
import {previewFontFamily} from './fonts';
import {ANIMATION_LABELS} from './TitleDesigner';
import {FeatureHelp} from './FeatureHelp';
import {CaptionStylePicker, EXTRA_CAPTION_PRESETS, captionStyleOptions} from './CaptionStylePicker';

type F = Record<string, any>;
const FAMILIES = ['Noto Sans', 'Poppins', 'Bebas Neue', 'Anton', 'Pacifico', 'Noto Naskh Arabic', 'Noto Sans Arabic', 'Amiri', 'Tajawal', 'Lalezar',
  'Arial', 'Calibri', 'Segoe UI', 'Tahoma', 'Times New Roman', 'Georgia', 'Verdana', 'Trebuchet MS'];
const ENTRANCE = ['none', 'fade', 'letters-pop', 'letters-fade', 'letters-flip', 'letters-blur', 'words-pop', 'words-fade', 'words-flip', 'shine', 'bounce', 'zoom', 'blur', 'neon', 'wobble', 'glitch'];

/** One-click caption looks, CapCut-style. */
export const CAPTION_PRESETS: {name: string; sample: string; values: F}[] = [
  {name: 'Classic', sample: 'Classic', values: {family: 'Noto Sans', size: 44, bold: false, italic: false, case: 'none', color: '#FFFFFF', outline_color: '#000000', outline_width: 2, shadow: 0, background: 'none', split: 'full', karaoke: false, caption_animation: 'none', exit_animation: 'none', loop: 'none', spacing: 0}},
  {name: 'YouTube box', sample: 'Box', values: {family: 'Noto Sans', size: 42, bold: false, case: 'none', color: '#FFFFFF', background: 'box', box_color: '#000000', box_opacity: 70, box_padding: 10, shadow: 0, split: 'full', karaoke: false, caption_animation: 'fade', exit_animation: 'none', loop: 'none'}},
  {name: 'Viral bold', sample: 'VIRAL', values: {family: 'Anton', size: 84, case: 'upper', color: '#FFFFFF', outline_color: '#000000', outline_width: 6, background: 'none', shadow: 0, split: 'phrases', phrase_words: 3, karaoke: true, karaoke_style: 'box', highlight_color: '#FFD84D', caption_animation: 'words-pop', caption_animation_ms: 300, exit_animation: 'none', loop: 'none'}},
  {name: 'Karaoke', sample: 'Karaoke', values: {family: 'Poppins', size: 62, bold: true, case: 'none', color: '#FFFFFF', outline_color: '#000000', outline_width: 3, background: 'none', split: 'phrases', phrase_words: 4, karaoke: true, karaoke_style: 'color', highlight_color: '#7CFF6B', caption_animation: 'fade', caption_animation_ms: 200, exit_animation: 'none'}},
  {name: 'Neon', sample: 'Neon', values: {family: 'Poppins', size: 60, bold: true, case: 'none', color: '#FFFFFF', outline_width: 0, background: 'none', shadow: 0, split: 'phrases', phrase_words: 4, karaoke: false, caption_animation: 'neon', caption_animation_ms: 900, highlight_color: '#29E6FF', exit_animation: 'fade'}},
  {name: 'Cinematic', sample: 'CINEMA', values: {family: 'Noto Sans', size: 34, bold: false, case: 'upper', spacing: 8, color: '#F2E6D0', outline_width: 0, shadow: 2, shadow_opacity: 70, background: 'none', split: 'full', karaoke: false, caption_animation: 'letters-fade', caption_animation_ms: 1500, exit_animation: 'fade', loop: 'none'}},
  {name: 'Documentary', sample: 'Story', values: {family: 'Amiri', size: 46, bold: false, italic: true, case: 'none', color: '#FFFFFF', outline_width: 0, shadow: 3, shadow_opacity: 75, background: 'none', split: 'phrases', phrase_words: 5, karaoke: false, caption_animation: 'fade', caption_animation_ms: 400, exit_animation: 'fade'}},
  {name: 'Underline', sample: 'Under', values: {family: 'Poppins', size: 58, bold: true, case: 'none', color: '#FFFFFF', outline_color: '#000000', outline_width: 3, background: 'none', split: 'phrases', phrase_words: 4, karaoke: true, karaoke_style: 'underline', highlight_color: '#FF6B6B', caption_animation: 'none'}},
  {name: 'Arabic modern', sample: 'عربي', values: {family: 'Tajawal', size: 66, bold: true, case: 'none', color: '#FFFFFF', outline_color: '#000000', outline_width: 3, background: 'none', split: 'phrases', phrase_words: 3, karaoke: true, karaoke_style: 'box', highlight_color: '#FFB020', caption_animation: 'words-pop', caption_animation_ms: 300}},
  {name: 'Bold outline', sample: 'BOLD', values: {family: 'Poppins', size: 64, bold: true, case: 'upper', color: '#FFFFFF', outline_color: '#000000', outline_width: 7, background: 'none', shadow: 2, shadow_opacity: 60, split: 'phrases', phrase_words: 3, karaoke: false, caption_animation: 'words-pop', caption_animation_ms: 250}},
  {name: 'Yellow box', sample: 'Yellow', values: {family: 'Poppins', size: 56, bold: true, case: 'none', color: '#111111', background: 'box', box_color: '#FFD84D', box_opacity: 100, box_padding: 12, outline_width: 0, split: 'phrases', phrase_words: 4, karaoke: false, caption_animation: 'bounce', caption_animation_ms: 300}},
  {name: 'Red highlight', sample: 'Red', values: {family: 'Anton', size: 72, case: 'upper', color: '#FFFFFF', outline_color: '#000000', outline_width: 5, background: 'none', split: 'phrases', phrase_words: 2, karaoke: true, karaoke_style: 'box', highlight_color: '#FF3B3B', caption_animation: 'words-pop', caption_animation_ms: 250}},
  {name: 'Green karaoke', sample: 'Green', values: {family: 'Bebas Neue', size: 78, case: 'upper', color: '#FFFFFF', outline_color: '#000000', outline_width: 5, background: 'none', split: 'phrases', phrase_words: 3, karaoke: true, karaoke_style: 'color', highlight_color: '#39FF6A', caption_animation: 'none'}},
  {name: 'Blue glow', sample: 'Glow', values: {family: 'Poppins', size: 58, bold: true, case: 'none', color: '#FFFFFF', outline_width: 0, background: 'none', split: 'phrases', phrase_words: 3, karaoke: true, karaoke_style: 'glow', highlight_color: '#4DB8FF', caption_animation: 'fade', caption_animation_ms: 200}},
  {name: 'Handwritten', sample: 'Hello', values: {family: 'Pacifico', size: 60, bold: false, case: 'none', color: '#FFFFFF', outline_color: '#1A1A1A', outline_width: 3, background: 'none', shadow: 2, split: 'phrases', phrase_words: 4, karaoke: false, caption_animation: 'fade', caption_animation_ms: 300}},
  {name: 'News lower third', sample: 'News', values: {family: 'Noto Sans', size: 40, bold: true, case: 'none', color: '#FFFFFF', background: 'box', box_color: '#C8102E', box_opacity: 95, box_padding: 10, outline_width: 0, position: 'bottom', halign: 'left', split: 'full', karaoke: false, caption_animation: 'fade', caption_animation_ms: 300}},
  {name: 'Elegant serif', sample: 'Elegant', values: {family: 'Amiri', size: 50, bold: false, italic: false, case: 'none', color: '#F5EFE0', outline_width: 0, shadow: 2, shadow_opacity: 80, spacing: 2, background: 'none', split: 'phrases', phrase_words: 5, karaoke: false, caption_animation: 'letters-fade', caption_animation_ms: 700}},
  {name: 'Creator punch', sample: 'PUNCH!', values: {family: 'Anton', size: 86, bold: true, case: 'upper', color: '#FFFFFF', outline_color: '#151515', outline_width: 8, shadow: 2, background: 'none', split: 'phrases', phrase_words: 2, karaoke: true, karaoke_style: 'pop', highlight_color: '#FFB000', caption_animation: 'bounce', caption_animation_ms: 240}},
  {name: 'Soft subtitle', sample: 'Soft subtitle', values: {family: 'Poppins', size: 42, bold: false, case: 'none', color: '#FFFFFF', outline_color: '#000000', outline_width: 2, shadow: 2, background: 'box', box_color: '#111827', box_opacity: 72, box_padding: 9, split: 'phrases', phrase_words: 5, karaoke: false, caption_animation: 'fade', caption_animation_ms: 350}},
  {name: 'Glass panel', sample: 'Glass panel', values: {family: 'Poppins', size: 44, bold: true, case: 'none', color: '#FFFFFF', outline_width: 0, shadow: 1, background: 'box', box_color: '#24364B', box_opacity: 78, box_padding: 14, split: 'phrases', phrase_words: 4, karaoke: true, karaoke_style: 'color', highlight_color: '#7CE7FF', caption_animation: 'fade', caption_animation_ms: 300}},
  {name: 'Pastel pop', sample: 'Pastel pop', values: {family: 'Poppins', size: 58, bold: true, case: 'none', color: '#FFE9F4', outline_color: '#49243B', outline_width: 3, shadow: 2, background: 'none', split: 'phrases', phrase_words: 3, karaoke: true, karaoke_style: 'pop', highlight_color: '#FF8CC6', caption_animation: 'words-pop', caption_animation_ms: 260}},
  {name: 'Cyber cyan', sample: 'CYBER', values: {family: 'Bebas Neue', size: 72, bold: true, case: 'upper', color: '#B8FBFF', outline_color: '#07252D', outline_width: 3, shadow: 3, background: 'none', split: 'phrases', phrase_words: 3, karaoke: true, karaoke_style: 'glow', highlight_color: '#00E5FF', caption_animation: 'glitch', caption_animation_ms: 300}},
  {name: 'Clean white', sample: 'Clean white', values: {family: 'Noto Sans', size: 46, bold: true, case: 'none', color: '#FFFFFF', outline_color: '#101114', outline_width: 3, shadow: 1, background: 'none', split: 'phrases', phrase_words: 5, karaoke: false, caption_animation: 'fade', caption_animation_ms: 250}},
  {name: 'Pulse', sample: 'Pulse', values: {family: 'Bebas Neue', size: 80, case: 'upper', color: '#FFE14D', outline_color: '#000000', outline_width: 4, background: 'none', split: 'phrases', phrase_words: 2, karaoke: false, caption_animation: 'bounce', caption_animation_ms: 350, loop: 'pulse', exit_animation: 'pop', exit_ms: 200}},
  {name: 'TikTok word pop', sample: 'POP!', values: {family: 'Anton', size: 76, bold: true, case: 'upper', color: '#FFFFFF', outline_color: '#111111', outline_width: 6, split: 'phrases', phrase_words: 2, karaoke: true, karaoke_style: 'pop', highlight_color: '#FFE600', caption_animation: 'words-pop', caption_animation_ms: 210, exit_animation: 'pop', exit_ms: 180}},
  {name: 'Reels minimal', sample: 'Minimal', values: {family: 'Poppins', size: 42, bold: true, case: 'none', color: '#FFFFFF', outline_color: '#171717', outline_width: 2, shadow: 3, shadow_opacity: 82, split: 'phrases', phrase_words: 5, karaoke: false, caption_animation: 'fade', caption_animation_ms: 260, exit_animation: 'fade'}},
  {name: 'Yellow marker', sample: 'Marker', values: {family: 'Poppins', size: 50, bold: true, case: 'none', color: '#171717', background: 'box', box_color: '#FFE45E', box_opacity: 100, box_padding: 11, outline_width: 0, split: 'phrases', phrase_words: 4, karaoke: true, karaoke_style: 'underline', highlight_color: '#E53D32', caption_animation: 'words-pop', caption_animation_ms: 240}},
  {name: 'Blue subtitle bar', sample: 'Subtitle', values: {family: 'Noto Sans', size: 40, bold: true, case: 'none', color: '#FFFFFF', background: 'box', box_color: '#173D68', box_opacity: 94, box_padding: 12, outline_width: 0, split: 'phrases', phrase_words: 5, karaoke: true, karaoke_style: 'color', highlight_color: '#75D7FF', caption_animation: 'fade', caption_animation_ms: 300}},
  {name: 'Creator highlight', sample: 'Creator', values: {family: 'Anton', size: 68, bold: true, case: 'upper', color: '#FFFFFF', outline_color: '#25121B', outline_width: 5, background: 'none', split: 'phrases', phrase_words: 3, karaoke: true, karaoke_style: 'box', highlight_color: '#FF3E78', caption_animation: 'bounce', caption_animation_ms: 260}},
  {name: 'Arabic clean', sample: 'مرحبا', values: {family: 'Noto Sans Arabic', size: 48, bold: true, case: 'none', color: '#FFFFFF', outline_color: '#171717', outline_width: 3, shadow: 1, split: 'phrases', phrase_words: 4, karaoke: false, caption_animation: 'fade', caption_animation_ms: 300}},
  {name: 'Neon lime karaoke', sample: 'LIME', values: {family: 'Bebas Neue', size: 70, bold: true, case: 'upper', color: '#F7FFF2', outline_color: '#142610', outline_width: 4, shadow: 3, background: 'none', split: 'phrases', phrase_words: 3, karaoke: true, karaoke_style: 'glow', highlight_color: '#78FF39', caption_animation: 'neon', caption_animation_ms: 520}},
  ...EXTRA_CAPTION_PRESETS,
];

/** CSS approximation of a caption style (used by the presets and the live preview). */
export function captionCss(f: F, scale = 1): React.CSSProperties {
  const ow = f.background === 'box' ? 0 : Number(f.outline_width ?? 2);
  const oc = f.outline_color || '#000000';
  const shadows: string[] = [];
  if (ow > 0) for (let a = 0; a < 16; a++) {const r = ow * scale * 0.6; shadows.push(`${(Math.cos(a / 8 * Math.PI) * r).toFixed(1)}px ${(Math.sin(a / 8 * Math.PI) * r).toFixed(1)}px 0 ${oc}`);}
  if (Number(f.shadow) > 0) {const d = Number(f.shadow) * scale; const op = (Number(f.shadow_opacity ?? 60) / 100).toFixed(2); const sc = /^#[0-9a-f]{6}$/i.test(f.shadow_color || '') ? f.shadow_color : '#000000'; shadows.push(`${d}px ${d}px ${d}px rgba(${parseInt(sc.slice(1, 3), 16)},${parseInt(sc.slice(3, 5), 16)},${parseInt(sc.slice(5, 7), 16)},${op})`);}
  const hex = (h: string, o: number) => `rgba(${parseInt(h.slice(1, 3), 16)},${parseInt(h.slice(3, 5), 16)},${parseInt(h.slice(5, 7), 16)},${o})`;
  return {
    fontFamily: previewFontFamily(f.family), fontWeight: f.bold ? 700 : 400, fontStyle: f.italic ? 'italic' : 'normal',
    textDecoration: f.underline ? 'underline' : 'none', color: f.color || '#FFFFFF', letterSpacing: `${Number(f.spacing || 0) * scale * 0.5}px`,
    textTransform: f.case === 'upper' ? 'uppercase' : f.case === 'lower' ? 'lowercase' : f.case === 'title' ? 'capitalize' : 'none',
    textShadow: shadows.join(',') || 'none',
    background: f.background === 'box' ? hex(f.box_color || '#000000', Number(f.box_opacity ?? 60) / 100) : 'transparent',
    padding: f.background === 'box' ? `${Number(f.box_padding ?? 10) * scale * 0.4}px ${Number(f.box_padding ?? 10) * scale * 0.7}px` : 0,
  };
}

/** Live caption preview on the editor picture: first phrase (or whole text) with the chosen
 *  style, position and a sample word highlight. The render is exact; this is close. */
export function CaptionPreview({font, text, projectW, projectH}: {font: F; text: string; projectW: number; projectH: number}) {
  if (!font.captions_enabled || !text.trim() || font.typewriter) return null;
  const words = text.trim().split(/\s+/);
  const shown = font.split === 'phrases' ? words.slice(0, Math.max(1, Number(font.phrase_words || 3))) : words;
  const hiIdx = font.karaoke ? Math.min(1, shown.length - 1) : -1;
  const hi = font.highlight_color || '#FFD84D';
  const pos = font.position || 'bottom';
  const cqw = Number(font.size || 44) * 0.74 / projectW * 100;
  const base = projectH > projectW * 1.2 ? 20 : 5.5;     // vertical: clear of TikTok/Reels/Shorts buttons    // libass size ≈ 0.74 of a browser em
  const style: React.CSSProperties = {
    ...captionCss(font, 0.9), fontSize: `${cqw}cqw`,
    left: `${(100 - Number(font.max_width || 90)) / 2}%`, right: `${(100 - Number(font.max_width || 90)) / 2}%`,
    textAlign: (font.halign || 'center') as any,
    ...(pos === 'top' ? {top: `${base + Number(font.offset_y || 0)}%`} : pos === 'middle' ? {top: '50%', transform: 'translateY(-50%)'} : {bottom: `${base + Number(font.offset_y || 0)}%`}),
  };
  return <div className="caption-preview" aria-hidden="true" style={{position: 'absolute', zIndex: 5, pointerEvents: 'none', ...style, background: 'transparent', padding: 0}} dir="auto">
    <span style={{...captionCss(font, 0.9), fontSize: 'inherit', display: 'inline', boxDecorationBreak: 'clone', WebkitBoxDecorationBreak: 'clone', lineHeight: 1.35}}>
      {shown.map((w, i) => {
        const cur = i === hiIdx, st = font.karaoke_style || 'fill';
        const wStyle: React.CSSProperties = !cur ? {} : st === 'box' ? {background: hi, borderRadius: '0.25em', padding: '0 0.18em', color: font.color || '#fff'}
          : st === 'underline' ? {color: hi, textDecoration: 'underline'} : st === 'pop' ? {color: hi, fontSize: '1.2em'} : st === 'glow' ? {color: hi, textShadow: `0 0 0.35em ${hi}`} : {color: hi};
        return <React.Fragment key={i}><span style={wStyle}>{w}</span>{i < shown.length - 1 ? ' ' : ''}</React.Fragment>;
      })}
    </span>
  </div>;
}

function Seg<T extends string>({label, value, options, onChange}: {label: string; value: T; options: [T, React.ReactNode][]; onChange: (v: T) => void}) {
  return <div className="film-option"><span>{label}</span><div className="segmented" role="radiogroup" aria-label={label}>
    {options.map(([v, l]) => <button key={v} role="radio" aria-checked={value === v} className={value === v ? 'selected' : ''} onClick={() => onChange(v)}>{l}</button>)}
  </div></div>;
}
function Num({label, value, min, max, step = 1, onChange, unit = ''}: {label: string; value: number; min: number; max: number; step?: number; onChange: (v: number) => void; unit?: string}) {
  return <div className="adjust-row changed"><label>{label}</label>
    <input type="range" aria-label={label} min={min} max={max} step={step} value={value} onChange={e => onChange(Number(e.target.value))}/>
    <input type="number" aria-label={`${label} value`} min={min} max={max} step={step} value={value} onChange={e => onChange(Math.max(min, Math.min(max, Number(e.target.value) || 0)))}/><span className="unit">{unit}</span></div>;
}
const GROUP_GUIDE:Record<string,[string,string]>={
  'Caption styles':['Apply a ready-made visual treatment to captions.','Choose a style tile; caption wording remains unchanged.'],
  Font:['Set caption typeface, size and weight.','Choose a font and adjust size; use bundled Noto fonts for consistent Arabic rendering.'],
  'Colours & outline':['Set caption color, outline and contrast.','Choose a text color and outline that remains readable over your footage.'],
  'Background box':['Add a background plate behind captions.','Choose a fill and adjust its opacity, roundness and padding.'],
  Position:['Place captions within the frame.','Choose a preset position or adjust the on-screen offsets.'],
  Display:['Control how much caption text is shown at once.','Choose line wrapping and phrase settings for the style you want.'],
  'Word highlight':['Highlight spoken words as they are read.','Choose a highlight color/style; exact timing uses transcript or voice alignment when available.'],
  Animation:['Animate captions as they enter or reveal.','Choose an animation and duration, then render a scene to review timing.'],
};
const Group = ({title, Icon, children}: {title: string; Icon: typeof Type; children: React.ReactNode}) => {
  const [description,steps]=GROUP_GUIDE[title]||['Adjust this caption setting.','Change the control and review the caption preview.'];
  return <fieldset className="adjust-group caption-group"><legend><Icon size={12}/> {title} <FeatureHelp compact title={title} description={description} steps={steps}/></legend>{children}</fieldset>;
};

/** Captions Pro: every caption setting in one organised panel. */
export function CaptionStylePanel({scene, onChange}: {scene: Scene; onChange: (f: F) => void}) {
  const f = scene.font_json as F;
  const set = (p: F) => onChange(p);
  const busyAnim = f.typewriter;
  return <div className="caption-pro">
    <Group title="Caption styles" Icon={Wand2}>
      <CaptionStylePicker presets={CAPTION_PRESETS} css={captionCss} onApply={p => set({...p.values, captions_enabled: true, typewriter: false})}/>
    </Group>
    <label className="switch-label finishing-toggle"><input type="checkbox" checked={!!f.captions_enabled} onChange={e => set({captions_enabled: e.target.checked})}/> Captions enabled</label>
    <Group title="Font" Icon={Type}>
      <label className="control-label">Font<select aria-label="Caption font" value={f.family || 'Noto Naskh Arabic'} onChange={e => set({family: e.target.value})}>{FAMILIES.map(x => <option key={x}>{x}</option>)}</select></label>
      <Num label="Size" value={Number(f.size || 44)} min={16} max={120} onChange={size => set({size})}/>
      <div className="style-toggles" role="group" aria-label="Font style">
        <button className={`icon-toggle ${f.bold ? 'on' : ''}`} aria-pressed={!!f.bold} aria-label="Bold" onClick={() => set({bold: !f.bold})}><Bold size={14}/></button>
        <button className={`icon-toggle ${f.italic ? 'on' : ''}`} aria-pressed={!!f.italic} aria-label="Italic" onClick={() => set({italic: !f.italic})}><Italic size={14}/></button>
        <button className={`icon-toggle ${f.underline ? 'on' : ''}`} aria-pressed={!!f.underline} aria-label="Underline" onClick={() => set({underline: !f.underline})}><Underline size={14}/></button>
      </div>
      <Seg label="Letter case" value={f.case || 'none'} options={[['none', 'As typed'], ['upper', 'AA'], ['title', 'Aa'], ['lower', 'aa']]} onChange={v => set({case: v})}/>
      <Num label="Letter spacing" value={Number(f.spacing || 0)} min={-5} max={40} onChange={spacing => set({spacing})}/>
    </Group>
    <Group title="Colours & outline" Icon={Palette}>
      <div className="adjust-row changed"><label>Text colour</label><input type="color" aria-label="Caption colour" value={f.color || '#FFFFFF'} onChange={e => set({color: e.target.value.toUpperCase()})}/><span/><span/></div>
      <div className="adjust-row changed"><label>Outline</label><input type="color" aria-label="Outline colour" value={f.outline_color || '#000000'} onChange={e => set({outline_color: e.target.value.toUpperCase()})}/><span/><span/></div>
      <Num label="Outline width" value={Number(f.outline_width ?? 2)} min={0} max={12} onChange={outline_width => set({outline_width})}/>
      <Num label="Shadow" value={Number(f.shadow || 0)} min={0} max={10} onChange={shadow => set({shadow})}/>
      {Number(f.shadow) > 0 && <><div className="adjust-row changed"><label>Shadow colour</label><input type="color" aria-label="Shadow colour" value={f.shadow_color || '#000000'} onChange={e => set({shadow_color: e.target.value.toUpperCase()})}/><span/><span/></div>
        <Num label="Shadow opacity" value={Number(f.shadow_opacity ?? 60)} min={0} max={100} unit="%" onChange={shadow_opacity => set({shadow_opacity})}/></>}
    </Group>
    <Group title="Background box" Icon={Square}>
      <label className="switch-label finishing-toggle"><input type="checkbox" aria-label="Background box" checked={f.background === 'box'} onChange={e => set({background: e.target.checked ? 'box' : 'none'})}/> Box behind the captions</label>
      {f.background === 'box' && <>
        <div className="adjust-row changed"><label>Box colour</label><input type="color" aria-label="Box colour" value={f.box_color || '#000000'} onChange={e => set({box_color: e.target.value.toUpperCase()})}/><span/><span/></div>
        <Num label="Box opacity" value={Number(f.box_opacity ?? 60)} min={0} max={100} unit="%" onChange={box_opacity => set({box_opacity})}/>
        <Num label="Box padding" value={Number(f.box_padding ?? 10)} min={0} max={40} onChange={box_padding => set({box_padding})}/>
      </>}
    </Group>
    <Group title="Position" Icon={Move}>
      <Seg label="Vertical" value={f.position || 'bottom'} options={[['top', 'Top'], ['middle', 'Middle'], ['bottom', 'Bottom']]} onChange={v => set({position: v})}/>
      <Seg label="Align" value={f.halign || 'center'} options={[['left', 'Left'], ['center', 'Centre'], ['right', 'Right']]} onChange={v => set({halign: v})}/>
      <Num label="Move up / down" value={Number(f.offset_y || 0)} min={-40} max={40} unit="%" onChange={offset_y => set({offset_y})}/>
      <Num label="Max width" value={Number(f.max_width || 90)} min={30} max={100} unit="%" onChange={max_width => set({max_width})}/>
    </Group>
    <Group title="Display" Icon={Rows3}>
      <Seg label="Show" value={f.split || 'full'} options={[['full', 'Whole text'], ['phrases', 'Phrases (CapCut)']]} onChange={v => set({split: v, ...(v === 'phrases' ? {typewriter: false} : {})})}/>
      {f.split === 'phrases' && <Num label="Words per phrase" value={Number(f.phrase_words || 3)} min={1} max={8} onChange={phrase_words => set({phrase_words})}/>}
      <p className="hint">{f.split === 'phrases' ? 'A few words at a time, appearing as they are spoken.' : 'The whole caption stays on screen.'}</p>
    </Group>
    <Group title="Word highlight" Icon={Highlighter}>
      <label className="switch-label finishing-toggle"><input type="checkbox" aria-label="Word-by-word highlight" checked={!!f.karaoke} onChange={e => set({karaoke: e.target.checked, ...(e.target.checked ? {captions_enabled: true, typewriter: false} : {})})}/> Word-by-word highlight (follows the narration)</label>
      {f.karaoke && <>
        <label className="control-label">Caption style<select aria-label="Caption style" value={f.karaoke_style || 'fill'} onChange={e => set({karaoke_style: e.target.value})}>
          <option value="fill">Colour fill (spoken words stay coloured)</option><option value="color">Colour (only the current word)</option>
          <option value="box">Box (marker behind the word)</option><option value="underline">Underline</option>
          <option value="pop">Pop (current word grows)</option><option value="glow">Glow (current word glows)</option></select></label>
        <div className="adjust-row changed"><label>Highlight colour</label><input type="color" aria-label="Highlight colour" value={f.highlight_color || '#FFD84D'} onChange={e => set({highlight_color: e.target.value.toUpperCase()})}/><span/><span/></div>
      </>}
    </Group>
    <Group title="Animation" Icon={Sparkles}>
      <label className="control-label">Caption animation ✦<select aria-label="Caption animation" value={f.caption_animation || 'none'} disabled={busyAnim || (f.karaoke && f.split !== 'phrases')} onChange={e => set({caption_animation: e.target.value})}>
        {ENTRANCE.map(v => <option key={v} value={v}>{ANIMATION_LABELS[v] || v}</option>)}</select></label>
      <Num label="Entrance length" value={Number(f.caption_animation_ms || 900) / 1000} min={0.1} max={10} step={0.1} unit="s" onChange={s => set({caption_animation_ms: Math.round(s * 1000)})}/>
      <Seg label="Exit" value={f.exit_animation || 'none'} options={[['none', 'None'], ['fade', 'Fade out'], ['pop', 'Pop out']]} onChange={v => set({exit_animation: v})}/>
      <Seg label="Loop" value={f.loop || 'none'} options={[['none', 'None'], ['pulse', 'Pulse']]} onChange={v => set({loop: v})}/>
      <label className="switch-label finishing-toggle"><input type="checkbox" checked={!!f.typewriter} onChange={e => set({typewriter: e.target.checked, ...(e.target.checked ? {captions_enabled: true, karaoke: false, split: 'full'} : {})})}/> Typewriter reveal (captions)</label>
      <p className="hint">{busyAnim ? 'Typewriter reveal animates the captions on its own; turn it off to use the animations above.' : 'In phrases mode each phrase gets the entrance, exit and pulse. Arabic animates word by word. Render text preview for the exact result.'}</p>
    </Group>
  </div>;
}


const LANGS: [string, string][] = [['', 'Detect automatically'], ['ar', 'Arabic'], ['en', 'English'], ['fr', 'French'], ['es', 'Spanish'], ['de', 'German'], ['tr', 'Turkish'],
  ['fa', 'Persian'], ['ur', 'Urdu'], ['hi', 'Hindi'], ['id', 'Indonesian'], ['pt', 'Portuguese'], ['it', 'Italian'], ['ru', 'Russian'], ['zh', 'Chinese'], ['ja', 'Japanese'], ['ko', 'Korean']];

/** CapCut-style automatic captions: transcribe the speech in the scene (narration, or the
 *  videos' own sound) with the language detected, then style them with Captions Pro. */
export function AutoCaptions({scene, onDone, onStyle}: {scene: Scene; onDone: (s: Scene) => void; onStyle?: (values: F) => void | Promise<void>}) {
  const [lang, setLang] = React.useState('');
  const [provider, setProvider] = React.useState('local');
  const [source, setSource] = React.useState('auto');
  const [style, setStyle] = React.useState('Viral bold');
  const [wordsPerClip,setWordsPerClip]=React.useState(3);
  const [busy, setBusy] = React.useState(false);
  const [msg, setMsg] = React.useState('');
  const tr = (scene.font_json as any)?.transcript;
  const hasNarr = scene.voice_takes.some(t => t.accepted);
  const hasVideo = scene.shots.some(s => s.asset?.type === 'video');
  async function go() {
    setBusy(true); setMsg('Listening to the speech…');
    try {
      const preset = CAPTION_PRESETS.find(p => p.name === style);
      const sc = await api.autoCaptions(scene.id, {provider, language: lang, phrase_words:wordsPerClip, source}); const t = (sc.font_json as any)?.transcript;
      if (preset && onStyle) await onStyle({...preset.values, captions_enabled: true, typewriter: false});
      const portions=(sc.font_json as any)?.caption_segments?.length||0;
      setMsg(`Done: ${t?.words?.length || 0} words · ${portions} editable caption clips${t?.language ? ` · language: ${t.language}` : ''}${t?.word_timing==='estimated'?' · timing estimated from phrase boundaries':''}${preset ? ` · style: ${preset.name}` : ''}. Edit each clip below or click it on T1.`); onDone(sc);
    } catch (e: any) {setMsg(e.message || String(e));} finally {setBusy(false);}
  }
  const disabled = !hasNarr && !hasVideo;
  const hasTranscript = Array.isArray(tr?.words) && tr.words.length > 0;
  return <section className="auto-captions-card" aria-label="Auto captions">
    <header><span className="acc-icon"><Sparkles size={16}/></span><div><strong>Auto captions</strong><span>{disabled ? 'Add narration or a video with sound to this scene first.' : `Turns ${hasNarr ? 'the narration' : 'the speech in your video'} into timed captions, in any language.`}</span></div>
      {tr?.language && <span className="info-badge ok">{tr.language} · {tr.source === 'clips' ? 'video sound' : 'narration'}</span>}</header>
    <div className="acc-grid">
      <label className="control-label">Language<select aria-label="Speech language" value={lang} disabled={disabled} onChange={e => setLang(e.target.value)}>{LANGS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      {hasNarr && hasVideo && <label className="control-label">Audio source<select aria-label="Caption audio source" value={source} disabled={disabled} onChange={e=>setSource(e.target.value)}><option value="auto">Auto · narration first</option><option value="narration">Scene narration</option><option value="clips">Video clip sound</option></select></label>}
      <label className="control-label">Caption style<select aria-label="Auto caption style" value={style} disabled={disabled} onChange={e => {setStyle(e.target.value);const p=CAPTION_PRESETS.find(x=>x.name===e.target.value);if(p)setWordsPerClip(Number(p.values.phrase_words||3));}}><option value="">Keep current style</option>{captionStyleOptions(CAPTION_PRESETS)}</select></label>
      <label className="control-label">Service<select aria-label="Transcription service" value={provider} disabled={disabled} onChange={e => setProvider(e.target.value)}><option value="local">Local Whisper · free</option><option value="elevenlabs">ElevenLabs Scribe · cloud</option><option value="openai">OpenAI Whisper · cloud</option></select></label>
      <label className="control-label">Words per caption clip<select aria-label="Words per caption clip" value={wordsPerClip} disabled={disabled} onChange={e=>setWordsPerClip(Math.max(1,Math.min(8,Number(e.target.value)||3)))}>{Array.from({length:8},(_,i)=>i+1).map(n=><option key={n} value={n}>{n} {n===1?'word':'words'}</option>)}</select></label>
      <button className="btn btn-primary acc-go" disabled={busy || disabled} onClick={() => void go()}><Sparkles size={14}/> {busy ? 'Transcribing…' : hasTranscript ? 'Regenerate captions' : 'Generate captions'}</button>
    </div>
    {provider === 'local' && <p className="hint">Runs on this PC with no API key. The multilingual Whisper model downloads once on first use; after that, captions work offline.</p>}
    {msg && <p className="info-status" aria-live="polite">{msg}</p>}
    {provider === 'local' && <WhisperCheck/>}
  </section>;
}
