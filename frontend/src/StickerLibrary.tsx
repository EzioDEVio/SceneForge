import React, {useEffect, useMemo, useState} from 'react';
import {api} from './api';
import library from './stickerLibrary.json';

/** One bundled sticker (assets/stickers/library.json, built by scripts/build_sticker_library.py). */
export type LibrarySticker = {id: string; name: string; category: string; tags: string; emoji?: string; file: string; source: string};

export const STICKER_LIBRARY: LibrarySticker[] = library.items as LibrarySticker[];
export const STICKER_CATEGORIES: string[] = library.categories;
export const STICKER_ATTRIBUTION: string = library.attribution.twemoji;
const RECENT_KEY = 'sceneforge.recentStickers';
const RECENT_MAX = 16;

/** Every query word must appear in the sticker's name, tags, category or emoji. */
export function stickerMatches(s: LibrarySticker, query: string): boolean {
  const hay = `${s.name} ${s.tags} ${s.category} ${s.emoji || ''}`.toLowerCase();
  return query.toLowerCase().split(/\s+/).filter(Boolean).every(word => hay.includes(word));
}

function readRecent(): string[] {
  try {
    const ids = JSON.parse(localStorage.getItem(RECENT_KEY) || '[]');
    return Array.isArray(ids) ? ids.filter((id: unknown) => typeof id === 'string' && STICKER_LIBRARY.some(s => s.id === id)) : [];
  } catch {return [];}
}

/** Category tabs + the sticker grid. Search text comes from the panel (it also filters uploads). */
export function StickerLibraryGrid({query, disabled, busyId, onPick, extra, extraMatches}: {
  query: string; disabled: boolean; busyId: string; onPick: (s: LibrarySticker) => void;
  extra?: React.ReactNode; extraMatches?: boolean;
}) {
  const [category, setCategory] = useState('All');
  const [recent, setRecent] = useState<string[]>(readRecent);
  const [broken, setBroken] = useState<Record<string, boolean>>({});
  useEffect(() => {try {localStorage.setItem(RECENT_KEY, JSON.stringify(recent));} catch {/* storage unavailable */}}, [recent]);
  const shown = useMemo(() => {
    const pool = category === 'Recent' ? recent.map(id => STICKER_LIBRARY.find(s => s.id === id)!).filter(Boolean)
      : category === 'All' ? STICKER_LIBRARY : STICKER_LIBRARY.filter(s => s.category === category);
    return pool.filter(s => stickerMatches(s, query));
  }, [category, query, recent]);
  const tabs = ['All', ...(recent.length ? ['Recent'] : []), ...STICKER_CATEGORIES];
  function pick(s: LibrarySticker) {
    setRecent(ids => [s.id, ...ids.filter(id => id !== s.id)].slice(0, RECENT_MAX));
    onPick(s);
  }
  const showExtra = category === 'All';
  return <>
    <div className="sticker-tabs" role="group" aria-label="Sticker categories">
      {tabs.map(t => <button key={t} type="button" className={`sticker-tab ${category === t ? 'selected' : ''}`} aria-pressed={category === t}
        onClick={() => setCategory(t)}>{t}{t !== 'All' && t !== 'Recent' ? <small>{STICKER_LIBRARY.filter(s => s.category === t).length}</small> : null}</button>)}
    </div>
    <div className="sticker-grid" role="group" aria-label="Sticker choices">
      {shown.map(s => <button key={s.id} type="button" className="sticker-choice library-sticker-choice" title={s.name} data-sticker-id={s.id}
        aria-label={`Add ${s.name} sticker`} disabled={disabled || !!busyId} onClick={() => pick(s)}>
        <span aria-hidden="true">{busyId === s.id ? '…' : broken[s.id]
          ? (s.emoji || s.name.slice(0, 3))
          : <img src={api.stickerImageUrl(s.id)} alt="" loading="lazy" draggable={false} onError={() => setBroken(b => ({...b, [s.id]: true}))}/>}</span>
        <small>{s.name}</small></button>)}
      {showExtra && extra}
    </div>
    {!shown.length && !(showExtra && extraMatches) && <p className="hint">{category === 'Recent' && !query ? 'Stickers you add appear here.' : 'No stickers match that search.'}</p>}
    <p className="sticker-credit">Emoji: Twemoji, CC-BY 4.0</p>
  </>;
}
