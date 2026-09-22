"""Plan-hash / cache-key computation for dependency-aware invalidation.

Spec section 11: "Cache keys include content hash, project/scene revision,
crop/motion, timings, voice settings, renderer version and relevant font
settings." "Changing a transition must not regenerate speech or images."
"Changing spoken text invalidates its audio, captions, and affected
renders." "Changing a selected image invalidates the visual render only."

We implement this with three independent hashes per scene:
  - visual_hash:  shots (asset ids/content hashes, crop, motion, fit, effect)
  - audio_hash:   accepted voice take's audio asset content hash
  - caption_hash: subtitle_text + font_json
and a combined `part_plan_hash` = hash(visual_hash, audio_hash, caption_hash,
lead/trail, canvas, fps, RENDERER_VERSION). A part is "stale" whenever
`scene.rendered_plan_hash != part_plan_hash`. Because the three sub-hashes
are independent, callers (the renderer) can also tell *which* artifact
changed and, in later milestones, reuse an unaffected intermediate — for
M1 we always re-render the part's video when *any* sub-hash changes, but
we surface which sub-hash changed in job metadata so operators/tests can
verify e.g. that a crop change did not touch the audio hash.
"""
from __future__ import annotations

import hashlib
import json

from app.db.models import Scene

RENDERER_VERSION = "sceneforge-render-2.3-crop"


def _hash_obj(obj) -> str:
    blob = json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def visual_hash_of(scene: Scene) -> str:
    shots_repr = [
        {
            "asset_id": s.asset_id,
            "asset_hash": s.asset.content_hash if s.asset else None,
            "order": s.order_index,
            "in": s.source_in_ms,
            "out": s.source_out_ms,
            "duration": s.duration_ms,
            "fit": s.fit,
            "crop": s.crop_json,
            "motion": s.motion_json,
        }
        for s in scene.shots
    ]
    return _hash_obj({
        "shots": shots_repr,
        "effect_preset": scene.effect_preset,
        "effect_intensity": scene.effect_intensity,
    })


def audio_hash_of(scene: Scene) -> str:
    accepted = next((t for t in scene.voice_takes if t.accepted), None)
    if not accepted:
        return "no-audio"
    return _hash_obj({
        "take_id": accepted.id,
        "audio_asset_hash": accepted.audio_asset.content_hash if accepted.audio_asset else None,
        "measured_duration_ms": accepted.measured_duration_ms,
    })


def caption_hash_of(scene: Scene) -> str:
    return _hash_obj({
        "subtitle_text": scene.subtitle_text,
        "font": scene.font_json,
    })


def part_plan_hash(scene: Scene, canvas: tuple[int, int], fps: int) -> dict:
    v = visual_hash_of(scene)
    a = audio_hash_of(scene)
    c = caption_hash_of(scene)
    combined = _hash_obj({
        "visual": v,
        "audio": a,
        "caption": c,
        "lead_ms": scene.lead_ms,
        "trail_ms": scene.trail_ms,
        "timing_mode": scene.timing_mode,
        "requested_duration_ms": scene.requested_duration_ms,
        "canvas": canvas,
        "fps": fps,
        "renderer_version": RENDERER_VERSION,
    })
    return {"visual": v, "audio": a, "caption": c, "combined": combined}


def is_stale(scene: Scene, canvas: tuple[int, int], fps: int) -> bool:
    return scene.rendered_plan_hash != part_plan_hash(scene, canvas, fps)["combined"]


def export_plan_hash(scene_hashes: list[str], transitions: list[dict]) -> str:
    return _hash_obj({"scenes": scene_hashes, "transitions": transitions, "renderer_version": RENDERER_VERSION})
