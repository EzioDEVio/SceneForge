"""Clean up: silence detection, filler-word detection and scene jump cuts.

  POST /api/silence/detect      {asset_id} or {scene_id, source: narration|clips}
                                + threshold_db (-60..-20), min_silence_ms (200..3000), padding_ms (0..500)
  POST /api/fillers/detect      {scene_id, source, words?: [..], padding_ms?: 0..200}
  POST /api/cleanup/scenes/{id}/jump-cut   {cuts: [[start_ms, end_ms], ...]} in scene time

"Source time" in the responses is time inside the audio a timeline clip would play:
the asset itself for asset_id, the detached narration (trim applied, 0 = first kept
sample) for narration, and the clip sound from the shot's in-point for clips. Scene
requests also return `scene_ranges` / per-match `start_ms` in scene time.

The jump cut divides a single static, normal-speed source video scene into consecutive
scenes that keep only the non-silent source ranges, in one request. Captions, transcript
words, timed titles and overlays are rebased like the two-way source split. The clip's
own sound stays linked to the picture.
"""
from __future__ import annotations

from copy import deepcopy

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Asset, Scene
from app.render import silence as sil

router = APIRouter(tags=["cleanup"])
MAX_SEGMENTS = 200
SOURCES = ("narration", "clips")


def _bad(message: str, code: int = 400):
    raise HTTPException(code, message)


def _scene(db, scene_id) -> Scene:
    scene = db.get(Scene, scene_id) if isinstance(scene_id, str) else None
    if not scene:
        _bad("Scene not found", 404)
    return scene


def _source(body: dict) -> str:
    source = body.get("source", "narration")
    if source not in SOURCES:
        _bad("source must be 'narration' or 'clips'.")
    return source


def _lead(scene) -> int:
    return 250 if scene.lead_ms is None else int(scene.lead_ms)


def _scene_total(scene) -> int:
    from app.render.media import media_duration_ms
    if scene.timing_mode == "fixed" and scene.requested_duration_ms:
        return int(scene.requested_duration_ms)
    return int(media_duration_ms(scene) or scene.measured_duration_ms or scene.requested_duration_ms or 4000)


def _single_video_shot(scene):
    shots = list(scene.shots)
    if len(shots) != 1:
        _bad(f"Silence removal on a scene needs exactly one video clip; this scene has {len(shots)}. "
             "Detach the clip sound to a timeline track, or render the scene and split it instead.")
    shot = shots[0]
    if not shot.asset or shot.asset.type != "video":
        _bad("Silence removal on a scene needs a video clip with sound.")
    return shot


@router.post("/api/silence/detect")
def detect_silence(body: dict, db: Session = Depends(get_db)):
    from app.render.renderer import _resolve_asset_path
    body = body or {}
    try:
        params = sil.clean_params(body)
    except sil.CleanupError as e:
        _bad(str(e))
    asset_id, scene_id = body.get("asset_id"), body.get("scene_id")
    if bool(asset_id) == bool(scene_id):
        _bad("Send either asset_id or scene_id with source.")
    scene_offset = None   # scene time = source time + scene_offset
    if asset_id:
        asset = db.get(Asset, asset_id) if isinstance(asset_id, str) else None
        if not asset:
            _bad("Asset not found", 404)
        if asset.type not in ("audio", "video"):
            _bad("Silence detection needs an audio or video file.")
        start, length = 0, None
    else:
        scene = _scene(db, scene_id)
        source = _source(body)
        if source == "narration":
            take = next((t for t in scene.voice_takes if t.accepted), None)
            if not take or not take.audio_asset_id:
                _bad("This scene has no narration. Choose the clip sound instead.")
            asset = db.get(Asset, take.audio_asset_id)
            edit = take.edit_json or {}
            start = int(edit.get("in_ms") or 0)
            length = int(edit["out_ms"]) - start if edit.get("out_ms") else None
            scene_offset = _lead(scene)
        else:
            shot = _single_video_shot(scene)
            asset = shot.asset
            start = int(shot.source_in_ms or 0)
            length = _scene_total(scene)
            if shot.source_out_ms:
                length = min(length, int(shot.source_out_ms) - start)
            scene_offset = 0
    try:
        samples = sil.decode_mono(_resolve_asset_path(asset), start, length)
    except sil.CleanupError as e:
        _bad(str(e))
    ranges = sil.find_silences(samples, params["threshold_db"], params["min_silence_ms"], params["padding_ms"])
    out = {"asset_id": asset.id, "duration_ms": int(round(len(samples) * 1000 / sil.RATE)), **params,
           "ranges": ranges, "total_removable_ms": sil.total_ms(ranges), "cuts": len(ranges)}
    if scene_offset is not None:
        out["scene_ranges"] = [[s + scene_offset, e + scene_offset] for s, e in ranges]
        out["scene_offset_ms"] = scene_offset
    return out


