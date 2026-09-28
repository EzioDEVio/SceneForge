"""Small render smoke test for the extra SceneForge color-filter presets."""
import pathlib, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "backend"))

from app.domain.constants import EffectPreset
from app.render.filters import build_effect_chain

cases = {
    "teal_amber": EffectPreset.TEAL_AMBER,
    "pastel": EffectPreset.PASTEL,
    "bleach_bypass": EffectPreset.BLEACH_BYPASS,
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
