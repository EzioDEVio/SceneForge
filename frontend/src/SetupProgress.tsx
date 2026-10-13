import React from 'react';
import {createPortal} from 'react-dom';
import {Captions, CheckCircle2, ChevronLeft, ChevronRight, Clapperboard, Cpu, Film, Keyboard, Loader2, Map, Mic, Minimize2, Palette, Sparkles, Type, VolumeX, X} from 'lucide-react';

type Setup = {status: string; completed: number; total: number; current: string; part?: number; step?: string; log: string[]; error: string; queue?: string[]};
const NAMES: Record<string, string> = {whisper: 'Whisper captions', kokoro: 'Kokoro voices', stable_diffusion: 'Stable Diffusion pictures', chatterbox: 'Chatterbox voices'};
const ICONS: Record<string, typeof Cpu> = {whisper: Captions, kokoro: Sparkles, stable_diffusion: Cpu, chatterbox: Mic};

// While engines download: what SceneForge can do, one card at a time.
const TOUR: {Icon: typeof Cpu; title: string; text: string; where: string; tint: string; img?: string}[] = [
  {Icon: Type, title: 'Titles with your video inside the letters', text: 'Video inside text and Textured titles open in their own window with a live preview. Drag the title on the picture to place it.', where: 'Overlays → Creative titles', tint: '#57C7DD', img: '/tour/titles.webp'},
  {Icon: Clapperboard, title: 'Drop anything, anywhere', text: 'The Free timeline takes scenes, pictures, video, text and sound on any track. Box-select to move several together.', where: 'Timeline → Free timeline', tint: '#7C9CFF', img: '/tour/timeline.webp'},
  {Icon: Captions, title: 'Captions that write themselves', text: 'Auto captions turn narration, dialogue or a song into timed, editable caption clips in many languages.', where: 'Text → Auto captions', tint: '#F2B84B', img: '/tour/captions.webp'},
  {Icon: Keyboard, title: 'Typewriter titles with keystroke sound', text: 'Captions type themselves letter by letter. Pick a speed and add the keystroke sound.', where: 'Text → Typewriter', tint: '#E98B6D', img: '/tour/typewriter.webp'},
  {Icon: Palette, title: 'Looks, old film and colour', text: 'Classic looks, film grades, old-film scratches and flicker, adjustment sliders and your own .cube LUTs.', where: 'Effects → Looks · Old film · Adjust & LUT', tint: '#B98CF2', img: '/tour/looks.webp'},
  {Icon: VolumeX, title: 'Bleep or mute words', text: 'Censor a word in the narration, in a video’s own sound or in any timeline clip, with a bleep or silence.', where: 'Audio → Censor words', tint: '#F07C8E', img: '/tour/censor.webp'},
  {Icon: Map, title: 'Map routes and arrows', text: 'Animate a journey between places, draw arrows and circles, and blur faces or number plates.', where: 'Effects → More effects', tint: '#5FD1A0'},
  {Icon: Film, title: 'Ready for every platform', text: 'Export for YouTube, TikTok, Reels and Instagram, or as a small file to share. Press Ctrl+/ any time for all shortcuts.', where: 'Export video', tint: '#57C7DD', img: '/tour/export.webp'},
];
const TIPS = ['Press Ctrl+/ to see every keyboard shortcut.', 'Ctrl+S saves a restore point you can go back to.', 'Hover a look to preview it on the picture, click to apply.',
  'Drag the line above the timeline to give the preview more room.', 'Right-click a clip on the timeline for more actions.', 'Your projects and models stay on this computer.'];

