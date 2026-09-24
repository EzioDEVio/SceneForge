"""FFmpeg filter-graph fragment builders: fit/crop, motion (zoompan-based
Ken Burns family), and color-grade effect presets.

All motion types (static, zoom in/out, pan, close-up, ken burns) resolve to
one deterministic start/end (focal_x, focal_y, scale) triple and are driven
through a single zoompan expression parameterised by the output frame index
`on` and the fixed total frame count `D`. This works uniformly for looped
still images *and* real video frames, so motion is honestly supported on
both asset types (not just images).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.constants import EffectPreset, FitMode, MotionType

# (focal_x0, focal_y0, scale0, focal_x1, focal_y1, scale1)
_MOTION_PRESETS: dict[str, tuple[float, float, float, float, float, float]] = {
    MotionType.STATIC: (0.5, 0.5, 1.0, 0.5, 0.5, 1.0),
    MotionType.ZOOM_IN: (0.5, 0.5, 1.0, 0.5, 0.5, 1.18),
    MotionType.ZOOM_OUT: (0.5, 0.5, 1.18, 0.5, 0.5, 1.0),
    MotionType.PAN_LEFT: (0.68, 0.5, 1.15, 0.32, 0.5, 1.15),
    MotionType.PAN_RIGHT: (0.32, 0.5, 1.15, 0.68, 0.5, 1.15),
    MotionType.PAN_UP: (0.5, 0.68, 1.15, 0.5, 0.32, 1.15),
    MotionType.PAN_DOWN: (0.5, 0.32, 1.15, 0.5, 0.68, 1.15),
    MotionType.DIAGONAL_UP: (0.3, 0.7, 1.25, 0.7, 0.3, 1.25),
    MotionType.DIAGONAL_DOWN: (0.3, 0.3, 1.25, 0.7, 0.7, 1.25),
    MotionType.PUSH_LEFT: (0.65, 0.5, 1.05, 0.3, 0.5, 1.35),
    MotionType.PULL_RIGHT: (0.3, 0.5, 1.35, 0.65, 0.5, 1.05),
    MotionType.CLOSE_UP: (0.5, 0.5, 1.0, 0.5, 0.5, 1.4),
}

MAX_SUPPORTED_SCALE = 1.5  # overscan ceiling; UI warns above this


@dataclass
class MotionPlan:
    fx0: float
    fy0: float
    z0: float
    fx1: float
    fy1: float
    z1: float


def resolve_motion(motion_json: dict) -> MotionPlan:
    mtype = motion_json.get("type", MotionType.STATIC)
    if mtype == MotionType.KEN_BURNS:
        start = motion_json.get("start", {"x": 0.5, "y": 0.5, "scale": 1.0})
        end = motion_json.get("end", {"x": 0.5, "y": 0.5, "scale": 1.0})
        return MotionPlan(start["x"], start["y"], start["scale"], end["x"], end["y"], end["scale"])
    preset = _MOTION_PRESETS.get(mtype, _MOTION_PRESETS[MotionType.STATIC])
    return MotionPlan(*preset)


def overscan_warning(plan: MotionPlan) -> str | None:
    peak = max(plan.z0, plan.z1)
    if peak > MAX_SUPPORTED_SCALE:
        return (
            f"Requested scale {peak:.2f} exceeds the {MAX_SUPPORTED_SCALE} overscan ceiling; "
            "clamped to avoid sampling outside the upscaled source frame."
        )
    return None


def build_cover_motion_chain(
    plan: MotionPlan,
    out_w: int,
    out_h: int,
    fps: int,
    total_frames: int,
    upscale_factor: float | None = None,
) -> str:
    """cover fit + animated zoom/pan (Ken Burns family), for image or video input.

    Deliberately does NOT use FFmpeg's `zoompan` filter. `zoompan` is
    well known (both in community reports and confirmed by direct
    benchmarking during this project) to be dramatically slower than an
    equivalent `scale` + `crop` combination — recreating its internal
    scaling context in a way that made a single 5s 1080p shot take
    ~100s. The same visual effect is achieved here with three cheap,
    well-optimized stages instead:
      1. one-time cover scale to a baseline that fills the canvas
      2. a `scale` filter with `eval=frame` animating the zoom level
         (confirmed by direct testing to genuinely re-evaluate per frame,
         unlike `crop`'s width/height which are eval='init'-only)
      3. a `crop` to the final constant output size, with per-frame x/y
         (crop's x/y DO support eval=frame, by default) implementing pan
         and focal-point tracking
    Benchmarked end-to-end at full 1920x1080 for a 5s shot: ~2s versus
    ~100s+ for the old zoompan-based chain — roughly a 50x speedup, with
    no loss of the deterministic start/end (focal_x, focal_y, scale)
    contract shots already declare.
    """
    z0 = min(plan.z0, MAX_SUPPORTED_SCALE)
    z1 = min(plan.z1, MAX_SUPPORTED_SCALE)
    d = max(total_frames, 1)
    denom = max(d - 1, 1)

    # t: normalized progress through the shot, 0..1, keyed to frame number
    t = f"(n/{denom})"
    zt = f"({z0}+({z1}-{z0})*{t})"
    fx = f"({plan.fx0}+({plan.fx1}-{plan.fx0})*{t})"
    fy = f"({plan.fy0}+({plan.fy1}-{plan.fy0})*{t})"
    # x/y here operate on crop's input dims (iw/ih), which at this point
    # in the chain are the *animated* scaled size from stage 2 — ffmpeg
    # resolves iw/ih per-frame automatically, so this tracks the zoom
    # without Python needing to know the numeric baseline size.
    x_expr = f"clip({fx}*iw-{out_w}/2,0,iw-{out_w})"
    y_expr = f"clip({fy}*ih-{out_h}/2,0,ih-{out_h})"

    stage_a = f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase"
    stage_b = f"scale=w='ceil(iw*({zt})/2)*2':h='ceil(ih*({zt})/2)*2':eval=frame"
    stage_c = f"crop={out_w}:{out_h}:x='{x_expr}':y='{y_expr}'"
    return f"{stage_a},{stage_b},{stage_c}"


def build_contain_chain(out_w: int, out_h: int, blurred_bg: bool) -> str:
    if not blurred_bg:
        return (
            f"scale={out_w}:{out_h}:force_original_aspect_ratio=decrease,"
            f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2:color=black"
        )
    # blurred cover background + sharp contain foreground, composited.
    return (
        f"split=2[bg][fg];"
        f"[bg]scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
        f"crop={out_w}:{out_h},gblur=sigma=20[bgblur];"
        f"[fg]scale={out_w}:{out_h}:force_original_aspect_ratio=decrease[fgs];"
        f"[bgblur][fgs]overlay=(W-w)/2:(H-h)/2"
    )


_EFFECT_FILTERS: dict[str, str] = {
    EffectPreset.ORIGINAL: "",
    EffectPreset.BLACK_AND_WHITE: "hue=s=0",
    EffectPreset.SEPIA: (
        "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131:0"
    ),
    EffectPreset.WARM: "eq=gamma_r=1.06:gamma_b=0.94:saturation=1.08",
    EffectPreset.COOL: "eq=gamma_b=1.08:gamma_r=0.95:saturation=0.96",
    EffectPreset.VINTAGE: "curves=preset=vintage",
    EffectPreset.VIGNETTE: "vignette=PI/4",
    EffectPreset.SOFT_GLOW: "gblur=sigma=6:steps=1",
    EffectPreset.CINEMATIC: "colorbalance=bs=.12:rs=-.05:rh=.10:bh=-.08,eq=contrast=1.12:saturation=.85",
    EffectPreset.NOIR: "hue=s=0,eq=contrast=1.45:brightness=-.03,vignette=PI/4",
    EffectPreset.SHARPEN: "unsharp=5:5:1.2:5:5:0",
    EffectPreset.NEGATIVE: "negate",
    EffectPreset.FILM_GRAIN: "noise=alls=24:allf=t+u",
    EffectPreset.HIGH_CONTRAST: "eq=contrast=1.35:saturation=1.12",
    EffectPreset.FADED: "eq=contrast=0.8:brightness=0.07:saturation=0.8",
    EffectPreset.DREAM: "gblur=sigma=1.5,eq=brightness=0.04:saturation=0.8",
    # Desaturated vintage grade + heavier grain + vignette — an "old
    # film reel" look, distinct from the lighter "Vintage" preset.
    EffectPreset.OLD_FILM: "curves=preset=vintage,eq=saturation=0.75:contrast=1.05,noise=alls=22:allf=t+u,vignette=PI/3.5",
}


# ---------------------------------------------------------------------------
# Glitch: full-frame slice displacement + RGB split + noise, in bursts.
# ---------------------------------------------------------------------------
GLITCH_BLOCKS = {"small": 16, "medium": 10, "large": 6}
GLITCH_BURST_PERIOD_S = 1.2


def _glitch_gate(speed: float, strength: float) -> str:
    """1 during a glitch burst. `speed` multiplies how often bursts occur
    (1.0 = every 1.2 s, 2.0 = every 0.6 s). Burst length is in real seconds
    and grows with strength, capped so a gap always remains between bursts."""
    period = GLITCH_BURST_PERIOD_S / speed
    burst = min(0.12 + 0.2 * strength, period * 0.6)
    return f"lt(mod(t,{period:.4f}),{burst:.4f})"


def build_glitch_chain(strength: float, speed: float = 1.0, block: str = "medium", width: int = 1920) -> str:
    """Every horizontal band of the frame can tear sideways — the bands tile
    the whole height, so the distortion covers the full frame rather than a
    few fixed strips. Deterministic (no RNG) so renders are reproducible.

    strength 0..1 drives tear distance, how many bands tear at once, burst
    length, RGB split and noise. speed 0.25..4 scales burst frequency and how
    fast bands jitter. block chooses band height (small = many thin bands).
    """
    s = max(0.0, min(1.0, strength))
    v = max(0.25, min(4.0, speed))
    n = GLITCH_BLOCKS.get(block, GLITCH_BLOCKS["medium"])
    gate = _glitch_gate(v, s)
    amp = 0.015 + 0.075 * s                      # fraction of frame width
    threshold = 0.55 - 1.05 * s                  # lower = more bands tear
    labels = "".join(f"[b{i}]" for i in range(n))
    parts = [f"split={n + 1}[g0]{labels}"]
    prev = "g0"
    for i in range(n):
        f1 = 17 + 7.3 * i                        # incommensurate per-band rates
        ph = 1.7 * i
        parts.append(f"[b{i}]crop=iw:ceil(ih/{n}):0:ih*{i}/{n}[s{i}]")
        x = f"W*{amp:.4f}*sin(t*{f1 * v:.3f}+{ph:.2f})"
        enable = f"{gate}*gt(sin(t*{(5.1 + 2.9 * i) * v:.3f}+{ph:.2f}),{threshold:.3f})"
        nxt = f"g{i + 1}"
        parts.append(f"[{prev}][s{i}]overlay=x='{x}':y=H*{i}/{n}:enable='{enable}'[{nxt}]")
        prev = nxt
    shift = max(1, int(round(width * (0.002 + 0.012 * s))))   # 4..27 px at 1080p
    noise = int(round(6 + 22 * s))
    parts.append(
        f"[{prev}]rgbashift=rh={shift}:bh=-{shift}:gv={max(1, shift // 6)}:enable='{gate}',"
        f"noise=alls={noise}:allf=t+u:enable='{gate}'"
    )
    return ";".join(parts)


# ---------------------------------------------------------------------------
# Adjustments (per-scene sliders). All values are integers; 0 = no change.
# ---------------------------------------------------------------------------
ADJUST_RANGES = {
    "exposure": (-100, 100), "contrast": (-100, 100), "saturation": (-100, 100),
    "vibrance": (-100, 100), "temperature": (-100, 100), "tint": (-100, 100),
    "highlights": (-100, 100), "shadows": (-100, 100),
    "sharpen": (0, 100), "vignette": (0, 100), "grain": (0, 100),
}


def clean_adjust(raw: dict | None) -> dict:
    out = {}
    for key, (lo, hi) in ADJUST_RANGES.items():
        value = (raw or {}).get(key, 0)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        value = int(round(max(lo, min(hi, value))))
        if value:
            out[key] = value
    return out


def build_adjust_chain(adjust: dict | None) -> tuple[str | None, str | None]:
    """Spatial adjustments only; colour controls are baked into the grade LUT
    (render/grade.py). Returns (detail, finishing): sharpen runs straight
    after the grade, vignette and grain run last so they sit on top of the
    final look like real lens and film artefacts."""
    a = clean_adjust(adjust)
    detail = f"unsharp=5:5:{a['sharpen'] / 100 * 1.6:.3f}:5:5:0" if "sharpen" in a else None
    finishing: list[str] = []
    if "vignette" in a:
        finishing.append(f"vignette=angle={0.15 + a['vignette'] / 100 * 0.95:.3f}")
    if "grain" in a:
        finishing.append(f"noise=alls={max(1, round(a['grain'] * 0.35))}:allf=t+u")
    return detail, (",".join(finishing) or None)


def build_grade_chain(grade_lut_path: str | None) -> str | None:
    """One lut3d pass (planar RGB is the fastest input for lut3d)."""
    from app.render.ffmpeg_utils import escape_path_for_filter
    if not grade_lut_path:
        return None
    return f"format=gbrp,lut3d=file='{escape_path_for_filter(grade_lut_path)}':interp=tetrahedral"




def build_effect_chain(preset: str, intensity: int, glitch: dict | None = None, width: int = 1920) -> str | None:
    """Returns a filter fragment to append after label splitting, or None
    for 'original'/0 intensity (no-op — cheapest path, and Original always
    disables other looks per spec)."""
    if preset == EffectPreset.ORIGINAL or intensity <= 0:
        return None
    if preset == EffectPreset.GLITCH:
        g = glitch or {}
        return build_glitch_chain(intensity / 100, float(g.get("speed", 1.0)), str(g.get("block", "medium")), width)
    effect = _EFFECT_FILTERS.get(preset)
    if not effect:
        return None
    if preset == EffectPreset.SOFT_GLOW:
        # screen-blend a blurred copy over the original for a glow look.
        alpha = max(0.0, min(intensity, 100)) / 100.0
        return (
            f"split=2[base][glow];[glow]{effect}[glowed];"
            f"[base][glowed]blend=all_mode=screen:all_opacity={alpha:.3f}"
        )
    if intensity >= 100:
        return effect
    alpha = max(0.0, min(intensity, 100)) / 100.0
    return f"split=2[base][fx];[fx]{effect}[fxed];[base][fxed]blend=all_mode=normal:all_opacity={alpha:.3f}"


def is_static_plan(plan: MotionPlan) -> bool:
    return (
        plan.z0 == 1.0 and plan.z1 == 1.0
        and plan.fx0 == 0.5 and plan.fx1 == 0.5
        and plan.fy0 == 0.5 and plan.fy1 == 0.5
    )


def build_cover_static_chain(out_w: int, out_h: int) -> str:
    """Plain cover crop with NO animation. Deliberately separate from
    build_cover_motion_chain: static motion was previously routed through
    the full zoompan pipeline with z pinned at 1.0, which still paid the
    full per-frame swscale cost of an upscaled intermediate frame for a
    result that never moves. A straight scale+crop is dramatically
    cheaper and produces an identical (motionless) result."""
    return (
        f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
        f"crop={out_w}:{out_h}"
    )


def build_shot_video_chain(
    fit: str,
    motion_json: dict,
    out_w: int,
    out_h: int,
    fps: int,
    total_frames: int,
    effect_preset: str,
    effect_intensity: int,
    in_label: str = "0:v",
    look: dict | None = None,
    grade_lut_path: str | None = None,
) -> tuple[str, str | None]:
    """Returns (filter_complex_str, overscan_warning_or_none).

    The returned string is a *complete*, fully-labelled filter_complex
    graph running from `[in_label]` to a final `[vout]` pad — safe to
    combine splits/blends without the ambiguity of chaining bare -vf
    fragments with commas and semicolons.
    """
    plan = resolve_motion(motion_json)
    warning = overscan_warning(plan)
    look = look or {}
    effect_chain = build_effect_chain(effect_preset, effect_intensity, look.get("glitch"), out_w)
    primary, finishing = build_adjust_chain(look.get("adjust"))
    grade_chain = build_grade_chain(grade_lut_path)

    if fit == FitMode.COVER:
        if is_static_plan(plan):
            fit_chain = build_cover_static_chain(out_w, out_h)
        else:
            fit_chain = build_cover_motion_chain(plan, out_w, out_h, fps, total_frames)
    else:
        if plan.z0 != 1.0 or plan.z1 != 1.0 or plan.fx0 != 0.5 or plan.fy0 != 0.5:
            warning = (warning or "") + (
                " Motion is only applied with cover fit; contain/contain_blur ignore motion in M1."
            )
        fit_chain = build_contain_chain(out_w, out_h, blurred_bg=(fit == FitMode.CONTAIN_BLUR))

    # Grade order: fit/motion -> grade LUT (colour sliders + imported LUT)
    # -> sharpen -> look preset -> vignette/grain. Each stage may be a plain comma chain or a labelled
    # split/blend sub-graph; stages are joined through [st*] pads.
    # setsar=1 normalizes sample-aspect-ratio drift introduced by
    # scale/crop rounding — without it, concat/xfade between two shots
    # with slightly different computed SAR (e.g. 3952:3951 vs 1126:1125,
    # both ~1.0 but not bit-identical) fails with "Input link parameters
    # do not match" and silently produces a zero-byte output.
    stages = [c for c in (grade_chain, primary, effect_chain, finishing) if c]
    if not stages:
        return f"[{in_label}]{fit_chain},setsar=1[vout]", warning
    graph = f"[{in_label}]{fit_chain}[st0]"
    for i, stage in enumerate(stages):
        end = ",setsar=1[vout]" if i == len(stages) - 1 else f"[st{i + 1}]"
        graph += f";[st{i}]{stage}{end}"
    return graph, warning
