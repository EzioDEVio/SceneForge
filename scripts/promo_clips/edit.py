"""Editing pass: turns a raw screencast recording (raw/<name>/) into social clips.

  out/<name>_16x9.mp4  1920x1080  smooth zooms to each step, caption bar, intro + end card
  out/<name>_9x16.mp4  1080x1920  header with the feature name, zoomed content, big captions

Usage: python3 edit.py <name> [--only 16x9|9x16] [--preview SECONDS]
Per-clip settings live in CLIPS below (title, speed-ups in source seconds)."""
import bisect, json, math, pathlib, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path('/tmp/claude-0/clips')
FPS = 30
SRC_W, SRC_H = 1600, 900
FONT = '/usr/share/fonts/truetype/google-fonts/Poppins-%s.ttf'
LOGO = Image.open('/home/claude/sf07/SceneForge/frontend/dist/logo.png').convert('RGBA')
VIOLET = (124, 92, 255); GOLD = (255, 200, 61); INK = (14, 12, 24); WHITE = (255, 255, 255)
REPO = 'github.com/EzioDEVio/SceneForge'

CLIPS = {
    '1_keyframes': dict(title='Keyframe animation', kicker='Make titles move', speed=[], tail=5.5, v={
        '1. Click the timeline where the move starts': dict(vfocus=(290, 150, 720, 750)),
        '3. Move the playhead later': dict(vfocus=(290, 150, 720, 750)),
        '4. Move or resize the title': dict(vfocus=(1045, 230, 555, 480), pip=(405, 165, 470, 240)),
        'A second keyframe is added for you': dict(pip=(405, 165, 470, 240)),
        '5. Scrub the timeline to see it glide': dict(vfocus=(290, 150, 720, 750)),
        '6. Render the scene': dict(vfocus=(380, 150, 720, 450)),
    }),
    '2_typewriter': dict(title='Typewriter captions', kicker='Words that type themselves', speed=[], tail=6.0),
    '3_video_in_text': dict(title='Video inside text', kicker='Your footage, inside the letters', speed=[], tail=6.0),
    '4_caption_styles': dict(title='Caption styles', kicker='Captions that pop, in one click', speed=[], tail=6.0),
    '5_title_templates': dict(title='Title templates', kicker='Pro titles in one click', speed=[], tail=6.0),
    '6_vertical_export': dict(title='Vertical Shorts', kicker='One video, every platform', speed=[], tail=4.0),
}


def font(w, s): return ImageFont.truetype(FONT % w, s)


def ease(t): t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ timing
class Timeline:
    """Maps output time -> source time, cutting skip regions and speeding up configured spans."""
    def __init__(self, frames, events, cfg):
        self.t0 = frames[0][1]
        self.ts = [f[1] - self.t0 for f in frames]
        self.names = [f[0] for f in frames]
        end = self.ts[-1]
        ev = [dict(e, s=e['t'] - self.t0) for e in events]
        cuts, open_ = [], None
        for e in ev:
            if e['kind'] == 'skip_start': open_ = e['s'] + 0.35
            if e['kind'] == 'skip_end' and open_ is not None: cuts.append((open_, e['s'])); open_ = None
        speeds, sp = list(cfg.get('speed', [])), None
        for e in ev:
            if e['kind'] == 'speed_start': sp = (e['s'], e.get('x', 3.0))
            if e['kind'] == 'speed_end' and sp: speeds.append((sp[0], e['s'], sp[1])); sp = None
        segs, s = [], 0.0
        marks = sorted([(a, b, 'cut', 0) for a, b in cuts] + [(a, b, 'speed', k) for a, b, k in speeds])
        for a, b, kind, k in marks:
            if a > s: segs.append((s, a, 1.0))
            if kind == 'speed': segs.append((a, b, k))
            s = b
        segs.append((s, end, 1.0))
        self.segs = [(a, b, k) for a, b, k in segs if b > a]
        self.out_starts, acc = [], 0.0
        for a, b, k in self.segs:
            self.out_starts.append(acc); acc += (b - a) / k
        self.duration = acc
        for e in ev:
            e.update(cfg.get('v', {}).get(e.get('text'), {}))
        self.events = ev

    def src(self, o):
        i = max(0, bisect.bisect_right(self.out_starts, o) - 1)
        a, b, k = self.segs[i]
        return min(b, a + (o - self.out_starts[i]) * k)

    def out(self, s):
        for (a, b, k), o in zip(self.segs, self.out_starts):
            if s <= b: return o + max(0.0, s - a) / k
        return self.duration

    def frame(self, s):
        return self.names[max(0, bisect.bisect_right(self.ts, s) - 1)]


