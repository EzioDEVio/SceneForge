import React, {useEffect, useRef} from 'react';
import type {FilmLook} from './api';

// Mirrors FILM_DEFAULTS in backend/app/render/filters.py.
export const FILM_DEFAULTS: FilmLook = {scratches: 60, dust: 50, flicker: 40, weave: 35, sound: 0, fps: 18, tone: 'bw'};
export const FILM_STYLES: {name: string; hint: string; film: FilmLook}[] = [
  {name: 'WWII newsreel', hint: 'Black & white, heavy scratches, strong flicker', film: {scratches: 75, dust: 60, flicker: 55, weave: 45, sound: 40, fps: 18, tone: 'bw'}},
  {name: '8mm home movie', hint: 'Faded colour, dust, hand-held projector wobble', film: {scratches: 35, dust: 55, flicker: 35, weave: 60, sound: 50, fps: 18, tone: 'faded'}},
  {name: 'Silent era', hint: 'Sepia, 16 fps, worn print', film: {scratches: 85, dust: 75, flicker: 70, weave: 55, sound: 45, fps: 16, tone: 'sepia'}},
];

export function filmToneFilter(film?: FilmLook | null): string {
  if (!film) return '';
  return {color: '', faded: 'saturate(0.6) contrast(0.92) brightness(1.03) sepia(0.12)', sepia: 'sepia(0.9) contrast(1.08)', bw: 'grayscale(1) contrast(1.22) brightness(0.98)'}[film.tone] || '';
}

type Scratch = {x: number; drift: number; wobble: number; phase: number; life: number; age: number; width: number; bright: boolean; level: number; top: number; bottom: number};

/** Live approximation of the old-film look over the editor preview: scratches,
 *  dust, hairs and flicker drawn on a canvas at the film frame rate, plus gate
 *  weave applied to the picture. The render uses the real FFmpeg version. */
export function FilmPreview({film}: {film: FilmLook}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const el = canvas.current; if (!el) return;
    const ctx = el.getContext('2d'); if (!ctx) return;
    const media = () => Array.from(el.parentElement?.querySelectorAll<HTMLElement>('.canvas-media') || []);
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    const fps = film.fps || 24, s = film.scratches / 100, d = film.dust / 100;
    let scratches: Scratch[] = [], frame = 0, raf = 0, last = 0;
    const draw = () => {
      const w = el.width = Math.min(960, el.clientWidth || 640), h = el.height = Math.round(w * (el.clientHeight || 360) / (el.clientWidth || 640));
      const k = w / 960;
      ctx.clearRect(0, 0, w, h);
      // flicker
      if (film.flicker) {const f = (Math.random() - .5) * .18 * film.flicker / 100; ctx.fillStyle = f > 0 ? `rgba(255,255,255,${f})` : `rgba(0,0,0,${-f})`; ctx.fillRect(0, 0, w, h);}
      // scratches: spawn, drift, fade out
      if (Math.random() < (0.05 + 0.4 * s) / 2 && s > 0) scratches.push({x: Math.random() * w, drift: (Math.random() - .5) * .5 * k, wobble: (.3 + Math.random() * 1.3) * k, phase: Math.random() * 6, life: Math.round((0.4 + Math.random() * 2) * fps), age: 0, width: [0.8, 1.2, 1.8][Math.floor(Math.random() * 3)] * k * 1.4, bright: Math.random() < .75, level: (.35 + .45 * Math.random()) * (.6 + .6 * s), top: Math.random() < .3 ? Math.random() * h * .6 : 0, bottom: Math.random() < .3 ? h * (.4 + Math.random() * .6) : h});
      scratches = scratches.filter(sc => sc.age++ < sc.life);
      for (const sc of scratches) {
        if (Math.random() < .08) continue;
        const x = sc.x + sc.drift * sc.age + sc.wobble * Math.sin(sc.age * .7 + sc.phase);
        ctx.fillStyle = sc.bright ? `rgba(255,255,255,${sc.level})` : `rgba(0,0,0,${sc.level * .8})`;
        ctx.fillRect(x, sc.top, sc.width, sc.bottom - sc.top);
      }
      // dust and the odd hair
      const specks = Math.round((1 + 18 * d) * (0.5 + Math.random()));
      for (let i = 0; i < specks && d > 0; i++) {
        const dark = Math.random() < .7; ctx.fillStyle = dark ? `rgba(0,0,0,${.4 + .5 * Math.random()})` : `rgba(255,255,255,${.4 + .5 * Math.random()})`;
        ctx.beginPath(); ctx.arc(Math.random() * w, Math.random() * h, (1 + Math.random() * 2.4) * k, 0, 6.3); ctx.fill();
      }
      if (d > 0 && Math.random() < .03 * d) {
        let x = Math.random() * w, y = Math.random() * h, a = Math.random() * 6.3;
        ctx.strokeStyle = 'rgba(0,0,0,.55)'; ctx.lineWidth = 1.1 * k; ctx.beginPath(); ctx.moveTo(x, y);
        for (let i = 0; i < 40; i++) {a += (Math.random() - .5) * .4; x += Math.cos(a) * 1.5 * k; y += Math.sin(a) * 1.5 * k; ctx.lineTo(x, y);} ctx.stroke();
      }
      // gate weave (and the occasional frame slip) moves the picture itself
      const wv = film.weave / 100;
      const dx = wv * .4 * (Math.sin(frame * .37 + 1.3) * .6 + (Math.random() - .5) * .8);
      const dy = wv * .6 * (Math.sin(frame * .29) * .6 + (Math.random() - .5) * .8) + (Math.random() < .008 * wv ? 4 * wv : 0);
      for (const m of media()) m.style.transform = wv ? `translate(${dx}%, ${dy}%) scale(${1 + 0.02 * wv + 0.02})` : '';
      frame++;
    };
    const loop = (t: number) => {if (t - last >= 1000 / fps) {last = t; draw();} raf = requestAnimationFrame(loop);};
    if (reduce) draw(); else raf = requestAnimationFrame(loop);
    return () => {cancelAnimationFrame(raf); for (const m of media()) m.style.transform = '';};
  }, [film.scratches, film.dust, film.flicker, film.weave, film.fps]);
  return <canvas ref={canvas} className="film-preview" aria-hidden="true"/>;
}
