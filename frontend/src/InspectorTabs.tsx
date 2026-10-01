import React, {useCallback, useEffect, useLayoutEffect, useRef, useState} from 'react';
import {ChevronDown, type LucideIcon} from 'lucide-react';

type Tab<T extends string> = {name: T; Icon: LucideIcon};

/** The Scene settings tab bar: one row that scrolls sideways when the inspector is
 *  narrow. Tabs that do not fit are also listed in a "More" menu, so every tab stays one
 *  click away. Arrow keys, Home and End move between tabs (roving tabindex). */
export function InspectorTabs<T extends string>({tabs, active, onSelect, idPrefix, panelId}: {
  tabs: Tab<T>[]; active: T; onSelect: (name: T) => void; idPrefix: string; panelId: string;
}) {
  const listRef = useRef<HTMLDivElement>(null);
  const moreRef = useRef<HTMLDivElement>(null);
  const [overflow, setOverflow] = useState<T[]>([]);
  const [menuOpen, setMenuOpen] = useState(false);
  const names = tabs.map(t => t.name).join('|');

  const measure = useCallback(() => {
    const list = listRef.current;
    if (!list) return;
    const width = list.clientWidth;
    if (!width) {setOverflow(o => o.length ? [] : o); return;}   // not laid out (hidden scene editor)
    const hidden: T[] = [];
    list.querySelectorAll<HTMLElement>('[role="tab"]').forEach(el => {
      const left = el.offsetLeft - list.scrollLeft, right = left + el.offsetWidth;
      if (left < -1 || right > width + 1) hidden.push(el.dataset.tab as T);
    });
    setOverflow(o => o.join('|') === hidden.join('|') ? o : hidden);
  }, []);

  useLayoutEffect(() => {measure();}, [measure, names]);
  useEffect(() => {
    const list = listRef.current;
    window.addEventListener('resize', measure);
    let ro: ResizeObserver | undefined;
    if (list && typeof ResizeObserver !== 'undefined') {ro = new ResizeObserver(() => measure()); ro.observe(list);}
    return () => {window.removeEventListener('resize', measure); ro?.disconnect();};
  }, [measure]);
  useEffect(() => {
    if (!menuOpen) return;
    const close = (e: MouseEvent) => {if (!moreRef.current?.contains(e.target as Node)) setMenuOpen(false);};
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [menuOpen]);
  useEffect(() => {if (!overflow.length) setMenuOpen(false);}, [overflow.length]);

  const reveal = (name: T) => {
    const el = document.getElementById(`${idPrefix}-${name}-tab`);
    (el as any)?.scrollIntoView?.({block: 'nearest', inline: 'nearest'});
    return el;
  };
  const choose = (name: T, focus = false) => {
    onSelect(name);
    requestAnimationFrame(() => {const el = reveal(name); if (focus) el?.focus(); measure();});
  };
  const onKey = (e: React.KeyboardEvent, name: T) => {
    const i = tabs.findIndex(t => t.name === name);
    const next = e.key === 'ArrowRight' ? (i + 1) % tabs.length : e.key === 'ArrowLeft' ? (i - 1 + tabs.length) % tabs.length
      : e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1 : -1;
    if (next < 0) return;
    e.preventDefault();
    const target = tabs[next].name;
    onSelect(target);
    document.getElementById(`${idPrefix}-${target}-tab`)?.focus();
    reveal(target);
  };
  const menuKey = (e: React.KeyboardEvent) => {
    const items = Array.from(moreRef.current?.querySelectorAll<HTMLElement>('[role="menuitemradio"]') || []);
    const at = items.indexOf(document.activeElement as HTMLElement);
    if (e.key === 'Escape') {e.preventDefault(); e.stopPropagation(); setMenuOpen(false); moreRef.current?.querySelector<HTMLElement>('.inspector-tabs-more-button')?.focus();}
    else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {e.preventDefault(); items[(at + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length]?.focus();}
  };

  return <div className={`inspector-tabbar ${overflow.length ? 'has-overflow' : ''}`}>
    <div className="inspector-tabs" role="tablist" aria-label="Scene tools" ref={listRef} onScroll={measure}>
      {tabs.map(({name, Icon}) => <button key={name} role="tab" data-tab={name} id={`${idPrefix}-${name}-tab`} aria-controls={panelId}
        aria-selected={active === name} className={active === name ? 'active' : ''} title={name}
        onClick={() => choose(name)} onKeyDown={e => onKey(e, name)} tabIndex={active === name ? 0 : -1}>
        <Icon size={16}/><span>{name}</span></button>)}
    </div>
    {overflow.length > 0 && <div className="inspector-tabs-more" ref={moreRef} onKeyDown={menuKey}>
      <button className={`inspector-tabs-more-button ${overflow.includes(active) ? 'active' : ''}`} aria-haspopup="menu" aria-expanded={menuOpen}
        aria-label={`More scene tools (${overflow.length} hidden)`} title="Tabs that do not fit"
        onClick={() => {setMenuOpen(o => !o); requestAnimationFrame(() => moreRef.current?.querySelector<HTMLElement>('[role="menuitemradio"]')?.focus());}}>
        More <ChevronDown size={13}/></button>
      {menuOpen && <div className="inspector-tabs-menu" role="menu" aria-label="More scene tools">
        {tabs.filter(t => overflow.includes(t.name)).map(({name, Icon}) => <button key={name} role="menuitemradio" aria-checked={active === name}
          onClick={() => {setMenuOpen(false); choose(name, true);}}><Icon size={14}/>{name}</button>)}
      </div>}
    </div>}
  </div>;
}