export function SetupProgress() {
  // Render inside the editor or project list so the current theme's colours apply.
  const host = () => document.querySelector('.studio-shell, .project-home') || document.body;
  const [state, setState] = React.useState<Setup | null>(null);
  const [hidden, setHidden] = React.useState(() => {try {return sessionStorage.getItem('sf.setupHidden') === '1';} catch {return false;}});
  const [slide, setSlide] = React.useState(0);
  const [finished, setFinished] = React.useState(false);
  const [failed, setFailed] = React.useState(false);
  const last = React.useRef('');
  React.useEffect(() => {
    let active = true, timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const r = await fetch('/api/local-ai/setup'); const s = await r.json();
        if (active && r.ok) {
          setState(s);
          if (last.current === 'running' && s.status === 'done') {setFinished(true); setHidden(false);}
          if (last.current === 'running' && s.status === 'error') {setFailed(true); setHidden(false);}
          if (s.status === 'running' && last.current !== 'running') {setFinished(false); setFailed(false);}
          last.current = s.status;
        }
      } catch {/* the app shows connection problems elsewhere */}
      if (active) timer = setTimeout(poll, last.current === 'running' ? 2000 : 6000);
    };
    void poll();
    return () => {active = false; clearTimeout(timer);};
  }, []);
  const running = state?.status === 'running';
  const reduce = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  React.useEffect(() => {if (!running || hidden || reduce) return; const t = setInterval(() => setSlide(i => (i + 1) % TOUR.length), 8000); return () => clearInterval(t);}, [running, hidden, reduce]);
  const hide = (value: boolean) => {setHidden(value); try {sessionStorage.setItem('sf.setupHidden', value ? '1' : '0');} catch {/* ignore */}};
  if (!state || (!running && !finished && !failed)) return null;
  const total = Math.max(1, state.total);
  const pct = Math.min(100, Math.round(((state.completed + (running ? Math.min(.95, state.part || 0) : 0)) / total) * 100));
  const done = finished && !running;
  const close = () => {setFinished(false); setFailed(false); hide(false);};
  if (hidden && !done && !failed) {
    return createPortal(<button className="setup-pill" onClick={() => hide(false)} aria-label={`Setting up free AI, ${pct}% done. Show progress`}>
      <span className="setup-pill-ring" style={{'--p': `${pct}%`} as React.CSSProperties}><span>{pct}%</span></span>
      <span><b>Setting up free AI</b><small>{NAMES[state.current] || 'Working'} · keep SceneForge open</small></span>
    </button>, host());
  }
  const t = TOUR[slide];
  const queue = state.queue?.length ? state.queue : Object.keys(NAMES).filter(c => state.current === c);
  const finishedOf = (c: string) => queue.indexOf(c) < state.completed;
  return createPortal(<div className="setup-backdrop" role="dialog" aria-modal="true" aria-label="Setting up free AI">
    <section className="setup-screen">
      <header>
        <span className="setup-title">{done ? <CheckCircle2 size={20} aria-hidden/> : failed ? <X size={20} aria-hidden/> : <Loader2 size={20} className="spin" aria-hidden/>} {done ? 'Free AI is ready' : failed ? 'Setup needs attention' : 'Setting up free AI on this computer'}</span>
        {done || failed ? <button className="icon-reset" aria-label="Close" onClick={close}><X size={18}/></button>
              : <button className="text-btn" onClick={() => hide(true)}><Minimize2 size={14} aria-hidden/> Keep working</button>}
      </header>
      <div className="setup-body">
        <div className="setup-progress">
          <div className="setup-percent" aria-hidden>{pct}<small>%</small></div>
          <div className={`setup-bar ${done ? 'done' : ''}`} role="progressbar" aria-label="Setup progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}><span style={{width: `${pct}%`}}/></div>
          <p className="setup-step" role="status">{done ? 'Everything is installed and connected. Pick it in Voice & narration or Generate image.' : failed ? state.error : `${NAMES[state.current] || 'Preparing'} · ${state.step || 'Working'}`}</p>
          {failed && <button className="btn btn-primary" onClick={() => {close(); window.dispatchEvent(new CustomEvent('sceneforge-open-ai-engines', {detail: 'sd'}));}}>Open AI Engines to retry</button>}
          <ul className="setup-steps">{queue.map(c => {const Icon = ICONS[c] || Cpu; const isNow = running && state.current === c;
            const ok = !isNow && (finishedOf(c) || done);
            return <li key={c} className={isNow ? 'now' : ok ? 'ok' : ''}><Icon size={15} aria-hidden/><span>{NAMES[c]}</span><em>{isNow ? 'in progress' : ok ? 'ready' : 'waiting'}</em></li>;})}</ul>
          {running && <p className="hint">First setup can take 10–40 minutes depending on your connection. You can keep editing; this keeps running in the background.</p>}
          {!done && <details className="setup-log" open={failed}><summary>Details</summary><pre>{state.log.slice(-12).join('\n')}</pre></details>}
        </div>
        <div className="setup-tour" aria-roledescription="carousel" aria-label="What you can do in SceneForge">
          <div className="setup-art" style={{'--tint': t.tint} as React.CSSProperties} aria-hidden>
            {t.img ? <img src={t.img} alt="" loading="lazy" onError={e => {e.currentTarget.style.display = 'none';}}/> : <><span className="setup-art-grid"/><span className="setup-art-orb"/><t.Icon size={64} strokeWidth={1.4}/></>}
            {t.img && <span className="setup-art-badge"><t.Icon size={16} aria-hidden/></span>}
          </div>
          <div className="setup-card" aria-live={reduce ? 'polite' : 'off'}>
            <small>{slide + 1} of {TOUR.length} · {t.where}</small>
            <h3>{t.title}</h3>
            <p>{t.text}</p>
          </div>
          <div className="setup-nav">
            <button className="icon-reset" aria-label="Previous feature" onClick={() => setSlide(i => (i + TOUR.length - 1) % TOUR.length)}><ChevronLeft size={18}/></button>
            <span className="setup-dots">{TOUR.map((_, i) => <button key={i} aria-label={`Feature ${i + 1}`} aria-current={i === slide} onClick={() => setSlide(i)}/>)}</span>
            <button className="icon-reset" aria-label="Next feature" onClick={() => setSlide(i => (i + 1) % TOUR.length)}><ChevronRight size={18}/></button>
          </div>
          <p className="setup-tip"><b>Tip</b> {TIPS[slide % TIPS.length]}</p>
        </div>
      </div>
    </section>
  </div>, host());
}
