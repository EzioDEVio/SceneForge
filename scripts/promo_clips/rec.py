"""Recording harness: drives the real SceneForge editor in Chromium and records it with a CDP
screencast (high-quality JPEG frames with timestamps). A drawn pointer + click ripple is injected
because headless Chromium has no visible cursor. Every step logs a caption and a focus rectangle
for the editing pass (edit.py)."""
import base64, json, math, pathlib, sys, tempfile, time
sys.path.insert(0, '/home/claude/sf07/SceneForge/scripts')
from capture_readme_screenshots import Editor, webm_bridge  # reuse the README capture helpers
from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8765'
VW, VH = 1600, 900

CURSOR_JS = r"""
(() => {
  if (window.__sfCursor) return; window.__sfCursor = 1;
  const add = () => {
    const c = document.createElement('div'); c.id = '__cur';
    c.innerHTML = '<svg width="30" height="30" viewBox="0 0 24 24"><path d="M3 2l7.5 19 2.6-7.6L21 10.8z" fill="#fff" stroke="#111" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    Object.assign(c.style, {position:'fixed', left:'-50px', top:'-50px', zIndex: 2147483647, pointerEvents:'none', filter:'drop-shadow(0 2px 3px rgba(0,0,0,.45))', transition:'transform .08s'});
    document.documentElement.appendChild(c);
    const st = document.createElement('style');
    st.textContent = '@keyframes __rip{from{transform:translate(-50%,-50%) scale(.2);opacity:.95}to{transform:translate(-50%,-50%) scale(1);opacity:0}}' +
      '.__rip{position:fixed;width:64px;height:64px;border-radius:50%;border:4px solid #FFC83D;background:rgba(255,200,61,.25);pointer-events:none;z-index:2147483646;animation:__rip .55s ease-out forwards}';
    document.documentElement.appendChild(st);
    addEventListener('mousemove', e => { c.style.left = (e.clientX - 3) + 'px'; c.style.top = (e.clientY - 2) + 'px'; }, true);
    addEventListener('mousedown', e => { c.style.transform = 'scale(.85)';
      const r = document.createElement('div'); r.className = '__rip'; r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px';
      document.documentElement.appendChild(r); setTimeout(() => r.remove(), 700); }, true);
    addEventListener('mouseup', () => { c.style.transform = ''; }, true);
  };
  if (document.documentElement) add(); else addEventListener('DOMContentLoaded', add);
})();
"""


