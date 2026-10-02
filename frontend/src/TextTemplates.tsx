// Ready-made title templates (0.9.0): intro, outro, lower third, chapter and quote.
// A template simply adds ordinary text layers (with animations) that you then edit like any title.
import React from 'react';
import {LayoutTemplate} from 'lucide-react';
import type {TextLayer} from './api';
import {FeatureHelp} from './FeatureHelp';

type Part = Omit<TextLayer, 'id' | 'start_ms' | 'end_ms'> & {start_ms?: number; end_ms?: number};
export type TextTemplate = {id: string; name: string; hint: string; parts: Part[]};

const base = {bold: true, color: '#FFFFFF', shadow: 4, outline_width: 0, spacing: 0, animation_ms: 900, exit_ms: 400} as const;

export const TEXT_TEMPLATES: TextTemplate[] = [
  {id: 'lower-third', name: 'Lower third', hint: 'Name and role in the bottom-left corner, like a TV interview.', parts: [
    {...base, kind: 'text_plus', text: 'Your Name', x: 7, y: 79, size: 64, family: 'Poppins', align: 'left', animation: 'slide', start_ms: 300, end_ms: 5000},
    {...base, kind: 'text', text: 'Title or role', x: 7, y: 87, size: 38, bold: false, color: '#FFD84D', family: 'Poppins', align: 'left', animation: 'fade', start_ms: 600, end_ms: 5000},
  ]},
  {id: 'intro', name: 'Intro title', hint: 'A big opening title with a small line underneath.', parts: [
    {...base, kind: 'text_plus', text: 'YOUR TITLE', x: 50, y: 44, size: 150, family: 'Bebas Neue', spacing: 10, animation: 'reveal-iris', animation_ms: 1200},
    {...base, kind: 'text', text: 'a film by Your Name', x: 50, y: 60, size: 42, bold: false, color: '#D9DEE8', family: 'Poppins', animation: 'fade', start_ms: 900},
  ]},
  {id: 'outro', name: 'Outro / end card', hint: 'Thank viewers and ask them to follow or subscribe.', parts: [
    {...base, kind: 'text_plus', text: 'Thanks for watching', x: 50, y: 42, size: 96, family: 'Poppins', animation: 'letters-fade'},
    {...base, kind: 'text_plus', text: 'Subscribe for more', x: 50, y: 58, size: 48, color: '#FF4F6D', family: 'Poppins', animation: 'bounce', start_ms: 900},
  ]},
  {id: 'chapter', name: 'Chapter heading', hint: 'A numbered chapter with its name, for long videos.', parts: [
    {...base, kind: 'text', text: 'CHAPTER 1', x: 50, y: 40, size: 44, color: '#FFD84D', family: 'Poppins', spacing: 12, animation: 'fade'},
    {...base, kind: 'text_plus', text: 'The beginning', x: 50, y: 53, size: 110, family: 'Bebas Neue', animation: 'letters-fade', start_ms: 400},
  ]},
  {id: 'quote', name: 'Quote', hint: 'A quotation in a wrapped box with the speaker’s name.', parts: [
    {...base, kind: 'text_box', text: '“Write a memorable quote here.”', x: 50, y: 45, size: 58, bold: false, family: 'Amiri', box_width: 70, animation: 'words-fade', animation_ms: 1600},
    {...base, kind: 'text', text: '— Speaker name', x: 50, y: 66, size: 36, bold: false, color: '#D9DEE8', family: 'Poppins', animation: 'fade', start_ms: 1400},
  ]},
];

/** Turn a template into text layers placed from `at` ms (end 0 = until the scene ends). */
export function templateLayers(t: TextTemplate, at = 0, newId: () => string = () => crypto.randomUUID()): TextLayer[] {
  return t.parts.map(p => ({...p, id: newId(), start_ms: at + (p.start_ms || 0), end_ms: p.end_ms ? at + p.end_ms : 0} as TextLayer));
}

export function TextTemplatePicker({count, max, onAdd}: {count: number; max: number; onAdd: (layers: TextLayer[], name: string) => void}) {
  return <div className="text-templates" role="group" aria-label="Title templates">
    <div className="section-heading"><h4><LayoutTemplate size={14}/> Templates</h4>
      <FeatureHelp compact title="Title templates" description="Ready-made titles: a lower third, an intro, an end card, a chapter heading or a quote. Each adds normal text layers you can edit." steps="Click a template, then change the words in its layers below. Move them on the preview, or change the font, colour and animation like any title."/></div>
    <div className="text-template-grid">{TEXT_TEMPLATES.map(t => <button key={t.id} className="btn text-template" title={t.hint} aria-label={`Add ${t.name} template`}
      disabled={count + t.parts.length > max} onClick={() => onAdd(templateLayers(t), t.name)}><strong>{t.name}</strong><small>{t.hint}</small></button>)}</div>
  </div>;
}
