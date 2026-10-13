import React from 'react';
import {Search, X} from 'lucide-react';

/** One search box for the whole app: icon inside the field, a clear button while there is
 *  text, Escape to clear (except inside dialogs, where Escape closes), and an optional live count of what matched. */
export function SearchField({value, onChange, label, placeholder, count, className = '', autoFocus, compact, escapeClears = true}: {
  value: string; onChange: (value: string) => void; label: string; placeholder?: string;
  count?: number; className?: string; autoFocus?: boolean; compact?: boolean; escapeClears?: boolean;
}) {
  const input = React.useRef<HTMLInputElement>(null);
  const query = value.trim();
  return <div className={`search-field ${compact ? 'compact' : ''} ${query ? 'has-value' : ''} ${className}`.trim()}>
    <Search className="search-field-icon" size={compact ? 14 : 16} aria-hidden/>
    <input ref={input} type="search" aria-label={label} placeholder={placeholder} value={value} autoFocus={autoFocus}
      onChange={e => onChange(e.target.value)}
      onKeyDown={e => {if (escapeClears && e.key === 'Escape' && value) {e.preventDefault(); e.stopPropagation(); onChange('');}}}/>
    {query && count !== undefined && <span className={`search-field-count ${count ? '' : 'none'}`} aria-live="polite">{count ? `${count} found` : 'No matches'}</span>}
    {value && <button type="button" className="search-field-clear" aria-label={`Clear ${label.toLowerCase()}`} title={escapeClears ? "Clear (Esc)" : "Clear"}
      onClick={() => {onChange(''); input.current?.focus();}}><X size={compact ? 13 : 14} aria-hidden/></button>}
  </div>;
}
