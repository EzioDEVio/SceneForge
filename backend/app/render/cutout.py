"""Subject cutout (beta): AI background removal with a local ONNX model.

Models are the ONNX conversions published with rembg (MIT) on GitHub releases:
  isnet  = "isnet-general-use" (IS-Net / DIS, Apache-2.0), 1024 x 1024 input, ~170 MB, better edges
  u2netp = "u2netp" (U^2-Net small, Apache-2.0), 320 x 320 input, ~4.6 MB, fast
They download once, on first use, into the models folder (~/.sceneforge/models/cutout,
or SCENEFORGE_CUTOUT_MODEL_DIR). Download is atomic: written to <name>.partial,
checked (size and MD5), then renamed. Inference runs on the CPU with onnxruntime.

Pre/post-processing matches rembg's sessions (base.normalize + predict):
  RGB -> resize (LANCZOS) to the model size -> divide by the image max ->
  (x - mean) / std per channel -> NCHW float32; output[0][:, 0] is min-max
  normalised to 0..1, then resized (LANCZOS) back to the source size.
  u2netp: mean (0.485, 0.456, 0.406), std (0.229, 0.224, 0.225)
  isnet:  mean (0.5, 0.5, 0.5),       std (1.0, 1.0, 1.0)
"""
from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path

MODELS = {
    "isnet": {"file": "isnet-general-use.onnx", "size": 1024, "mean": (0.5, 0.5, 0.5), "std": (1.0, 1.0, 1.0),
              "md5": "fc16ebd8b0c10d971d3513d564d01e29", "approx_mb": 170, "label": "IS-Net general use (best quality)",
              "url": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx"},
    "u2netp": {"file": "u2netp.onnx", "size": 320, "mean": (0.485, 0.456, 0.406), "std": (0.229, 0.224, 0.225),
               "md5": "8e83ca70e441ab06c318d82300c84806", "approx_mb": 4.6, "label": "U²-Net small (fast)",
               "url": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx"},
}
DEFAULT_MODEL = "isnet"
EDGES = ("soft", "crisp")
MAX_PIXELS = 40_000_000

_sessions: dict[str, object] = {}
_locks = {k: threading.Lock() for k in MODELS}
_progress: dict[str, dict] = {}


class CutoutError(RuntimeError):
    pass


def model_dir() -> Path:
    return Path(os.environ.get("SCENEFORGE_CUTOUT_MODEL_DIR", Path.home() / ".sceneforge" / "models" / "cutout"))


def model_path(model: str) -> Path:
    return model_dir() / MODELS[model]["file"]


def status() -> dict:
    out = []
    for key, m in MODELS.items():
        p = model_path(key)
        ok = p.is_file() and p.stat().st_size > 1_000_000
        out.append({"id": key, "label": m["label"], "file": m["file"], "approx_mb": m["approx_mb"], "downloaded": ok,
                    "bytes": p.stat().st_size if ok else 0, "url": m["url"], "download": _progress.get(key)})
    return {"folder": str(model_dir()), "default": DEFAULT_MODEL, "models": out, "source": "github.com (rembg releases)"}


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_model(model: str) -> Path:
    """Return the model path, downloading it on first use (atomic, verified)."""
    if model not in MODELS:
        raise CutoutError(f"Unknown cutout model '{model}'. Choose one of: {', '.join(MODELS)}.")
    dest = model_path(model)
    with _locks[model]:
        if dest.is_file() and dest.stat().st_size > 1_000_000:
            return dest
        import requests
        m = MODELS[model]
        folder = dest.parent
        partial = dest.with_name(dest.name + ".partial")
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise CutoutError(f"Could not create the models folder {folder}: {e}")
        _progress[model] = {"done": 0, "total": int(m["approx_mb"] * 1_000_000)}
        try:
            with requests.get(m["url"], stream=True, timeout=(15, 60)) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length") or 0) or _progress[model]["total"]
                _progress[model] = {"done": 0, "total": total}
                with open(partial, "wb") as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
                        _progress[model]["done"] += len(chunk)
            if partial.stat().st_size <= 1_000_000:
                raise CutoutError("the downloaded file is too small")
            if _md5(partial) != m["md5"]:
                raise CutoutError("the downloaded file failed its checksum")
            os.replace(partial, dest)
        except Exception as e:
            partial.unlink(missing_ok=True)
            reason = str(e) if isinstance(e, CutoutError) else type(e).__name__
            raise CutoutError(
                f"Could not download the background-removal model ({m['file']}, ~{m['approx_mb']} MB) from github.com: {reason}. "
                f"Check your internet connection and try again, or download {m['url']} yourself and place it in {folder}.")
        finally:
            _progress.pop(model, None)
    return dest


def _session(model: str):
    path = ensure_model(model)
    key = str(path)
    if key not in _sessions:
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        try:
            _sessions[key] = ort.InferenceSession(key, sess_options=opts, providers=["CPUExecutionProvider"])
        except Exception as e:
            raise CutoutError(f"The cutout model in {path.parent} could not be loaded ({e}). Delete {path.name} there and try again to re-download it.")
    return _sessions[key]


def predict_matte(img, model: str = DEFAULT_MODEL):
    """Alpha matte (PIL 'L', source size) for an RGB PIL image."""
    import numpy as np
    from PIL import Image
    m = MODELS[model]
    sess = _session(model)
    size = (m["size"], m["size"])
    arr = np.array(img.convert("RGB").resize(size, Image.Resampling.LANCZOS)).astype(np.float64)
    arr = arr / max(float(arr.max()), 1e-6)
    x = np.zeros_like(arr)
    for c in range(3):
        x[:, :, c] = (arr[:, :, c] - m["mean"][c]) / m["std"][c]
    x = np.expand_dims(x.transpose((2, 0, 1)), 0).astype(np.float32)
    pred = sess.run(None, {sess.get_inputs()[0].name: x})[0][:, 0, :, :]
    hi, lo = float(pred.max()), float(pred.min())
    pred = np.squeeze((pred - lo) / (hi - lo if hi > lo else 1.0))
    mask = Image.fromarray((pred * 255).astype("uint8"), mode="L")
    return mask.resize(img.size, Image.Resampling.LANCZOS)


def refine(mask, edge: str = "soft", feather: int = 0):
    """'crisp' pushes the matte towards 0/255 (removes faint haze); feather blurs the edge (px)."""
    import numpy as np
    from PIL import Image, ImageFilter
    if edge == "crisp":
        a = np.asarray(mask).astype(np.float32) / 255
        a = np.clip((a - 0.35) / 0.3, 0, 1)
        mask = Image.fromarray((a * a * (3 - 2 * a) * 255).astype("uint8"), mode="L")
    if feather:
        mask = mask.filter(ImageFilter.GaussianBlur(feather))
    return mask


def cutout_file(src: str, dest: str, model: str = DEFAULT_MODEL, edge: str = "soft", feather: int = 0) -> tuple[int, int]:
    """Write an RGBA PNG of the subject (background transparent). Returns (w, h)."""
    from PIL import Image, ImageChops
    if edge not in EDGES:
        raise CutoutError(f"Edge must be one of: {', '.join(EDGES)}.")
    if not 0 <= int(feather) <= 20:
        raise CutoutError("Feather must be between 0 and 20 px.")
    try:
        img = Image.open(src)
        img.load()
    except Exception as e:
        raise CutoutError(f"This image could not be read: {e}")
    if img.width * img.height > MAX_PIXELS:
        raise CutoutError("This image is larger than 40 megapixels. Use a smaller copy for background removal.")
    alpha = img.getchannel("A") if "A" in img.getbands() else None
    rgb = img.convert("RGB")
    mask = refine(predict_matte(rgb, model), edge, int(feather))
    if alpha is not None:
        mask = ImageChops.darker(mask, alpha)
    out = rgb.convert("RGBA")
    out.putalpha(mask)
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    out.save(dest, optimize=False)
    return out.size


def frame_layer(cutout: str, dest: str, fit: str, out_w: int, out_h: int) -> None:
    """Place a cutout on a transparent frame-sized canvas exactly as the shot is
    fitted by the renderer (filters.build_cover_static_chain / build_contain_chain),
    so the layer lines up with the picture underneath."""
    from PIL import Image
    im = Image.open(cutout).convert("RGBA")
    iw, ih = im.size
    canvas = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    if fit == "cover":
        s = max(out_w / iw, out_h / ih)
        w, h = max(out_w, round(iw * s)), max(out_h, round(ih * s))
        big = im.resize((w, h), Image.Resampling.LANCZOS)
        x, y = (w - out_w) // 2, (h - out_h) // 2
        canvas = big.crop((x, y, x + out_w, y + out_h))
    else:  # contain / contain_blur: centred, letterboxed
        s = min(out_w / iw, out_h / ih)
        w, h = min(out_w, round(iw * s)), min(out_h, round(ih * s))
        canvas.paste(im.resize((w, h), Image.Resampling.LANCZOS), ((out_w - w) // 2, (out_h - h) // 2))
    canvas.save(dest)