# ------------------------------------------------------------------ camera
def fit_rect(focus, aspect, pad=0.07, min_w=None, loose=False):
    x, y, w, h = focus
    if loose and w * (1 + pad * 2) / aspect > SRC_H:
        # too wide for a tall box: keep the focus shape and let the frame letterbox it
        w2, h2 = w * (1 + pad * 2), h * (1 + pad * 2)
        w2 = min(w2, SRC_W); h2 = min(max(h2, w2 / 2.2), SRC_H)
        cx = min(max(x + w / 2, w2 / 2), SRC_W - w2 / 2); cy = min(max(y + h / 2, h2 / 2), SRC_H - h2 / 2)
        return (cx - w2 / 2, cy - h2 / 2, w2, h2)
    w, h = w * (1 + pad * 2), h * (1 + pad * 2)
    cx, cy = x + focus[2] / 2, y + focus[3] / 2
    if w / h < aspect: w = h * aspect
    else: h = w / aspect
    if min_w and w < min_w: w, h = min_w, min_w / aspect
    if w > SRC_W: w, h = SRC_W, SRC_W / aspect
    if h > SRC_H: h, w = SRC_H, SRC_H * aspect
    cx = min(max(cx, w / 2), SRC_W - w / 2); cy = min(max(cy, h / 2), SRC_H - h / 2)
    return (cx - w / 2, cy - h / 2, w, h)


def camera_track(tl, aspect, min_w):
    """List of (out_time, rect) keys; the camera eases between them over 0.7 s."""
    keys = [(0.0, (0, 0, SRC_W, SRC_H) if aspect > 1 else fit_rect((440, 0, 720, 900), aspect))]
    for e in tl.events:
        f = (e.get('vfocus') or e.get('focus')) if aspect < 1 else e.get('focus')
        if e['kind'] in ('caption', 'focus') and f:
            keys.append((tl.out(e['s']), fit_rect(f, aspect, min_w=min_w)))
    return keys


def camera_at(keys, o, move=0.7):
    rect = keys[0][1]
    for i, (t, r) in enumerate(keys):
        if o < t: break
        prev = keys[i - 1][1] if i else r
        k = ease((o - t) / move)
        rect = tuple(p + (q - p) * k for p, q in zip(prev, r))
    return rect


# ------------------------------------------------------------------ text cards
def wrap(draw, text, f, width):
    words, lines, cur = text.split(), [], ''
    for w in words:
        nxt = (cur + ' ' + w).strip()
        if draw.textlength(nxt, font=f) <= width or not cur: cur = nxt
        else: lines.append(cur); cur = w
    lines.append(cur)
    return lines