class Rec:
    def __init__(self, name):
        self.name = name
        self.dir = pathlib.Path('/tmp/claude-0/clips/raw') / name
        if self.dir.exists():
            for f in self.dir.iterdir(): f.unlink()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.frames, self.events = [], []
        self.mx, self.my = VW * 0.6, VH * 0.6
        self.recording = False

    # ---------- lifecycle
    def __enter__(self):
        self.p = sync_playwright().start()
        self.b = self.p.chromium.launch()
        self.ctx = self.b.new_context(viewport={'width': VW, 'height': VH}, device_scale_factor=1.2)
        webm_bridge(self.ctx, pathlib.Path(tempfile.mkdtemp(prefix='sf-webm-')))
        self.ctx.add_init_script(CURSOR_JS)
        self.pg = self.ctx.new_page()
        self.ed = Editor(self.pg, BASE)
        self.cdp = self.ctx.new_cdp_session(self.pg)
        self.cdp.on('Page.screencastFrame', self._frame)
        return self

    def __exit__(self, *a):
        if self.recording: self.stop()
        (self.dir / 'events.json').write_text(json.dumps({'frames': self.frames, 'events': self.events}, indent=1))
        self.b.close(); self.p.stop()

    def _frame(self, f):
        if not self.recording: return
        i = len(self.frames)
        path = self.dir / f'f{i:05d}.jpg'
        path.write_bytes(base64.b64decode(f['data']))
        self.frames.append([path.name, f['metadata']['timestamp']])
        try: self.cdp.send('Page.screencastFrameAck', {'sessionId': f['sessionId']})
        except Exception: pass

    def start(self):
        self.recording = True
        self.t0 = time.time()
        self.cdp.send('Page.startScreencast', {'format': 'jpeg', 'quality': 92, 'maxWidth': 1920, 'maxHeight': 1080, 'everyNthFrame': 1})
        self.pg.mouse.move(self.mx, self.my)
        self.wait(400)

    def stop(self):
        self.wait(300)
        self.cdp.send('Page.stopScreencast'); self.recording = False

    # ---------- marks for the editing pass
    def mark(self, kind, **kw):
        self.events.append({'t': time.time(), 'kind': kind, **kw})

    def caption(self, text, focus=None, zoom=None):
        """New on-screen step caption. focus = (x, y, w, h) page px to frame, or a locator."""
        if focus is not None and not isinstance(focus, (tuple, list)):
            bb = focus.bounding_box(); focus = (bb['x'], bb['y'], bb['width'], bb['height'])
        self.mark('caption', text=text, focus=focus, zoom=zoom)

    def focus(self, focus, zoom=None):
        if not isinstance(focus, (tuple, list)):
            bb = focus.bounding_box(); focus = (bb['x'], bb['y'], bb['width'], bb['height'])
        self.mark('focus', focus=focus, zoom=zoom)

    # ---------- human-like input
    def wait(self, ms):
        # keep the event loop pumping so screencast frames arrive
        end = time.time() + ms / 1000
        while time.time() < end:
            self.pg.wait_for_timeout(min(50, max(1, int((end - time.time()) * 1000))))

    def _glide(self, sx, sy, x, y, ms):
        t0 = time.time(); d = ms / 1000
        while True:
            t = min(1.0, (time.time() - t0) / d); e = t * t * (3 - 2 * t)
            self.pg.mouse.move(sx + (x - sx) * e, sy + (y - sy) * e)
            if t >= 1: break
            self.pg.wait_for_timeout(10)
        self.mx, self.my = x, y

    def move(self, x, y, ms=650):
        self._glide(self.mx, self.my, x, y, ms)

    def center(self, loc, fx=0.5, fy=0.5):
        loc.scroll_into_view_if_needed(); self.wait(150)
        bb = loc.bounding_box()
        return bb['x'] + bb['width'] * fx, bb['y'] + bb['height'] * fy

    def click(self, loc, fx=0.5, fy=0.5, ms=650, after=500):
        x, y = self.center(loc, fx, fy)
        self.move(x, y, ms); self.wait(120)
        self.mark('click', x=x, y=y)
        self.pg.mouse.down(); self.wait(70); self.pg.mouse.up()
        self.wait(after)

    def click_xy(self, x, y, ms=650, after=500):
        self.move(x, y, ms); self.wait(120); self.mark('click', x=x, y=y)
        self.pg.mouse.down(); self.wait(70); self.pg.mouse.up(); self.wait(after)

    def drag(self, x0, y0, x1, y1, ms=1200, after=500):
        self.move(x0, y0); self.wait(150); self.mark('click', x=x0, y=y0)
        self.pg.mouse.down(); self.wait(120)
        self._glide(x0, y0, x1, y1, ms)
        self.wait(120); self.pg.mouse.up(); self.wait(after)

    def type(self, loc, text, delay=70, after=400):
        self.click(loc, after=150)
        self.pg.keyboard.press('Control+A'); self.pg.keyboard.press('Delete')
        for ch in text:
            self.pg.keyboard.type(ch); self.pg.wait_for_timeout(delay)
        self.wait(after)

    def scene_id(self, title):
        import requests
        p = requests.get(f'{BASE}/api/projects').json()
        for pr in p:
            full = requests.get(f"{BASE}/api/projects/{pr['id']}").json()
            for sc in full['scenes']:
                if sc['title'] == title and pr['title'] == 'Night City Stories': return sc
        raise KeyError(title)

    def save_result(self, title, start=0.0, secs=6.0):
        """Download the scene's rendered MP4 so the edit can end on the real result, full screen."""
        import requests
        sc = self.scene_id(title)
        r = requests.get(f"{BASE}/api/assets/{sc['rendered_asset_id']}/stream", timeout=300); r.raise_for_status()
        (self.dir / 'result.mp4').write_bytes(r.content)
        (self.dir / 'result.json').write_text(json.dumps({'start': start, 'secs': secs}))

    def grab_audio(self, url, name):
        """Fetch audio the browser played (it is not in the screencast) and mark it for the mix."""
        import requests
        r = requests.get(BASE + url, timeout=120); r.raise_for_status()
        (self.dir / name).write_bytes(r.content)
        self.mark('audio', file=name)

    def park(self):
        """Move the pointer out of the way (bottom-right corner of the preview)."""
        self.move(VW * 0.52, VH * 0.6, 500)
