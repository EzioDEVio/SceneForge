"""Large exports assemble in batches (bounded memory) with the same timing as one pass."""
import os, pathlib, subprocess, sys, tempfile
root = pathlib.Path(__file__).resolve().parents[2]
tmp = tempfile.TemporaryDirectory(prefix="sf-batch-"); os.environ["SCENEFORGE_DATA_DIR"] = tmp.name
sys.path.insert(0, str(root / "backend"))
from types import SimpleNamespace
import numpy as np
from app.render import renderer
from app.render.renderer import RenderContext, _render_export_core
from app.render.ffmpeg_utils import probe

colors = ["red", "green", "blue", "yellow", "cyan", "magenta", "white", "orange", "purple", "gray", "pink", "brown"]
paths, scenes = {}, []
for i, c in enumerate(colors):
    p = pathlib.Path(tmp.name) / f"s{i}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={c}:s=160x90:r=25:d=2",
                    "-f", "lavfi", "-i", f"sine=frequency={300 + 40 * i}:duration=2", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", "-shortest", str(p)], check=True)
    paths[f"s{i}"] = str(p); scenes.append(SimpleNamespace(id=f"s{i}"))
types = ["cut", "dissolve", "fade_through_black", "wipe_left", "cut", "dissolve", "cut", "slide", "dissolve", "cut", "circle_open"]
transitions = [{"type": t, "duration_ms": 0 if t == "cut" else 400} for t in types]
project = SimpleNamespace(id="batch", width=160, height=90, fps=25)
n = 0
def check(name, ok):
    global n; assert ok, name; n += 1; print("PASS " + name, flush=True)

renderer.EXPORT_BATCH = 100
single = _render_export_core(project, scenes, paths, transitions, RenderContext())
renderer.EXPORT_BATCH = 5
batched = _render_export_core(project, scenes, paths, transitions, RenderContext())
ds, db = probe(single).duration_ms, probe(batched).duration_ms
vlen = lambda f: float(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration", "-of", "csv=p=0", f]).decode().strip()) * 1000
check(f"batched video length matches one pass ({vlen(single):.0f} vs {vlen(batched):.0f} ms)", abs(vlen(single) - vlen(batched)) <= 45)
def frame(path, t):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-ss", str(t), "-i", path, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    return np.frombuffer(raw, np.uint8).reshape(90, 160, 3).mean((0, 1))
for t in (1.0, 9.3, 15.0, 20.5):
    check(f"picture at {t}s matches one-pass export", np.abs(frame(single, t) - frame(batched, t)).max() < 12)
def rms(path, a, b):
    pcm = subprocess.check_output(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", "8000", "-"])
    x = np.frombuffer(pcm, np.float32)[int(a * 8000):int(b * 8000)]; return float(np.sqrt(np.mean(x ** 2)))
check("sound is present through the whole batched export", min(rms(batched, t, t + .5) for t in (0.5, 6, 12, 18, 21)) > .02)
def tone(path, t):
    pcm = subprocess.check_output(["ffmpeg", "-v", "error", "-ss", str(t), "-t", "0.25", "-i", path, "-f", "f32le", "-ac", "1", "-ar", "8000", "-"])
    x = np.frombuffer(pcm, np.float32); f = np.abs(np.fft.rfft(x)); return float(np.fft.rfftfreq(len(x), 1 / 8000)[f.argmax()])
for t in (8.9, 9.6, 17.4, 18.2):
    check(f"sound at {t}s (around a batch join) matches one pass ({tone(single, t):.0f} vs {tone(batched, t):.0f} Hz)", abs(tone(single, t) - tone(batched, t)) <= 8)
check("no intermediate batch files are left behind", not list(pathlib.Path(tmp.name, "tmp").glob("export_*.mkv")))
check(f"batched picture and sound end together ({db} ms file, {vlen(batched):.0f} ms video)", abs(db - vlen(batched)) <= 45)
print(f"{n} export batching checks passed")
