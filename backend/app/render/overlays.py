"""Picture-in-picture overlays: images or videos placed inside the scene.

Each overlay is a "card": the media scaled to its box, with rounded corners,
an optional border and a soft drop shadow. The static parts (shadow, border,
corner mask) are drawn once with Pillow as transparent PNGs; FFmpeg then only
has to composite per frame: scale, rotation, opacity, timing and the
entrance/exit animation. Overlays sit above the picture and its effects and
below captions and titles.

Overlay fields (all validated by clean_overlays):
  asset_id           image or video from this project
  x, y               centre of the card, % of frame width/height
  width              % of frame width (height follows the media's aspect)
  rotation           degrees, -180..180
  opacity            0..100
  radius             corner rounding, % of the card's shorter side (50 = pill/circle)
  border, border_color   width in px at 1080p, #RRGGBB
  shadow             0..100
  start_ms, end_ms   visible span within the scene (end None = scene end)
  anim_in, anim_out  none | fade | slide_left | slide_up | zoom
  anim_ms            animation length
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

ANIMS = ("none", "fade", "slide_left", "slide_up", "zoom")
DEFAULT_OVERLAY = {
    "asset_id": None, "x": 72.0, "y": 30.0, "width": 34.0, "rotation": 0, "opacity": 100,
    "radius": 6, "border": 6, "border_color": "#FFFFFF", "shadow": 60,
    "start_ms": 0, "end_ms": None, "anim_in": "fade", "anim_out": "fade", "anim_ms": 600,
    # extras: glide to an end position over the overlay's time, green screen, soft edges
    "x2": None, "y2": None, "chroma": None, "chroma_similarity": 30, "feather": 0,
}
_RANGES = {"x": (-50, 150), "y": (-50, 150), "width": (3, 100), "rotation": (-180, 180), "opacity": (0, 100),
           "radius": (0, 50), "border": (0, 40), "shadow": (0, 100), "start_ms": (0, 3_600_000), "anim_ms": (0, 5000),
           "chroma_similarity": (1, 100), "feather": (0, 100)}
MAX_OVERLAYS = 8


class OverlayError(ValueError):
    pass


def clean_overlays(raw, project_id: str, db) -> list[dict]:
    from app.db.models import Asset
    if not isinstance(raw, list):
        raise OverlayError("Overlays must be a list.")
    if len(raw) > MAX_OVERLAYS:
        raise OverlayError(f"A scene can have at most {MAX_OVERLAYS} overlays.")
    out = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict) or set(item) - set(DEFAULT_OVERLAY) - {"id"}:
            raise OverlayError(f"Overlay {i + 1} has unknown settings.")
        o = {**DEFAULT_OVERLAY, **item}
        asset = db.get(Asset, o["asset_id"]) if o["asset_id"] else None
        if not asset or asset.type not in ("image", "video") or asset.project_id != project_id:
            raise OverlayError(f"Overlay {i + 1}: choose an image or video from this project.")
        for key, (lo, hi) in _RANGES.items():
            v = o[key]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
                raise OverlayError(f"Overlay {i + 1}: {key} must be between {lo} and {hi}.")
        if o["end_ms"] is not None:
            if isinstance(o["end_ms"], bool) or not isinstance(o["end_ms"], (int, float)) or o["end_ms"] <= o["start_ms"]:
                raise OverlayError(f"Overlay {i + 1}: end must be after start.")
            o["end_ms"] = int(o["end_ms"])
        for key in ("x2", "y2"):
            if o[key] is not None and (isinstance(o[key], bool) or not isinstance(o[key], (int, float)) or not -50 <= o[key] <= 150):
                raise OverlayError(f"Overlay {i + 1}: end position must be between -50 and 150.")
        if o["chroma"] is not None and (not isinstance(o["chroma"], str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", o["chroma"])):
            raise OverlayError(f"Overlay {i + 1}: green-screen colour must look like #RRGGBB.")
        if not isinstance(o["border_color"], str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", o["border_color"]):
            raise OverlayError(f"Overlay {i + 1}: border colour must look like #RRGGBB.")
        for key in ("anim_in", "anim_out"):
            if o[key] not in ANIMS:
                raise OverlayError(f"Overlay {i + 1}: animation must be one of: {', '.join(ANIMS)}.")
        o["id"] = str(item.get("id") or f"ov{i}")[:40]
        for key in ("rotation", "opacity", "radius", "border", "shadow", "start_ms", "anim_ms", "chroma_similarity", "feather"):
            o[key] = int(round(o[key]))
        for key in ("x", "y", "width"):
            o[key] = round(float(o[key]), 2)
        out.append(o)
    return out


def _even(v: float) -> int:
    return max(2, int(round(v / 2)) * 2)


def card_images(o: dict, content_w: int, content_h: int, frame_h: int, cache: Path) -> tuple[str, str, int, int]:
    """Draw (once, cached) the card background (shadow + border) and the
    rounded-corner mask for the media. Returns (bg_png, mask_png, pad, border)."""
    from PIL import Image, ImageDraw, ImageFilter
    border = int(round(o["border"] * frame_h / 1080))
    radius = int(round(o["radius"] / 100 * min(content_w, content_h) + border))
    pad = int(round(max(content_w, content_h) * 0.05 * o["shadow"] / 100)) + 2
    key = hashlib.sha256(f"v2|{content_w}|{content_h}|{border}|{radius}|{pad}|{o['border_color']}|{o['shadow']}|{o.get('feather', 0)}".encode()).hexdigest()[:20]
    cache.mkdir(parents=True, exist_ok=True)
    bg_path, mask_path = cache / f"card_{key}.png", cache / f"mask_{key}.png"
    if not (bg_path.exists() and mask_path.exists()):
        cw, ch = content_w + 2 * border, content_h + 2 * border
        bg = Image.new("RGBA", (cw + 2 * pad, ch + 2 * pad), (0, 0, 0, 0))
        if o["shadow"]:
            shadow = Image.new("L", bg.size, 0)
            off = int(pad * 0.35)
            ImageDraw.Draw(shadow).rounded_rectangle([pad, pad + off, pad + cw - 1, pad + ch - 1 + off], radius, fill=int(150 * o["shadow"] / 100))
            shadow = shadow.filter(ImageFilter.GaussianBlur(max(1, pad * 0.45)))
            bg.paste((0, 0, 0, 255), (0, 0), shadow)
        if border:
            col = tuple(int(o["border_color"][i:i + 2], 16) for i in (1, 3, 5))
            ImageDraw.Draw(bg).rounded_rectangle([pad, pad, pad + cw - 1, pad + ch - 1], radius, fill=col + (255,))
        bg.save(bg_path)
        mask = Image.new("L", (content_w, content_h), 0)
        feather = o.get("feather", 0) / 100 * min(content_w, content_h) * 0.18
        inset = int(feather * 1.2)
        ImageDraw.Draw(mask).rounded_rectangle([inset, inset, content_w - 1 - inset, content_h - 1 - inset], max(0, radius - border), fill=255)
        if feather:
            mask = mask.filter(ImageFilter.GaussianBlur(feather))
        mask.save(mask_path)
    return str(bg_path), str(mask_path), pad, border


def _ease(p: str) -> str:
    return f"(0.5-0.5*cos(PI*{p}))"


def build_overlay_pass(overlays: list[dict], assets: dict, frame_w: int, frame_h: int, fps: int,
                       duration_ms: int, cache: Path, base: str = "0:v", first_input: int = 1,
                       final: str = "vout") -> tuple[list[str], str]:
    """Return (extra ffmpeg input args, filter graph) compositing all overlays
    onto `base` in list order (later = on top). Output label [final]."""
    dur = duration_ms / 1000
    inputs: list[str] = []
    graph: list[str] = []
    idx = first_input
    for n, o in enumerate(overlays):
        asset = assets[o["asset_id"]]
        aw, ah = (asset.width or 16), (asset.height or 9)
        cw = _even(frame_w * o["width"] / 100)
        ch = _even(cw * ah / aw)
        bg, mask, pad, border = card_images(o, cw, ch, frame_h, cache)
        src = asset.path
        if asset.type == "image":
            inputs += ["-loop", "1", "-framerate", str(fps), "-t", f"{dur:.3f}", "-i", src]
        else:
            inputs += ["-stream_loop", "-1", "-t", f"{dur:.3f}", "-i", src]
        inputs += ["-loop", "1", "-framerate", str(fps), "-t", f"{dur:.3f}", "-i", mask,
                   "-loop", "1", "-framerate", str(fps), "-t", f"{dur:.3f}", "-i", bg]
        m, k, b = idx, idx + 1, idx + 2
        idx += 3
        st = o["start_ms"] / 1000
        en = min(dur, o["end_ms"] / 1000) if o["end_ms"] else dur
        d = min(o["anim_ms"] / 1000, max(0.05, (en - st) / 2))
        chain = [f"[{m}:v]fps={fps},scale={cw}:{ch}:force_original_aspect_ratio=increase,crop={cw}:{ch},format=rgba,setsar=1[c{n}]",
                 f"[{k}:v]format=gray,scale={cw}:{ch}[m{n}]"]
        if o.get("chroma"):
            # Green screen: colorkey replaces alpha, so key first and multiply its
            # alpha with the rounded/feathered mask instead of letting it win.
            sim = 0.02 + 0.5 * o["chroma_similarity"] / 100
            chain += [f"[c{n}]colorkey={o['chroma'].replace('#', '0x')}:{sim:.3f}:0.08,split=2[ck{n}][ks{n}]",
                      f"[ks{n}]alphaextract[ka{n}]", f"[ka{n}][m{n}]blend=all_mode=multiply[km{n}]",
                      f"[ck{n}][km{n}]alphamerge[cm{n}]"]
        else:
            chain.append(f"[c{n}][m{n}]alphamerge[cm{n}]")
        chain += [
                 f"[{b}:v]format=rgba[b{n}]",
                 f"[b{n}][cm{n}]overlay=x={pad + border}:y={pad + border}:format=auto"]
        post = []
        if o["rotation"]:
            post.append(f"rotate=a={o['rotation']}*PI/180:c=none:ow=rotw({o['rotation']}*PI/180):oh=roth({o['rotation']}*PI/180)")
        if o["opacity"] < 100:
            post.append(f"colorchannelmixer=aa={o['opacity'] / 100:.3f}")
        if o["anim_in"] != "none" and d > 0:
            post.append(f"fade=t=in:st={st:.3f}:d={d:.3f}:alpha=1")
        if o["anim_out"] != "none" and d > 0:
            post.append(f"fade=t=out:st={max(st, en - d):.3f}:d={d:.3f}:alpha=1")
        p_in = _ease(f"clip((t-{st:.3f})/{d:.3f},0,1)") if d > 0 else "1"
        p_out = _ease(f"clip((t-{en - d:.3f})/{d:.3f},0,1)") if d > 0 else "0"
        zoom = []
        if o["anim_in"] == "zoom":
            zoom.append(f"(0.6+0.4*{p_in})")
        if o["anim_out"] == "zoom":
            zoom.append(f"(1-0.4*{p_out})")
        if zoom:
            z = "*".join(zoom)
            post.append(f"scale=w='max(2,trunc(iw*{z}/2)*2)':h='max(2,trunc(ih*{z}/2)*2)':eval=frame")
        graph.append(";".join(chain) + ("," + ",".join(post) if post else "") + f"[o{n}]")
        cx, cy = frame_w * o["x"] / 100, frame_h * o["y"] / 100
        dx = dy = "0"
        if o.get("x2") is not None or o.get("y2") is not None:
            # Glide from the start position to the end position over the overlay's time.
            glide = _ease(f"clip((t-{st:.3f})/{max(0.05, en - st):.3f},0,1)")
            ex = frame_w * (o["x2"] if o.get("x2") is not None else o["x"]) / 100
            ey = frame_h * (o["y2"] if o.get("y2") is not None else o["y"]) / 100
            dx, dy = f"{ex - cx:.1f}*{glide}", f"{ey - cy:.1f}*{glide}"
        dist_x, dist_y = frame_w * 0.35, frame_h * 0.35
        if o["anim_in"] == "slide_left":
            dx = f"({dx})+{dist_x:.1f}*(1-{p_in})"
        if o["anim_in"] == "slide_up":
            dy = f"({dy})+{dist_y:.1f}*(1-{p_in})"
        if o["anim_out"] == "slide_left":
            dx = f"({dx})-{dist_x:.1f}*{p_out}"
        if o["anim_out"] == "slide_up":
            dy = f"({dy})-{dist_y:.1f}*{p_out}"
        out = final if n == len(overlays) - 1 else f"ov{n}out"
        graph.append(f"[{base}][o{n}]overlay=x='{cx:.1f}-w/2+{dx}':y='{cy:.1f}-h/2+{dy}':"
                     f"enable='between(t,{st:.3f},{en:.3f})':eval=frame:format=auto[{out}]")
        base = out
    return inputs, ";".join(graph)
