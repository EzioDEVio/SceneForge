"""Render smoke test for the added color-filter and creative-effect presets."""
import pathlib, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "backend"))

from app.domain.constants import EffectPreset, FitMode
from app.render.filters import build_effect_chain, build_shot_video_chain

cases = {
    "teal_amber": EffectPreset.TEAL_AMBER,
    "pastel": EffectPreset.PASTEL,
    "bleach_bypass": EffectPreset.BLEACH_BYPASS,
    "chromatic_split": EffectPreset.CHROMATIC_SPLIT,
    "motion_trail": EffectPreset.MOTION_TRAIL,
}
for label, preset in cases.items():
    chain = build_effect_chain(preset, 100)
    assert chain, f"{label} did not produce a render filter"
    run = subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=160x90:d=0.2:r=10",
         "-vf", chain, "-f", "null", "-"], capture_output=True, text=True,
    )
    assert run.returncode == 0, f"{label} failed to render: {run.stderr[-500:]}"
    print(f"PASS {label} filter renders with FFmpeg")

for label in ("chromatic_split", "motion_trail"):
    graph, _ = build_shot_video_chain(
        FitMode.COVER, {"type": "static"}, 160, 90, 10, 3,
        cases[label].value, 100,
    )
    run = subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=160x90:d=0.3:r=10",
         "-filter_complex", graph, "-map", "[vout]", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    assert run.returncode == 0, f"{label} failed through the scene render graph: {run.stderr[-500:]}"
    print(f"PASS {label} renders through the full scene filter graph")
