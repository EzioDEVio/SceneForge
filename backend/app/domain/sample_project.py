"""Try a sample project" (0.9.0).

Builds a small ready-made project so a new user sees SceneForge working in seconds: three scenes
with pictures, captions in different styles, a title, a typewriter caption with sound, stickers,
looks and effects, transitions, a music bed with ducking, timeline sound effects on A3/A4 and
markers. All media is drawn here (Pillow/NumPy) or synthesised with FFmpeg, so nothing third-party
or copyrighted is used and it works offline. Scenes are not rendered; the user presses Render.

The project is created through the same endpoint functions the editor calls, so every value goes
through the normal validation.
"""
from __future__ import annotations

import hashlib
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from sqlalchemy.orm import Session

from app.config import FFMPEG_BIN, MEDIA_DIR
from app.db.models import Asset, Project
from app.domain import schemas
from app.domain.constants import AssetOrigin
from app.render.ffmpeg_utils import probe

W, H = 1920, 1080
TITLE = "Sample · A day in the city"


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
    img += np.clip(1 - d / (r * glow), 0, 1)[..., None] ** 2 * np.array(color) * 0.55
    img[d < r] = np.array(color)


def _hills(rng) -> Image.Image:
    img = _sky((40, 70, 140), (250, 170, 120), (255, 220, 170), 0.62)
    _sun(img, W * 0.68, H * 0.58, 70, (255, 236, 200), 6)
    pil = Image.fromarray(img.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(pil)
    for layer, (base, amp, col) in enumerate(((0.62, 90, (120, 90, 140)), (0.7, 70, (80, 60, 110)), (0.8, 60, (45, 38, 75)))):
        pts = [(0, H)]
        phase = rng.uniform(0, 6)
        for x in range(0, W + 40, 40):
            pts.append((x, H * base - amp * (0.6 * math.sin(x / 260 + phase) + 0.4 * math.sin(x / 97 + layer))))
        pts.append((W, H))
        d.polygon(pts, fill=col)
    return pil.filter(ImageFilter.GaussianBlur(0.6))


def _city(rng, night: bool) -> Image.Image:
    img = _sky((20, 24, 60), (60, 40, 90), (110, 60, 100), 0.7) if night else _sky((70, 120, 200), (170, 200, 235), (230, 235, 240), 0.7)
    if not night:
        _sun(img, W * 0.25, H * 0.25, 60, (255, 250, 230), 5)
    pil = Image.fromarray(img.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(pil)
    x = 0
    while x < W:
        bw, bh = int(rng.uniform(70, 170)), int(rng.uniform(H * 0.2, H * 0.62))
        body = (22, 22, 38) if night else (70, 85, 110)
        d.rectangle([x, H - bh, x + bw, H], fill=body)
        for wy in range(H - bh + 18, H - 20, 26):
            for wx in range(x + 10, x + bw - 12, 22):
                if rng.random() < (0.55 if night else 0.15):
                    c = (255, int(rng.uniform(190, 235)), 120) if night else (200, 220, 240)
                    d.rectangle([wx, wy, wx + 9, wy + 13], fill=c)
        x += bw + int(rng.uniform(4, 16))
    return pil


def _ff(*args):
    subprocess.run([FFMPEG_BIN, "-hide_banner", "-nostdin", "-loglevel", "error", "-y", *args], check=True, capture_output=True, timeout=120)


def make_media(folder: Path) -> dict[str, Path]:
    rng = np.random.default_rng(11)
    out = {"morning.jpg": folder / "sample-morning-hills.jpg", "afternoon.jpg": folder / "sample-afternoon-city.jpg",
           "night.jpg": folder / "sample-night-city.jpg", "music.mp3": folder / "sample-music.mp3", "whoosh.wav": folder / "sample-whoosh.wav",
           "chime.wav": folder / "sample-chime.wav"}
    _hills(rng).save(out["morning.jpg"], quality=90)
    _city(rng, night=False).save(out["afternoon.jpg"], quality=90)
    _city(rng, night=True).save(out["night.jpg"], quality=90)
    chord = "0.10*(sin(2*PI*220*t)+sin(2*PI*277.2*t)+sin(2*PI*329.6*t))*(0.6+0.4*sin(2*PI*0.25*t))"
    beat = "0.5*sin(2*PI*55*t*(1+2*exp(-mod(t,0.5)*30)))*exp(-mod(t,0.5)*9)"
    _ff("-f", "lavfi", "-i", f"aevalsrc='{beat}+{chord}':s=44100:d=24", "-af", "alimiter=limit=0.8,afade=t=out:st=21:d=3",
        "-c:a", "libmp3lame", "-q:a", "4", str(out["music.mp3"]))
    _ff("-f", "lavfi", "-i", "aevalsrc='(random(0)-0.5)*exp(-pow((t-0.6)*3,2))':s=44100:d=1.4", "-af", "bandpass=f=1500:w=1200,volume=4", str(out["whoosh.wav"]))
    _ff("-f", "lavfi", "-i", "aevalsrc='0.3*sin(2*PI*880*t)*exp(-t*6)+0.2*sin(2*PI*1320*t)*exp(-t*8)':s=44100:d=1.2", str(out["chime.wav"]))
    return out


def _register(db: Session, project_id: str, src: Path, kind: str) -> Asset:
    folder = Path(MEDIA_DIR) / project_id
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / src.name
    shutil.copyfile(src, dest)
    info = probe(str(dest))
    asset = Asset(project_id=project_id, type=kind, content_hash=hashlib.sha256(dest.read_bytes()).hexdigest(),
                  storage_key=str(dest.relative_to(MEDIA_DIR)), mime={"image": "image/jpeg", "audio": "audio/mpeg" if src.suffix == ".mp3" else "audio/wav"}[kind],
                  original_filename=src.name, width=info.width, height=info.height, duration_ms=info.duration_ms, origin=AssetOrigin.UPLOAD)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def create_sample_project(db: Session) -> Project:
    from app.api import projects as projects_api, scenes as scenes_api, stickers as stickers_api

    work = Path(tempfile.mkdtemp(prefix="sf-sample-"))
    try:
        media = make_media(work)
        project = projects_api.create_project(schemas.ProjectCreate(title=TITLE, language="en", aspect="16:9", fps=30), db)
        pid = project.id
        A = {k: _register(db, pid, p, "image" if p.suffix == ".jpg" else "audio") for k, p in media.items()}
        scene_ids = [s.id for s in db.get(Project, pid).scenes]

        def caption(**extra):
            return {"captions_enabled": True, "family": "Poppins", "size": 56, "color": "#FFFFFF", "outline_color": "#000000",
                    "outline_width": 3, "background": "none", "position": "bottom", **extra}
        karaoke = {"family": "Poppins", "size": 60, "bold": True, "case": "none", "color": "#FFFFFF", "outline_color": "#000000", "outline_width": 3,
                   "background": "none", "shadow": 0, "split": "phrases", "phrase_words": 4, "karaoke": True, "karaoke_style": "fill",
                   "highlight_color": "#FFD84D", "caption_animation": "none", "exit_animation": "none", "loop": "none"}

        plan = [
            ("Morning", "morning.jpg", "zoom_in", 6000, "Every city wakes up slowly, one window at a time.",
             caption(layers=[{"id": "T1", "kind": "text_plus", "text": "A DAY IN THE CITY", "x": 50, "y": 24, "size": 120, "family": "Bebas Neue",
                              "spacing": 10, "color": "#FFFFFF", "animation": "reveal-iris", "animation_ms": 1200, "start_ms": 0, "end_ms": 6000}]),
             "warm", {"leak": {"amount": 30, "speed": 30, "color": "warm"}}),
            ("Afternoon", "afternoon.jpg", "pan_right", 6000, "By noon the streets are full of people going somewhere.",
             caption(**karaoke), "teal_amber", {"flare": {"x": 25, "y": 25, "color": "#FFE2B0", "blend": "screen", "amount": 45, "drift": 20}}),
            ("Night", "night.jpg", "zoom_out", 7000, "And at night, the city tells its stories.",
             caption(typewriter=True, typewriter_sound=True, typewriter_volume=45), "vhs", {}),
        ]
        for sid, (title, img, motion, dur, text, font, effect, look) in zip(scene_ids, plan):
            scenes_api.add_shot(sid, schemas.ShotIn(asset_id=A[img].id, motion={"type": motion}), db)
            body = dict(title=title, original_text=text, spoken_text=text, subtitle_text=text, timing_mode="fixed",
                        requested_duration_ms=dur, font=font, effect_preset=effect, effect_intensity=70)
            if look:
                body["look"] = look
            scenes_api.update_scene(sid, schemas.SceneUpdate(**body), db)
        for sid, tr in zip(scene_ids[1:], ("dissolve", "circle_open")):
            scenes_api.update_scene(sid, schemas.SceneUpdate(transition_in={"type": tr, "duration_ms": 600}), db)
        # Stickers from the bundled library (skipped quietly if the library is not installed)
        try:
            sun = stickers_api.import_sticker(pid, "sun", db)
            arrow = stickers_api.import_sticker(pid, "bold-arrow-right", db)
            scenes_api.update_scene(scene_ids[0], schemas.SceneUpdate(overlays=[
                {"id": "st0", "asset_id": sun.id, "kind": "sticker", "x": 82, "y": 20, "width": 11, "border": 0, "radius": 0, "shadow": 0, "anim_in": "zoom", "anim_out": "none"}]), db)
            scenes_api.update_scene(scene_ids[1], schemas.SceneUpdate(overlays=[
                {"id": "st1", "asset_id": arrow.id, "kind": "sticker", "x": 20, "y": 60, "width": 10, "border": 0, "radius": 0, "shadow": 0, "anim_in": "fade", "anim_out": "none",
                 "keyframes": [{"t_ms": 0, "x": 12, "y": 60}, {"t_ms": 2500, "x": 30, "y": 60, "ease": "ease_in_out"}]}]), db)
        except Exception:   # a missing library or an older sticker id never blocks the sample
            db.rollback()
        clip = lambda cid, key, name, start, out, track, **k: {"id": cid, "asset_id": A[key].id, "name": name, "start_ms": start,
                                                               "source_in_ms": 0, "source_out_ms": out, "track": track, **k}
        fin = {"music": {"asset_id": A["music.mp3"].id, "volume": 45, "duck": 60, "fade_in_ms": 1500, "fade_out_ms": 2500},
               "audio_clips": [clip("wh1", "whoosh.wav", "Whoosh", 5400, 1400, "A3"), clip("ch1", "chime.wav", "Chime", 11600, 1200, "A4")],
               "timeline": {"version": 1, "audio_tracks": ["A3", "A4"], "tracks": {},
                            "markers": [{"id": "m1", "time_ms": 0, "duration_ms": 6000, "label": "Intro", "color": "blue"},
                                        {"id": "m2", "time_ms": 12000, "duration_ms": 0, "label": "Night falls", "color": "purple"}]}}
        projects_api.update_project(pid, schemas.ProjectUpdate(finishing=fin), db)
        db.expire_all()
        return db.get(Project, pid)
    finally:
        shutil.rmtree(work, ignore_errors=True)