def caption_card(text, max_w, size):
    """Rounded dark pill; '3. Do this' gets a gold number badge."""
    num, body = None, text
    if text[:2].rstrip('.').isdigit() and '. ' in text[:4]:
        num, body = text.split('. ', 1)
    f = font('Bold', size)
    tmp = ImageDraw.Draw(Image.new('RGBA', (10, 10)))
    badge = int(size * 1.55) if num else 0
    gap = int(size * 0.55) if num else 0
    padx, pady = int(size * 0.75), int(size * 0.5)
    lines = wrap(tmp, body, f, max_w - badge - gap - padx * 2)
    lh = int(size * 1.28)
    tw = max(tmp.textlength(l, font=f) for l in lines)
    w = int(tw + badge + gap + padx * 2); h = max(badge + pady * 2, lh * len(lines) + pady * 2)
    im = Image.new('RGBA', (w, h + 8), (0, 0, 0, 0))
    sh = Image.new('RGBA', im.size, (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle([0, 6, w - 1, h + 5], h // 2 if len(lines) == 1 else int(size * 0.8), fill=(0, 0, 0, 120))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(5)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], h // 2 if len(lines) == 1 else int(size * 0.8), fill=(18, 16, 30, 236), outline=(255, 255, 255, 40), width=2)
    x = padx
    if num:
        by = (h - badge) // 2
        d.ellipse([x, by, x + badge, by + badge], fill=GOLD)
        nf = font('Bold', int(size * 0.95))
        d.text((x + badge / 2, by + badge / 2 + 1), num, font=nf, fill=INK, anchor='mm')
        x += badge + gap
    y = (h - lh * len(lines)) // 2
    for l in lines:
        d.text((x, y + lh / 2), l, font=f, fill=WHITE, anchor='lm'); y += lh
    return im


def brand_chip(title, size):
    f = font('Bold', size); fl = font('Medium', size)
    tmp = ImageDraw.Draw(Image.new('RGBA', (10, 10)))
    lg = int(size * 1.6); t1 = 'SceneForge'; sep = '  ·  '
    w = int(lg + size * 0.6 + tmp.textlength(t1, font=f) + tmp.textlength(sep + title, font=fl) + size * 1.4)
    h = int(size * 2.3)
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], h // 2, fill=(18, 16, 30, 210))
    im.alpha_composite(LOGO.resize((lg, lg), Image.LANCZOS), (int(size * 0.45), (h - lg) // 2))
    x = int(lg + size * 0.75)
    d.text((x, h / 2), t1, font=f, fill=WHITE, anchor='lm'); x += tmp.textlength(t1, font=f)
    d.text((x, h / 2), sep + title, font=fl, fill=(200, 192, 255), anchor='lm')
    return im


def gradient(w, h):
    y = np.linspace(0, 1, h)[:, None]; x = np.linspace(0, 1, w)[None, :]
    a = np.array([22, 16, 48.]); b = np.array([60, 36, 140.]); c = np.array([12, 10, 22.])
    t = np.clip(0.55 * x + 0.45 * (1 - y), 0, 1)[..., None]
    img = c + (a - c) * (1 - t) + (b - c) * t * 0.9
    glow = np.exp(-(((x - 0.75) ** 2) / 0.08 + ((y - 0.2) ** 2) / 0.06))[..., None]
    img = img + glow * np.array([90, 60, 200.]) * 0.5
    return Image.fromarray(img.clip(0, 255).astype(np.uint8)).convert('RGBA')


def title_card(W, H, cfg, end=False):
    im = gradient(W, H); d = ImageDraw.Draw(im)
    s = min(W, H) / 1080
    lg = int(220 * s)
    if not end:
        im.alpha_composite(LOGO.resize((lg, lg), Image.LANCZOS), ((W - lg) // 2, int(H * 0.5 - lg - 120 * s)))
        d.text((W / 2, H * 0.5 + 10 * s), cfg['kicker'].upper(), font=font('Bold', int(34 * s)), fill=GOLD, anchor='mm')
        lines = wrap(d, cfg['title'], font('Bold', int(110 * s)), W * 0.86)
        y = H * 0.5 + 100 * s
        for l in lines:
            d.text((W / 2, y), l, font=font('Bold', int(110 * s)), fill=WHITE, anchor='mm'); y += 125 * s
        d.text((W / 2, y + 10 * s), 'in SceneForge Studio', font=font('Medium', int(40 * s)), fill=(200, 192, 255), anchor='mm')
    else:
        im.alpha_composite(LOGO.resize((lg, lg), Image.LANCZOS), ((W - lg) // 2, int(H * 0.5 - lg - 110 * s)))
        d.text((W / 2, H * 0.5 + 10 * s), 'SceneForge Studio', font=font('Bold', int(96 * s)), fill=WHITE, anchor='mm')
        d.text((W / 2, H * 0.5 + 100 * s), 'Free, open-source video editor for Windows', font=font('Medium', int(40 * s)), fill=(210, 204, 255), anchor='mm')
        pill = f = font('Bold', int(40 * s)); tw = d.textlength(REPO, font=f)
        px, py = W / 2 - tw / 2 - 34 * s, H * 0.5 + 170 * s
        d.rounded_rectangle([px, py, px + tw + 68 * s, py + 76 * s], int(38 * s), fill=GOLD)
        d.text((W / 2, py + 38 * s), REPO, font=f, fill=INK, anchor='mm')
    return im.convert('RGB')


# ------------------------------------------------------------------ audio
def tick(sr=48000):
    t = np.arange(int(sr * 0.05)) / sr
    return (np.sin(2 * np.pi * 2200 * t) * 0.5 + np.random.default_rng(1).normal(0, 0.3, t.size)) * np.exp(-t * 140) * 0.35


def whoosh(sr=48000, dur=0.7):
    n = int(sr * dur); t = np.arange(n) / sr
    noise = np.random.default_rng(2).normal(0, 1, n)
    k = np.exp(-((t - dur * 0.45) / (dur * 0.22)) ** 2)
    sm = np.convolve(noise, np.ones(18) / 18, 'same')
    return (sm * k * 0.35)


def load_audio(path, sr=48000, start=0.0, secs=None):
    args = ['ffmpeg', '-v', 'error', '-ss', str(start), '-i', str(path)] + (['-t', str(secs)] if secs else []) + ['-ac', '1', '-ar', str(sr), '-f', 's16le', '-']
    raw = subprocess.run(args, capture_output=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float64) / 32767


def build_audio(path, total, clicks, intro, extra=None, sr=48000):
    a = np.zeros(int(sr * (total + 0.5)))
    def put(sig, at, gain=1.0):
        i = int(at * sr); j = min(a.size, i + sig.size)
        if 0 <= i < a.size: a[i:j] += sig[:j - i] * gain
    tk = tick()
    for c in clicks: put(tk, c)
    put(whoosh(), max(0, intro - 0.35), 0.8)
    put(whoosh(), total - 3.0, 0.6)
    for sig, at, g in (extra or []):
        put(sig, at, g)
    a = np.clip(a, -1, 1)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((a * 32767).astype(np.int16).tobytes())


# ------------------------------------------------------------------ render
def render(name, fmt, preview=None):
    cfg = CLIPS[name]
    raw = ROOT / 'raw' / name
    data = json.loads((raw / 'events.json').read_text())
    tl = Timeline(data['frames'], data['events'], cfg)
    W, H = (1920, 1080) if fmt == '16x9' else (1080, 1920)
    INTRO, OUTRO = 1.6, 3.0
    body = min(tl.duration, tl.out(max(e['s'] for e in tl.events if e['kind'] == 'caption')) + cfg['tail'])
    res = json.loads((raw / 'result.json').read_text()) if (raw / 'result.json').exists() else None
    RES = res['secs'] if res else 0.0
    total = INTRO + body + RES + OUTRO
    if fmt == '16x9':
        box = (0, 0, 1920, 1080); aspect = 16 / 9; min_w = 900
        cap_max, cap_size, cap_y = 1500, 40, 1080 - 64
    else:
        box = (0, 300, 1080, 1350); aspect = 1080 / 1350; min_w = 560
        cap_max, cap_size, cap_y = 1000, 50, 300 + 1350 + 140
    keys = camera_track(tl, aspect, min_w)
    caps = [(tl.out(e['s']), e['text']) for e in tl.events if e['kind'] == 'caption' and e['text']]
    pips = [(tl.out(e['s']), e.get('pip')) for e in tl.events if e['kind'] == 'caption']
    cards = {}
    chip = brand_chip(cfg['title'], 26 if fmt == '16x9' else 30)
    intro_img, end_img = title_card(W, H, cfg), title_card(W, H, cfg, end=True)
    if fmt == '9x16':
        header = Image.new('RGBA', (W, 300), (0, 0, 0, 0)); hd = ImageDraw.Draw(header)
        header.alpha_composite(LOGO.resize((84, 84), Image.LANCZOS), (W // 2 - 42, 40))
        hd.text((W / 2, 175), cfg['title'], font=font('Bold', 72), fill=WHITE, anchor='mm')
        hd.text((W / 2, 245), cfg['kicker'], font=font('Medium', 36), fill=(200, 192, 255), anchor='mm')
        footer_txt = Image.new('RGBA', (W, 80), (0, 0, 0, 0))
        ImageDraw.Draw(footer_txt).text((W / 2, 40), 'SceneForge Studio · free & open source', font=font('Medium', 30), fill=(170, 165, 210), anchor='mm')
        bg_base = gradient(W, H).convert('RGB')
    out = ROOT / 'out'; out.mkdir(exist_ok=True)
    suffix = '_preview' if preview else ''
    vpath = out / f'{name}_{fmt}{suffix}.mp4'; apath = ROOT / 'work' / f'{name}_{fmt}.wav'
    clicks = [INTRO + tl.out(e['s']) for e in tl.events if e['kind'] == 'click']
    extra = [(load_audio(raw / e['file']), INTRO + tl.out(e['s']), 0.9) for e in tl.events if e['kind'] == 'audio']
    if res:
        extra.append((load_audio(raw / 'result.mp4', start=res['start'], secs=RES) * np.minimum(1, np.minimum(np.arange(int(RES * 48000)) / 4800, (RES * 48000 - np.arange(int(RES * 48000))) / 9600))[:len(load_audio(raw / 'result.mp4', start=res['start'], secs=RES))], INTRO + body, 1.0))
        rw, rh = (W, H) if fmt == '16x9' else (1080, 608)
        rproc = subprocess.Popen(['ffmpeg', '-v', 'error', '-ss', str(res['start']), '-i', str(raw / 'result.mp4'), '-t', str(RES), '-vf', f'scale={rw}:{rh}:flags=lanczos,fps={FPS}',
                                  '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
        res_card = caption_card('The result', cap_max, cap_size)
    build_audio(apath, total, clicks, INTRO, extra)
    ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                          '-i', str(apath), '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-profile:v', 'high',
                          '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', str(vpath)], stdin=subprocess.PIPE)
    cache = {}
    nframes = int(total * FPS) if not preview else int(min(total, preview) * FPS)
    for fi in range(nframes):
        T = fi / FPS
        if res and INTRO + body <= T < INTRO + body + RES:
            buf = rproc.stdout.read(rw * rh * 3)
            if len(buf) == rw * rh * 3: last_res = Image.frombytes('RGB', (rw, rh), buf)
            if fmt == '16x9':
                canvas = last_res.convert('RGBA'); canvas.alpha_composite(chip, (28, 24))
            else:
                canvas = bg_base.copy().convert('RGBA')
                m = Image.new('L', (rw, rh), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, rw - 1, rh - 1], 28, fill=255)
                canvas.paste(last_res, (0, 300 + (1350 - rh) // 2), m); canvas.alpha_composite(header, (0, 0))
            rt = T - INTRO - body; k = ease(rt / 0.3)
            cy = cap_y - res_card.height // 2 if fmt == '9x16' else cap_y - res_card.height
            canvas.alpha_composite(res_card, ((W - res_card.width) // 2, int(cy + (1 - k) * 24)))
            frame = canvas.convert('RGB')
            fade = min(1.0, (RES - rt) / 0.25)
            if fade < 1: frame = Image.blend(end_img, frame, max(0.0, fade))
            ff.stdin.write(np.asarray(frame).tobytes()); continue
        if T < INTRO or T >= INTRO + body:
            card = intro_img if T < INTRO else end_img
            # fade to/from the content
            frame = card
            if T >= INTRO - 0.25 and T < INTRO:
                pass
            ff.stdin.write(np.asarray(frame).tobytes()); continue
        o = T - INTRO
        s = tl.src(o); fname = tl.frame(s)
        if fname not in cache:
            if len(cache) > 6: cache.pop(next(iter(cache)))
            cache[fname] = Image.open(raw / fname).convert('RGB')
        src = cache[fname]
        x, y, w, h = camera_at(keys, o)
        bx, by, bw, bh = box
        if fmt == '16x9':
            canvas = src.resize((W, H), Image.LANCZOS, box=(x, y, x + w, y + h)).convert('RGBA')
        else:
            canvas = bg_base.copy().convert('RGBA')
            # contain the camera rect inside the content box
            sc = min(bw / w, bh / h); cw, ch = int(w * sc), int(h * sc)
            view = src.resize((cw, ch), Image.LANCZOS, box=(x, y, x + w, y + h))
            px, py = bx + (bw - cw) // 2, by + (bh - ch) // 2
            mask = Image.new('L', (cw, ch), 0); ImageDraw.Draw(mask).rounded_rectangle([0, 0, cw - 1, ch - 1], 28, fill=255)
            canvas.paste(view, (px, py), mask)
            canvas.alpha_composite(header, (0, 0))
        # picture-in-picture: keep the result visible while the camera is on the controls
        pip = None
        for pt, pr in pips:
            if o >= pt: pip = (pt, pr)
        if pip and pip[1]:
            pt, (qx, qy, qw, qh) = pip
            inside = qx >= x and qy >= y and qx + qw <= x + w and qy + qh <= y + h
            k = ease((o - pt - 0.5) / 0.35)
            if not inside and k > 0:
                pw = 600 if fmt == '16x9' else 560; ph = int(pw * qh / qw)
                view = src.resize((pw, ph), Image.LANCZOS, box=(qx, qy, qx + qw, qy + qh)).convert('RGBA')
                card = Image.new('RGBA', (pw + 12, ph + 12), (0, 0, 0, 0)); cd = ImageDraw.Draw(card)
                cd.rounded_rectangle([0, 0, pw + 11, ph + 11], 22, fill=(255, 255, 255, 235))
                m = Image.new('L', (pw, ph), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, pw - 1, ph - 1], 17, fill=255)
                card.paste(view, (6, 6), m)
                if k < 1: card.putalpha(card.getchannel('A').point(lambda v: int(v * k)))
                if fmt == '16x9': canvas.alpha_composite(card, (W - card.width - 30, 30))
                else: canvas.alpha_composite(card, (W - card.width - 24, box[1] + 24))
        if fmt == '16x9':
            canvas.alpha_composite(chip, (28, 24))
        # caption
        cur = None
        for ct, text in caps:
            if o >= ct - 0.05: cur = (ct, text)
        if cur:
            ct, text = cur
            if text not in cards: cards[text] = caption_card(text, cap_max, cap_size)
            card = cards[text]; k = ease((o - ct) / 0.3)
            cx = (W - card.width) // 2; cy = int(cap_y - card.height / 2 + (1 - k) * 24)
            if fmt == '16x9': cy = int(cap_y - card.height + (1 - k) * 24)
            if k < 1:
                c2 = card.copy(); c2.putalpha(c2.getchannel('A').point(lambda v: int(v * k))); card = c2
            canvas.alpha_composite(card, (cx, cy))
        frame = canvas.convert('RGB')
        # quick fades in/out of the cards
        fade = min(1.0, o / 0.25, (body - o) / 0.25 if not res else 1.0)
        if fade < 1:
            ref = intro_img if o < 0.3 else end_img
            frame = Image.blend(ref, frame, max(0.0, fade))
        ff.stdin.write(np.asarray(frame).tobytes())
    ff.stdin.close(); ff.wait()
    print(f'{vpath.name}: {nframes / FPS:.1f}s')
    return vpath


if __name__ == '__main__':
    name = sys.argv[1]
    only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
    prev = float(sys.argv[sys.argv.index('--preview') + 1]) if '--preview' in sys.argv else None
    for fmt in ('16x9', '9x16'):
        if only and fmt != only: continue
        render(name, fmt, prev)
