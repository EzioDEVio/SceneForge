import React, {useMemo, useState} from 'react';
import {Search} from 'lucide-react';
import data from './captionStyles.json';

type F = Record<string, any>;
export type CaptionPreset = {name: string; sample: string; values: F; group?: string};

/** Caption styles added in 0.7.0 RC9 (frontend/src/captionStyles.json). They use only the
 *  caption properties the renderer already maps to ASS (see backend/app/render/subtitles.py). */
export const EXTRA_CAPTION_PRESETS: CaptionPreset[] = data.styles as CaptionPreset[];
export const CAPTION_STYLE_GROUPS: string[] = data.groups;
const LEGACY_GROUPS: Record<string, string> = data.legacy_groups;

export function captionStyleGroup(p: CaptionPreset): string {
  return p.group || LEGACY_GROUPS[p.name] || 'Minimal';
}

function matches(p: CaptionPreset, query: string): boolean {
  const v = p.values;
  const hay = `${p.name} ${captionStyleGroup(p)} ${v.family || ''} ${v.karaoke ? `karaoke highlight ${v.karaoke_style || ''}` : ''} ${v.background === 'box' ? 'box' : ''} ${v.caption_animation || ''}`.toLowerCase();
  return query.toLowerCase().split(/\s+/).filter(Boolean).every(w => hay.includes(w));
}

/** The highlighted half of a karaoke tile sample (mirrors CaptionPreview's current word). */
function highlightCss(v: F): React.CSSProperties {
  const hi = v.highlight_color || '#FFD84D';
  switch (v.karaoke_style) {
    case 'box': return {background: hi, color: v.color || '#fff', borderRadius: 3, padding: '0 2px'};
    case 'glow': return {color: hi, textShadow: `0 0 6px ${hi}`};
    case 'underline': return {color: hi, textDecoration: 'underline'};
    default: return {color: hi};
  }
}

/** <option>s for a caption-style <select>, grouped like the picker. */
export function captionStyleOptions(presets: CaptionPreset[]): React.ReactNode {
  return CAPTION_STYLE_GROUPS.map(g => {
    const items = presets.filter(p => captionStyleGroup(p) === g);
    return items.length ? <optgroup key={g} label={g}>{items.map(p => <option key={p.name} value={p.name}>{p.name}</option>)}</optgroup> : null;
  });
}

/** Grouped, searchable caption-style tiles. Each tile previews the style with the same CSS
 *  approximation as the live caption preview. */
export function CaptionStylePicker({presets, css, onApply}: {presets: CaptionPreset[]; css: (f: F, scale?: number) => React.CSSProperties; onApply: (p: CaptionPreset) => void}) {
  const [group, setGroup] = useState('All');
  const [query, setQuery] = useState('');
  const shown = useMemo(() => presets.filter(p => (group === 'All' || captionStyleGroup(p) === group) && matches(p, query)), [presets, group, query]);
  return <div className="caption-style-picker">
    <label className="search-control"><Search size={14}/><input aria-label="Search caption styles" placeholder={`Search ${presets.length} styles…`} value={query} onChange={e => setQuery(e.target.value)}/></label>
    <div className="caption-style-tabs" role="group" aria-label="Caption style groups">
      {['All', ...CAPTION_STYLE_GROUPS].map(g => <button key={g} type="button" className={`sticker-tab ${group === g ? 'selected' : ''}`} aria-pressed={group === g} onClick={() => setGroup(g)}>
        {g}<small>{g === 'All' ? presets.length : presets.filter(p => captionStyleGroup(p) === g).length}</small></button>)}
    </div>
    <div className="caption-presets" role="group" aria-label="Caption styles">
      {shown.map(p => <button key={p.name} className="caption-preset" title={`${p.name} · ${captionStyleGroup(p)}`} aria-label={`Apply ${p.name} caption style`} onClick={() => onApply(p)}>
        <span className="caption-preset-sample" dir="auto" style={{...css({...p.values}, 0.55), fontSize: 20}}>{p.values.karaoke
          ? <>{p.sample.slice(0, Math.ceil(p.sample.length / 2))}<span style={highlightCss(p.values)}>{p.sample.slice(Math.ceil(p.sample.length / 2))}</span></> : p.sample}</span>
        <small>{p.name}</small></button>)}
    </div>
    {!shown.length && <p className="hint">No caption styles match that search.</p>}
  </div>;
}
