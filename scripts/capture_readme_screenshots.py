"""Capture the README screenshots in docs/images/ from a running SceneForge backend.

What it does
  1. media  - draws original demo media with Pillow/NumPy/FFmpeg (a sunset city, mountains,
              an illustrated presenter, a bokeh video, music-like and effect audio). Nothing
              third-party or copyrighted is used.
  2. seed   - creates a "Night City Stories" project through the HTTP API: 4 scenes with caption
              styles, titles with clock/iris reveals, effect presets with per-effect settings, an
              effect stack, stickers from the bundled library, a textured title, a subject cutout,
              a music bed, A3-A6 timeline clips with a group and a volume envelope, colour/range
              markers, beat markers, and rendered scenes. It DELETES every existing project in
              that backend first, so only point it at a throwaway data folder.
  3. shots  - drives the built editor with Playwright (Chromium) at 1600x900 and writes optimised
              PNGs to docs/images/.

No paid provider is called. The text-to-video shot only selects a cloud model to show the cost
estimate; nothing is generated. The cutout uses the local models (u2netp/People/IS-Net), so
point SCENEFORGE_CUTOUT_MODEL_DIR at a folder that has them for offline runs.

Typical run (Linux, from the repository root):
    npm --prefix frontend run build
    export SCENEFORGE_DATA_DIR=$(mktemp -d)        # throwaway data folder
    # the backend serves frontend/dist on the same origin; a Secret Service keyring avoids
    # credential-store warnings on Linux:
    dbus-run-session -- bash -c 'printf x | gnome-keyring-daemon --unlock --components=secrets;
        cd backend && HOME=/home/demo python -m uvicorn app.main:app --port 8765' &
    python scripts/capture_readme_screenshots.py --base http://127.0.0.1:8765

Requirements for this script: Python with requests, numpy, Pillow and playwright (with a
Chromium; set PLAYWRIGHT_BROWSERS_PATH if it lives elsewhere), plus ffmpeg on PATH.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import pathlib
import subprocess
import sys
import tempfile
import time

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parents[1]
W, H = 1920, 1080
VIEW = {"width": 1600, "height": 900}


# --------------------------------------------------------------------------- media
def _sky(top, mid, bot, horizon):
    y = np.linspace(0, 1, H)[:, None, None]
    top, mid, bot = (np.array(c, float) for c in (top, mid, bot))
    t1 = np.clip(y / horizon, 0, 1)
    t2 = np.clip((y - horizon) / (1 - horizon), 0, 1)
    col = np.where(y < horizon, top + (mid - top) * t1 ** 1.3, mid + (bot - mid) * t2)
    return np.broadcast_to(col, (H, W, 3)).copy()


def _sun(img, cx, cy, r, color, glow):
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    g = np.exp(-np.maximum(d - r, 0) / (r * glow))[..., None]
    img[:] = img * (1 - 0.65 * g) + np.array(color) * 0.65 * g
    img[:] = np.where((d < r)[..., None], np.array([255, 236, 190]), img)


def _city(rng):
    img = _sky((22, 18, 58), (250, 120, 70), (40, 20, 50), 0.66)
    _sun(img, W * 0.62, H * 0.6, 95, (255, 170, 90), 4)
    im = Image.fromarray(img.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    pts = [(x, H * 0.58 - 40 * math.sin(x / 210) - 25 * math.sin(x / 77)) for x in range(0, W + 20, 20)]
    d.polygon([(0, H * 0.62)] + pts + [(W, H), (0, H)], fill=(120, 60, 90))
    for layer, (col, base, hmax, wmin) in enumerate([((70, 35, 70), 0.70, 260, 40), ((38, 20, 45), 0.74, 380, 55), ((16, 10, 24), 0.80, 300, 70)]):
        x = -20
        while x < W:
            w = int(rng.integers(wmin, wmin * 2.4)); h = int(rng.integers(hmax * 0.3, hmax)); top = H * base - h
            d.rectangle([x, top, x + w, H], fill=col)
            if rng.random() < 0.25:
                d.rectangle([x + w // 2 - 2, top - 40, x + w // 2 + 2, top], fill=col)
            if layer:
                for wy in range(int(top) + 12, int(H * base), 18):
                    for wx in range(x + 8, x + w - 8, 14):
                        if rng.random() < 0.28:
                            d.rectangle([wx, wy, wx + 5, wy + 8], fill=(255, 200 - layer * 20, 120))
            x += w + int(rng.integers(2, 14))
    arr = np.asarray(im).astype(float)
    hz = int(H * 0.8)
    refl = arr[hz - (H - hz):hz][::-1] * 0.55 + np.array([10, 15, 40]) * 0.45
    for i in range(H - hz):
        arr[hz + i] = np.roll(refl[i], int(math.sin(i * 0.9) * 6), axis=0)
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))


def _mountains(rng):
    img = _sky((40, 80, 150), (250, 190, 150), (60, 90, 110), 0.55)
    _sun(img, W * 0.3, H * 0.5, 70, (255, 220, 160), 6)
    im = Image.fromarray(img.clip(0, 255).astype(np.uint8))
    for i, (col, base, amp) in enumerate([((150, 150, 190), 0.50, 160), ((100, 110, 160), 0.60, 140), ((60, 75, 120), 0.70, 120),
                                          ((30, 45, 75), 0.82, 90), ((15, 25, 40), 0.92, 60)]):
        d = ImageDraw.Draw(im); ph = rng.random() * 10
        pts = [(x, H * base - amp * (0.6 * math.sin(x / (300 - i * 30) + ph) + 0.4 * math.sin(x / (97 - i * 8) + ph * 2))
                - abs(math.sin(x / 41 + ph)) * 20) for x in range(0, W + 10, 10)]
        d.polygon([(0, H)] + pts + [(W, H)], fill=col)
        im = Image.blend(im, Image.new("RGB", (W, H), (230, 200, 200)), 0.06)
    d = ImageDraw.Draw(im)
    for _ in range(70):
        x = rng.integers(0, W); b = H * rng.uniform(0.94, 1.02); h = rng.uniform(60, 170)
        d.polygon([(x, b - h), (x - h * 0.22, b), (x + h * 0.22, b)], fill=(10, 18, 28))
    return im


def _presenter():
    """An illustrated person on a soft studio backdrop (for the subject cutout)."""
    im = Image.fromarray(_sky((200, 215, 230), (230, 225, 215), (180, 170, 160), 0.8).clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))
    d = ImageDraw.Draw(im); cx = int(W * 0.62)
    d.rounded_rectangle([cx - 230, 610, cx + 230, 1200], 160, fill=(170, 60, 50))
    d.polygon([(cx - 60, 600), (cx + 60, 600), (cx, 760)], fill=(240, 235, 225))
    d.rectangle([cx - 50, 520, cx + 50, 640], fill=(205, 150, 115))
    d.ellipse([cx - 125, 280, cx + 125, 570], fill=(222, 168, 130))
    d.chord([cx - 135, 255, cx + 135, 520], 180, 360, fill=(55, 35, 30))
    d.ellipse([cx - 140, 300, cx - 95, 430], fill=(55, 35, 30)); d.ellipse([cx + 95, 300, cx + 140, 430], fill=(55, 35, 30))
    for ex in (-48, 48):
        d.ellipse([cx + ex - 14, 410, cx + ex + 14, 432], fill=(40, 30, 30))
    d.arc([cx - 45, 450, cx + 45, 515], 20, 160, fill=(150, 70, 60), width=6)
    d.rounded_rectangle([cx - 200, 760, cx - 40, 860], 18, fill=(30, 32, 38)); d.ellipse([cx - 150, 775, cx - 80, 845], fill=(80, 90, 110))
    return im


def _ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def make_media(out: pathlib.Path):
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    _city(rng).save(out / "city_sunset.jpg", quality=92)
    _mountains(rng).save(out / "mountain_dawn.jpg", quality=92)
    _presenter().save(out / "storyteller.jpg", quality=92)
    # bokeh lights over a drifting gradient, 8 s, with a soft pad as its own sound
    vw, vh, fps, secs = 960, 540, 25, 8
    yy, xx = np.mgrid[0:vh, 0:vw].astype(np.float32)
    blobs = [(rng.uniform(0, vw), rng.uniform(0, vh), rng.uniform(22, 68), rng.uniform(-24, 24), rng.uniform(-12, 12), rng.uniform(0.2, 0.55)) for _ in range(24)]
    pad = "0.12*sin(2*PI*220*t)*(0.6+0.4*sin(2*PI*0.25*t))+0.08*sin(2*PI*277.2*t)+0.06*sin(2*PI*329.6*t)"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{vw}x{vh}", "-r", str(fps), "-i", "-",
                          "-f", "lavfi", "-i", f"aevalsrc='{pad}':s=48000:d={secs}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                          "-c:a", "aac", "-shortest", str(out / "night_lights.mp4")], stdin=subprocess.PIPE)
    for f in range(fps * secs):
        t = f / fps; a = 0.5 + 0.5 * math.sin(t * 0.6)
        frame = np.stack([20 + 40 * a + 30 * (xx / vw), 15 + 10 * (yy / vh), 60 + 60 * (1 - xx / vw) + 20 * a], -1)
        for bx, by, r, vx, vy, al in blobs:
            cx, cy = (bx + vx * t) % vw, (by + vy * t) % vh
            x0, x1, y0, y1 = int(max(0, cx - r - 2)), int(min(vw, cx + r + 2)), int(max(0, cy - r - 2)), int(min(vh, cy + r + 2))
            if x1 <= x0 or y1 <= y0:
                continue
            sub = frame[y0:y1, x0:x1]
            m = np.clip(1 - (np.sqrt((xx[y0:y1, x0:x1] - cx) ** 2 + (yy[y0:y1, x0:x1] - cy) ** 2) - r * 0.85) / (r * 0.15), 0, 1)[..., None] * al
            sub[:] = sub * (1 - m) + np.array([255, 170 + 60 * math.sin(bx), 90 + 90 * math.cos(by)]) * m
        p.stdin.write(frame.clip(0, 255).astype(np.uint8).tobytes())
    p.stdin.close(); p.wait()
    chord = lambda o: "pow(2,(if(lt(mod(t,8),2),0,if(lt(mod(t,8),4),%d,if(lt(mod(t,8),6),%d,%d))))/12)" % o
    music = ("aevalsrc='0.9*sin(2*PI*55*t*(1+2*exp(-mod(t,0.5)*30)))*exp(-mod(t,0.5)*9)"
             "+0.15*(random(0)-0.5)*exp(-mod(t+0.25,0.5)*60)"
             f"+0.10*(sin(2*PI*220*t*{chord((-4, 3, -2))})+sin(2*PI*261.6*t*{chord((-3, 4, -1))})+sin(2*PI*329.6*t*{chord((-4, 3, -2))}))'"
             ":s=44100:d=32")
    _ff("-f", "lavfi", "-i", music, "-af", "alimiter=limit=0.8", "-c:a", "libmp3lame", "-q:a", "3", str(out / "sunset_groove.mp3"))
    _ff("-f", "lavfi", "-i", "aevalsrc='0.25*sin(2*PI*110*t)*(0.5+0.5*sin(2*PI*0.1*t))+0.15*sin(2*PI*165*t)+0.05*(random(0)-0.5)':s=44100:d=14",
        "-af", "lowpass=f=900", str(out / "ambient_pad.wav"))
    _ff("-f", "lavfi", "-i", "aevalsrc='(random(0)-0.5)*exp(-pow((t-0.6)*3,2))':s=44100:d=1.4", "-af", "bandpass=f=1500:w=1200,volume=4", str(out / "whoosh.wav"))
    _ff("-f", "lavfi", "-i", "aevalsrc='0.3*sin(2*PI*880*t)*exp(-t*6)+0.2*sin(2*PI*1320*t)*exp(-t*8)':s=44100:d=1.2", str(out / "chime.wav"))
    _ff("-f", "lavfi", "-i", "aevalsrc='0.3*sin(2*PI*(160+30*sin(2*PI*3*t))*t)*(0.5+0.5*sin(2*PI*2.3*t))*lt(mod(t,2.4),2.0)':s=44100:d=9",
        str(out / "room_tone.wav"))


# --------------------------------------------------------------------------- seed
class Api:
    def __init__(self, base):
        self.base, self.s = base.rstrip("/"), requests.Session()

    def _ok(self, r):
        if r.status_code >= 400:
            raise SystemExit(f"{r.request.method} {r.url} -> {r.status_code} {r.text[:400]}")
        return r.json()

    def get(self, p): return self._ok(self.s.get(self.base + p))
    def post(self, p, **k): return self._ok(self.s.post(self.base + p, **k))
    def patch(self, p, js): return self._ok(self.s.patch(self.base + p, json=js))
    def delete(self, p): return self.s.delete(self.base + p)

    def wait(self, jid):
        for _ in range(2400):
            j = self.get(f"/api/jobs/{jid}")
            if j["status"] in ("succeeded", "failed", "cancelled"):
                return j
            time.sleep(0.5)
        raise SystemExit("job timed out")


def seed(api: Api, media: pathlib.Path):
    styles = {s["name"]: s["values"] for s in json.loads((ROOT / "frontend/src/captionStyles.json").read_text(encoding="utf-8"))["styles"]}
    for p in api.get("/api/projects"):
        api.delete(f"/api/projects/{p['id']}")
    pid = api.post("/api/projects", json={"title": "Night City Stories", "aspect": "16:9", "fps": 25})["id"]
    mimes = {".jpg": "image/jpeg", ".mp4": "video/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav"}
    A = {f.name: api.post(f"/api/assets/upload?project_id={pid}", files={"file": (f.name, f.read_bytes(), mimes[f.suffix])})
         for f in sorted(media.iterdir()) if f.suffix in mimes}
    scenes = api.get(f"/api/projects/{pid}")["scenes"]
    while len(scenes) < 4:
        api.post(f"/api/projects/{pid}/scenes", json={"title": ""}); scenes = api.get(f"/api/projects/{pid}")["scenes"]
    sid = [s["id"] for s in scenes]
    cap = lambda style, **extra: {"captions_enabled": True, **styles[style], **extra}
    plan = [
        ("Golden hour", "city_sunset.jpg", 6000, "Every city has a second life that begins when the sun goes down.",
         cap("Two-tone sunset", size=84, layers=[{"id": "T1", "kind": "text_plus", "text": "NIGHT CITY", "x": 50, "y": 22, "size": 150, "family": "Bebas Neue",
                                                   "spacing": 12, "color": "#FFFFFF", "animation": "reveal-iris", "animation_ms": 1200, "start_ms": 0, "end_ms": 6000}]),
         "golden_hour", {"fx_params": {"golden_hour": {"shadows": 115, "highlights": 130, "gamma": 104, "saturation": 125}}, "adjust": {"vignette": 25}}),
        ("Into the hills", "mountain_dawn.jpg", 6000, "Out past the last streetlight, the hills keep the old quiet.",
         cap("Cinematic letterbox"), "halation",
         {"fx_params": {"halation": {"threshold": 150, "radius": 20, "color": "#FF6A3D", "amount": 65}}, "leak": {"amount": 35, "speed": 30, "color": "warm"},
          "flare": {"x": 30, "y": 46, "color": "#FFC27A", "blend": "screen", "amount": 55, "drift": 20}, "shake": {"amount": 25, "speed": 40, "impact": False},
          "fx_order": ["flare", "leak", "shake", "spotlight", "wiggle"], "fx_bypass": ["shake"]}),
        ("City lights", "night_lights.mp4", 8000, "Downtown the lights blur into colour and everyone is going somewhere.",
         cap("Neon pink", size=84), "vhs", {"fx_params": {"vhs": {"bleed": 8, "noise": 18, "scanlines": 30, "tracking": 14}}}),
        ("Meet the storyteller", "storyteller.jpg", 6000, "And somewhere in the middle of it, someone is ready to tell the story.",
         cap("Karaoke yellow fill", captions_enabled=False, layers=[{"id": "B", "kind": "text_plus", "text": "STORIES", "x": 52, "y": 40, "size": 200, "family": "Anton",
                                                                     "color": "#FFD84D", "animation": "reveal-clock", "animation_ms": 1400, "start_ms": 0, "end_ms": 6000}]),
         "portra", {"fx_params": {"portra": {"tone": 110, "saturation": 104, "contrast": 106, "fade": 8}}}),
    ]
    for s, (title, src, dur, text, font, effect, look) in zip(sid, plan):
        api.post(f"/api/scenes/{s}/shots", json={"asset_id": A[src]["id"]})
        api.patch(f"/api/scenes/{s}", {"title": title, "original_text": text, "spoken_text": text, "subtitle_text": text, "timing_mode": "fixed",
                                       "requested_duration_ms": dur, "font": font, "effect_preset": effect, "effect_intensity": 80, "look": look})
    for s, tr in zip(sid[1:], ("dissolve", "zoom_in", "circle_open")):
        api.patch(f"/api/scenes/{s}", {"transition_in": {"type": tr, "duration_ms": 600}})
    st = [api.post(f"/api/projects/{pid}/stickers/{x}") for x in ("sun", "bold-arrow-right", "subscribe-pill")]
    sticker = lambda i, x, y, w, anim="none": {"id": f"st{i}", "asset_id": st[i]["id"], "kind": "sticker", "x": x, "y": y, "width": w, "border": 0, "radius": 0,
                                               "shadow": 0, "anim_in": anim, "anim_out": "none"}
    api.patch(f"/api/scenes/{sid[1]}", {"overlays": [sticker(0, 80, 22, 12, "zoom"), sticker(1, 22, 62, 10), sticker(2, 84, 82, 18)]})
    api.post(f"/api/scenes/{sid[2]}/textured-title", json={"text": "NEON", "texture": {"preset": "neon"}, "font": "Anton", "font_size": 200, "glow": 45,
                                                         "glow_color": "#FF4FD8", "x": 50, "y": 30, "width": 46})
    api.post(f"/api/scenes/{sid[3]}/subject-layer", json={"model": "u2netp", "edge": "soft"})
    clip = lambda cid, f, name, start, out, track, **k: {"id": cid, "asset_id": A[f]["id"], "name": name, "start_ms": start, "source_in_ms": 0,
                                                         "source_out_ms": out, "track": track, **k}
    fin = {
        "music": {"asset_id": A["sunset_groove.mp3"]["id"], "volume": 70, "duck": 60, "fade_in_ms": 1500, "fade_out_ms": 2500},
        "loudnorm": True,
        "audio_clips": [
            clip("pad", "ambient_pad.wav", "Ambient pad", 0, 12000, "A3", volume=80, fade_in_ms=1500, fade_out_ms=2000),
            clip("room", "room_tone.wav", "Street atmos", 12500, 9000, "A5", volume=90, gain=[[0, -24], [1500, 0], [5000, 0], [6200, -14], [9000, -14]]),
            clip("wh1", "whoosh.wav", "Whoosh", 5500, 1400, "A4", group="g-trans"),
            clip("ch1", "chime.wav", "Chime", 6900, 1200, "A4", group="g-trans"),
            clip("wh2", "whoosh.wav", "Whoosh", 11400, 1400, "A4"),
            clip("wh3", "whoosh.wav", "Whoosh", 19300, 1400, "A4"),
            clip("pad2", "ambient_pad.wav", "Ambient pad", 13000, 13000, "A3", volume=60, fade_in_ms=2000, fade_out_ms=3000),
            clip("ch2", "chime.wav", "Chime", 20600, 1200, "A6"),
        ],
        "timeline": {"version": 1, "audio_tracks": ["A3", "A4", "A5", "A6"], "tracks": {"A6": {"mute": True}},
                     "markers": [{"id": "m1", "time_ms": 1000, "duration_ms": 4000, "label": "Intro", "color": "blue"},
                                 {"id": "m2", "time_ms": 13000, "label": "Drop", "color": "red"},
                                 {"id": "m3", "time_ms": 19000, "duration_ms": 4000, "label": "Outro", "color": "purple"},
                                 {"id": "m4", "time_ms": 7400, "label": "Chime cue", "color": "green", "clip_id": "ch1", "offset_ms": 500}]},
    }
    api.patch(f"/api/projects/{pid}", {"finishing": fin})
    bm = api.post(f"/api/projects/{pid}/beat-markers", json={"every": 4})
    fin["timeline"]["markers"] += [{"id": f"beat-{i}-{b['time_ms']}", "time_ms": b["time_ms"], "duration_ms": 0, "label": "♪1" if b["downbeat"] else "♪",
                                    "color": "red" if b["downbeat"] else "purple"} for i, b in enumerate(bm["markers"])]
    api.patch(f"/api/projects/{pid}", {"finishing": fin})
    for s in sid:
        j = api.wait(api.post(f"/api/scenes/{s}/render")["job_id"])
        if j["status"] != "succeeded":
            raise SystemExit(f"scene render failed: {j.get('error_message')}")
    for s in sid:  # build the cached preview mixes (render + timeline audio) before the browser asks for them
        api.s.get(f"{api.base}/api/scenes/{s}/preview-media", timeout=600)
    print(f"seeded project {pid}")


# --------------------------------------------------------------------------- shots
def save_png(page, path: pathlib.Path, budget=300_000):
    """Screenshot, then keep the best PNG that fits the size budget: lossless, then a dithered
    256-colour palette (keeps picture gradients smooth), then a plain 256-colour palette."""
    raw = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
    candidates = (lambda: raw,
                  lambda: raw.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG),
                  lambda: raw.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
    for make in candidates:
        buf = io.BytesIO(); make().save(buf, format="PNG", optimize=True)
        if buf.tell() <= budget:
            break
    path.write_bytes(buf.getvalue())
    print(f"  {path.name}: {path.stat().st_size // 1024} KB")


class Editor:
    def __init__(self, page, base):
        self.pg, self.base = page, base

    def open(self, inspector=None):
        pg = self.pg
        pg.goto(self.base + "/"); pg.wait_for_timeout(800)
        pg.evaluate("w=>{try{localStorage.setItem('sceneforge.tour.v1','done');localStorage.removeItem('sceneforge.preferences.v1');"
                    "if(w)localStorage.setItem('sceneforge.inspectorWidth',String(w));else localStorage.removeItem('sceneforge.inspectorWidth');}catch(e){}}",
                    inspector)
        pg.reload(); pg.wait_for_timeout(1500)
        pg.get_by_text("Night City Stories").first.click(); pg.wait_for_timeout(3500)

    def dock(self, y):
        box = self.pg.locator(".dock-resizer").bounding_box()
        self.pg.mouse.move(800, box["y"] + box["height"] / 2); self.pg.mouse.down()
        self.pg.mouse.move(800, y, steps=10); self.pg.mouse.up(); self.pg.wait_for_timeout(600)

    def zoom(self, px_per_s):
        self.pg.evaluate("""v=>{const el=document.querySelector('input[aria-label="Timeline zoom"]');
          Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,String(v));
          el.dispatchEvent(new Event('input',{bubbles:true}));}""", px_per_s)
        self.pg.wait_for_timeout(600)

    def scene(self, title):
        self.pg.locator(".scene-list").get_by_text(title, exact=True).first.click(); self.pg.wait_for_timeout(1500)

    def tab(self, name):
        self.pg.locator(f'[role=tab][id$="-{name}-tab"]:visible').first.click(); self.pg.wait_for_timeout(1000)

    def scroll_to(self, text, offset=10):
        # 0.9.0: effects live in collapsible groups; open them so every card can be found
        self.pg.evaluate("""()=>document.querySelectorAll('button.fx-group-head[aria-expanded="false"]').forEach(b=>b.click())""")
        self.pg.wait_for_timeout(300)
        self.pg.evaluate("""([t,o])=>{const body=[...document.querySelectorAll('.inspector-body')].find(b=>b.getBoundingClientRect().width>0);
          const el=[...body.querySelectorAll('h2,h3,h4,h5,legend,strong,label,summary,span,p,button,div')].find(e=>e.children.length<4&&e.textContent.trim().toLowerCase().startsWith(t.toLowerCase()));
          if(!el) throw new Error('not found: '+t);
          body.scrollTop += el.getBoundingClientRect().top - body.getBoundingClientRect().top - o;}""", [text, offset])
        self.pg.wait_for_timeout(600)

    def seek(self, t):
        self.pg.evaluate("""async t=>{const v=[...document.querySelectorAll('video')].find(v=>v.getBoundingClientRect().width>0); if(!v) return;
          v.pause(); for(let i=0;i<300&&v.readyState<2;i++) await new Promise(r=>setTimeout(r,100));
          await new Promise(r=>{v.addEventListener('seeked',r,{once:true}); v.currentTime=t; setTimeout(r,5000);});}""", t)
        self.pg.mouse.move(5, 895); self.pg.wait_for_timeout(1200)

    def play_at(self, t, lead=3.2):
        """Play muted so the picture reaches t just as the screenshot is taken. A playing video
        hides Chromium's native controls, which would otherwise cover the captions."""
        self.seek(max(0.0, t - lead))
        self.pg.evaluate("""()=>{const v=[...document.querySelectorAll('video')].find(v=>v.getBoundingClientRect().width>0); if(v){v.muted=true; v.play();}}""")
        self.pg.mouse.move(5, 895); self.pg.wait_for_timeout(int(lead * 1000))

    def no_errors(self, name):
        bad = self.pg.evaluate("[...document.querySelectorAll('.error-box,[role=alert]')].filter(e=>e.getBoundingClientRect().height>0&&e.textContent.trim()).map(e=>e.textContent.trim().slice(0,120))")
        if bad:
            print(f"  WARNING {name}: visible error/alert: {bad}")