@router.post("/api/fillers/detect")
def detect_fillers(body: dict, db: Session = Depends(get_db)):
    body = body or {}
    scene = _scene(db, body.get("scene_id"))
    source = _source(body)
    padding = body.get("padding_ms", sil.FILLER_PADDING_MS)
    if isinstance(padding, bool) or not isinstance(padding, (int, float)) or not 0 <= padding <= 200:
        _bad("padding_ms must be between 0 and 200.")
    try:
        terms = sil.clean_terms(body.get("words"))
    except sil.CleanupError as e:
        _bad(str(e))
    transcript = (scene.font_json or {}).get("transcript") or {}
    words = transcript.get("words")
    if not isinstance(words, list) or not words:
        _bad("This scene has no transcript yet. Run Auto captions (Text tab) first, then look for filler words.")
    made_from = transcript.get("source")
    if made_from in SOURCES and made_from != source:
        label = {"narration": "the narration", "clips": "the video clip sound"}
        _bad(f"The captions of this scene were made from {label[made_from]}. "
             f"Run Auto captions on {label[source]} first, or choose {label[made_from]}.")
    offset = _lead(scene) if source == "narration" else 0
    matches = sil.find_fillers(words, terms, int(padding))
    for m in matches:
        m["source_start_ms"], m["source_end_ms"] = max(0, m["start_ms"] - offset), max(0, m["end_ms"] - offset)
    return {"scene_id": scene.id, "source": source, "terms": [" ".join(t) for t in terms], "scene_offset_ms": offset,
            "matches": matches, "total_removable_ms": sil.total_ms(sil.merge_ranges([[m["start_ms"], m["end_ms"]] for m in matches])),
            "language": transcript.get("language")}


def _slice_words(words, start: int, end: int):
    out = []
    for w in words:
        if not isinstance(w, (list, tuple)) or len(w) < 3:
            continue
        try:
            ws, we = int(w[1]), int(w[2])
        except (TypeError, ValueError):
            continue
        if we > start and ws < end:
            out.append([w[0], max(ws, start) - start, min(we, end) - start])
    return out


def _segment_font(raw: dict, start: int, end: int, total: int) -> dict:
    """Timed text of the scene restricted to [start, end] and rebased to 0 (like the source split)."""
    from app.api.scenes import _split_scene_font
    font = deepcopy(raw or {})
    if start > 0:
        font = _split_scene_font(font, start, total)[1]
    if end < total:
        font = _split_scene_font(font, end - start, total - start)[0]
    words = ((raw or {}).get("transcript") or {}).get("words")
    if isinstance(words, list):
        font["transcript"] = {**deepcopy((raw or {}).get("transcript") or {}), "words": _slice_words(words, start, end)}
    return font


def _segment_overlays(raw: list, start: int, end: int, total: int) -> list:
    from app.api.scenes import _split_scene_overlays
    rows = raw if isinstance(raw, list) else []
    if start > 0:
        rows = _split_scene_overlays(rows, start, total)[1]
    if end < total:
        rows = _split_scene_overlays(rows, end - start, total - start)[0]
    return rows