def webm_bridge(ctx, workdir: pathlib.Path):
    """Playwright's Chromium has no H.264/AAC decoder, so the editor's MP4 renders would stay
    blank. Serve the same rendered frames re-encoded to VP9/Opus WebM instead (screenshots only)."""
    cache: dict[str, tuple[bytes, str]] = {}

    def handle(route):
        url = route.request.url
        if url not in cache:
            r = requests.get(url, timeout=600)
            body, ctype = r.content, r.headers.get("content-type", "application/octet-stream")
            if r.ok and ("mp4" in ctype or "quicktime" in ctype):
                src, dst = workdir / f"in{len(cache)}.mp4", workdir / f"out{len(cache)}.webm"
                src.write_bytes(body)
                _ff("-i", str(src), "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "30", "-deadline", "realtime", "-cpu-used", "8",
                    "-c:a", "libopus", str(dst))
                body, ctype = dst.read_bytes(), "video/webm"
            cache[url] = (body, ctype)
        body, ctype = cache[url]
        headers = {"content-type": ctype, "cache-control": "no-store", "accept-ranges": "bytes"}
        rng = route.request.headers.get("range", "")
        if rng.startswith("bytes=") and ctype.startswith("video/"):  # byte ranges make the video seekable
            first, _, last = rng[6:].split(",")[0].partition("-")
            start = int(first or 0); end = min(int(last) if last else len(body) - 1, len(body) - 1)
            headers["content-range"] = f"bytes {start}-{end}/{len(body)}"
            route.fulfill(status=206, body=body[start:end + 1], headers=headers)
        else:
            route.fulfill(status=200, body=body, headers=headers)

    ctx.route("**/api/scenes/*/preview-media*", handle)
    ctx.route("**/api/assets/*/stream*", handle)


def capture(base: str, out: pathlib.Path):
    from playwright.sync_api import sync_playwright
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport=VIEW, device_scale_factor=1)
        webm_bridge(ctx, pathlib.Path(tempfile.mkdtemp(prefix="sf-webm-")))
        pg = ctx.new_page(); ed = Editor(pg, base)

        def shot(name):
            ed.no_errors(name); save_png(pg, out / name)

        # 1. Editor overview (hero)
        ed.open()
        ed.play_at(3.4); shot("editor-overview.png")

        # 2. Multitrack timeline: A3-A6, groups, envelope, colour/range/beat markers, right-click on clip sound
        ed.open(); ed.dock(330)
        ed.zoom(95)
        pg.locator("button.project-audio-body:visible", has_text="Street atmos").first.click(); pg.wait_for_timeout(500)
        pg.evaluate("document.querySelector('.sequence-scroll').scrollLeft=480"); pg.wait_for_timeout(500)
        src = pg.locator(".source-audio-clip:visible").first.bounding_box()
        pg.mouse.click(src["x"] + src["width"] * 0.2, src["y"] + src["height"] / 2, button="right"); pg.wait_for_timeout(700)
        shot("timeline-multitrack.png")

        # 3. Effects: presets + per-effect settings
        ed.open(inspector=640); ed.dock(900)
        ed.scene("Into the hills"); ed.tab("Effects")
        ed.scroll_to("Effect strength", 140)
        ed.play_at(3.4); shot("effects-settings.png")

        # 4. Effect stack + look presets
        ed.scroll_to("Effect stack", 10)
        ed.play_at(4.2); shot("effect-stack-presets.png")

        # 5. Caption styles
        ed.scene("City lights"); ed.tab("Text")
        ed.scroll_to("Caption styles", 10)
        ed.play_at(4.6); shot("caption-styles.png")

        # 6. Sticker & emoji library
        ed.scene("Into the hills"); ed.tab("Overlays")
        ed.scroll_to("Stickers & emoji", 10)
        ed.play_at(3.6); shot("stickers-library.png")

        # 7. Textured title
        ed.scene("City lights"); ed.tab("Overlays")
        ed.scroll_to("Textured title", 10)
        pg.locator(".inspector-body:visible input[placeholder*='LAVA']").first.fill("NEON")
        pattern = pg.locator(".inspector-body:visible select").filter(has=pg.locator("option", has_text="Galaxy")).first
        pattern.select_option(label=next(o for o in pattern.locator("option").all_inner_texts() if o.strip().lower() == "neon"))
        ed.play_at(3.4); shot("textured-title.png")

        # 7b. Video inside text (0.9.1)
        ed.scene("City lights"); ed.tab("Overlays")
        ed.scroll_to("Video inside text", 10)
        pg.locator(".inspector-body:visible input[placeholder*='NORWAY']").first.fill("1942")
        ed.play_at(3.4); shot("video-in-text.png")

        # 7c. Typewriter box with sound preview (0.9.0)
        ed.scene("Golden hour"); ed.tab("Text")
        ed.scroll_to("Typewriter", 10)
        ed.play_at(3.4); shot("typewriter-box.png")

        # 8. Subject cutout with result preview (People model, local)
        ed.scene("Meet the storyteller"); ed.tab("Overlays")
        ed.scroll_to("Subject cutout", 10)
        panel = pg.locator(".inspector-body:visible")
        model = panel.locator("select").filter(has=pg.locator("option", has_text="People")).first
        model.select_option(label=next(o for o in model.locator("option").all_inner_texts() if "People" in o))
        panel.get_by_role("button", name="Remove background").first.click()
        pg.locator(".cutout-preview img:visible").first.wait_for(timeout=180_000); pg.wait_for_timeout(1500)
        ed.scroll_to("Model", 8)
        ed.play_at(3.4); shot("subject-cutout.png")

        # 9. Timeline clip audio: volume, trims, fades + AI voice isolation
        ed.open(inspector=640); ed.dock(900); ed.tab("Audio")
        pg.locator(".inspector-body:visible select").filter(has=pg.locator('option[value="room"]')).first.select_option("room")  # the "Street atmos" clip
        pg.wait_for_timeout(1200)
        ed.scroll_to("Isolate voice", 250)
        ed.play_at(3.4); shot("audio-voice-isolation.png")

        # 10. Music & finishing: ducking, fit music, beat sync
        ed.scroll_to("Music & finishing", 10)
        ed.play_at(3.4); shot("music-finishing.png")

        # 11. Local voices (Docker) panel
        ed.scroll_to("Local voice engines", 10)
        ed.play_at(3.4); shot("local-voices.png")

        # 12. Text-to-video with a cloud cost estimate (nothing is generated)
        ed.open()
        pg.get_by_role("button", name="Generate video").first.click(); pg.wait_for_timeout(1500)
        pg.get_by_text("Google Veo", exact=True).first.click(); pg.wait_for_timeout(800)
        def pick(value, last=False):   # the generator's select that offers this option
            loc = pg.locator(".video-gen-panel select:visible").filter(has=pg.locator(f'option[value="{value}"]'))
            (loc.last if last else loc.first).select_option(value)
        pick("veo-3.1-fast"); pg.wait_for_timeout(400); pick("8"); pick("1080p"); pick("2", last=True)
        pg.locator("textarea:visible").first.fill("Slow aerial dolly over a neon-lit city at dusk, light rain, reflections on wet streets, cinematic, 35mm")
        pg.wait_for_timeout(600)
        shot("text-to-video.png")

        # 13. Export dialog
        ed.open()
        pg.get_by_role("button", name="Export video").first.click(); pg.wait_for_timeout(1200)
        shot("export-dialog.png")

        # 14. Project home in the Daylight theme
        pg.goto(base + "/"); pg.wait_for_timeout(800)
        pg.evaluate("localStorage.setItem('sceneforge.preferences.v1', JSON.stringify({theme:'light',accent:'violet',density:'compact',reduceMotion:false}))")
        pg.reload(); pg.wait_for_timeout(1800)
        shot("home-daylight.png")
        browser.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", default="http://127.0.0.1:8765", help="URL of a running SceneForge backend that serves frontend/dist")
    ap.add_argument("--out", default=str(ROOT / "docs" / "images"))
    ap.add_argument("--media", default=None, help="folder for generated demo media (default: a temp folder)")
    ap.add_argument("--skip-media", action="store_true", help="reuse media already in --media")
    ap.add_argument("--skip-seed", action="store_true", help="reuse the project already in the backend")
    a = ap.parse_args()
    media = pathlib.Path(a.media or tempfile.mkdtemp(prefix="sf-demo-media-"))
    if not a.skip_seed:
        if not a.skip_media:
            print("drawing demo media ..."); make_media(media)
        print("seeding the demo project ..."); seed(Api(a.base), media)
    print("capturing ..."); capture(a.base, pathlib.Path(a.out))


if __name__ == "__main__":
    sys.exit(main())