@router.post("/api/cleanup/scenes/{scene_id}/jump-cut")
def jump_cut_scene(scene_id: str, body: dict, db: Session = Depends(get_db)):
    from app.api.scenes import _caption_text, _out
    from app.db.models import Shot
    scene = _scene(db, scene_id)
    cuts = (body or {}).get("cuts")
    if not isinstance(cuts, list) or not cuts:
        _bad("cuts must be a non-empty list of [start_ms, end_ms] ranges in scene time.")
    if len(cuts) > 2000:
        _bad("Too many ranges.")
    if any(t.accepted for t in scene.voice_takes):
        _bad("This scene has a separate narration track, so cutting the picture would change the narration timing. "
             "Use “Remove silences” on the narration (A1) to move it to the timeline and cut it there, or remove the narration first.")
    shot = _single_video_shot(scene)
    speed = (shot.speed_json or {})
    if (shot.motion_json or {}).get("type", "static") != "static" or abs(float(speed.get("speed", 1) or 1) - 1) > 0.001 \
            or speed.get("freeze_at_ms") is not None or speed.get("ramp", "none") not in (None, "none"):
        _bad("Set the clip's motion to Static and its speed to 1× before removing silences from this scene.")
    total = _scene_total(scene)
    source_in = int(shot.source_in_ms or 0)
    if (shot.asset.duration_ms or 0) < source_in + total:
        _bad("The scene is longer than its video (a looped clip). Trim the scene to the video length first.")
    frame = max(1, round(1000 / scene.project.fps))
    try:
        merged = sil.merge_ranges(cuts, 0, total)
    except sil.CleanupError as e:
        _bad(str(e))
    keeps = sil.keep_ranges(merged, total, frame)
    if not keeps:
        _bad("Those ranges cover the whole scene. Nothing would be left.")
    if keeps == [[0, total]]:
        _bad("Nothing to remove: every range is shorter than one frame or outside the scene.")
    if len(keeps) > MAX_SEGMENTS:
        _bad(f"That would make {len(keeps)} scenes (limit {MAX_SEGMENTS}). Raise the minimum silence length.")
    original_font, original_overlays = deepcopy(scene.font_json or {}), deepcopy(scene.overlays_json or [])
    has_timed = bool(original_font.get("caption_segments"))
    original_subtitle = scene.subtitle_text
    extra = len(keeps) - 1
    for sibling in scene.project.scenes:
        if sibling.order_index > scene.order_index:
            sibling.order_index += extra
    segments = [scene]
    for i, (start, end) in enumerate(keeps):
        font = _segment_font(original_font, start, end, total)
        overlays = _segment_overlays(original_overlays, start, end, total)
        subtitle = _caption_text(font, original_subtitle, has_timed)
        if i == 0:
            target = scene
            target.font_json, target.overlays_json, target.subtitle_text = font, overlays, subtitle
            shot.source_in_ms, shot.source_out_ms, shot.duration_ms = source_in + start, source_in + end, end - start
        else:
            target = Scene(project_id=scene.project_id, order_index=scene.order_index + i, title=f"{scene.title} · {i + 1}",
                           original_text=scene.original_text, spoken_text=scene.spoken_text, subtitle_text=subtitle,
                           timing_mode="fixed", requested_duration_ms=end - start, lead_ms=0, trail_ms=0,
                           effect_preset=scene.effect_preset, effect_intensity=scene.effect_intensity, font_json=font,
                           look_json=deepcopy(scene.look_json or {}), overlays_json=overlays,
                           transition_in_json={"type": "cut", "duration_ms": 0})
            db.add(target)
            db.flush()
            db.add(Shot(scene_id=target.id, asset_id=shot.asset_id, order_index=0, fit=shot.fit, motion_json=deepcopy(shot.motion_json),
                        crop_json=deepcopy(shot.crop_json), audio_json=deepcopy(shot.audio_json or {}), speed_json=deepcopy(shot.speed_json or {}),
                        source_in_ms=source_in + start, source_out_ms=source_in + end, duration_ms=end - start))
            segments.append(target)
    scene.timing_mode, scene.requested_duration_ms = "fixed", keeps[0][1] - keeps[0][0]
    scene.rendered_asset_id = scene.rendered_plan_hash = scene.measured_duration_ms = None
    scene.revision += 1
    db.commit()
    for s in segments:
        db.refresh(s)
    kept = sum(e - s for s, e in keeps)
    return {"scenes": [_out(s).model_dump(mode="json") for s in segments], "kept_ms": kept, "removed_ms": total - kept,
            "segments": len(keeps)}
