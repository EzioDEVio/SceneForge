"""Independent project image, video and text clips. Preview uses the export text raster."""
from __future__ import annotations
from app.render.font_runtime import load_font
import hashlib
import json
import math
import re
import uuid
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from app.config import MEDIA_DIR, PROXIES_DIR
from app.render.ffmpeg_utils import probe, run_ffmpeg
from app.render.textured_text import FONTS, _font_path, _shape

DEFAULTS = dict(track=0, start_ms=0, duration_ms=3000, x=50, y=50, width=40,
                rotation=0, opacity=100, size=72, color='#ffffff', family='Noto Sans', align='center')
CACHE = Path(PROXIES_DIR) / 'layer-clips'


def clean_layer_clips(raw, project_id, db):
    from app.db.models import Asset
    from app.render.finishing import FinishingError
    if not isinstance(raw, list) or len(raw) > 64:
        raise FinishingError('Use up to 64 image, video and text clips in a project.')
    result, ids = [], set()
    for c in raw:
        if not isinstance(c, dict) or set(c) - (set(DEFAULTS) | {'id', 'kind', 'name', 'asset_id', 'text', 'source_in_ms', 'mute', 'volume'}):
            raise FinishingError('This image, video or text clip has unsupported settings.')
        out = {**DEFAULTS, **c}
        ident = out.get('id')
        if not isinstance(ident, str) or not 1 <= len(ident) <= 80 or ident in ids:
            raise FinishingError('Each image, video or text clip needs a unique short id.')
        ids.add(ident)
        if out.get('kind') not in ('image', 'video', 'text', 'text_box', 'text_plus'):
            raise FinishingError('Choose an image, video, Text, Text box or Text+ clip.')
        for key, lo, hi in [('track', 0, 5), ('start_ms', 0, 86400000), ('duration_ms', 100, 86400000),
                            ('x', -100, 200), ('y', -100, 200), ('width', 1, 100), ('rotation', -180, 180),
                            ('opacity', 0, 100), ('size', 8, 240)]:
            v = out[key]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
                raise FinishingError(f'Clip {key} must be between {lo} and {hi}.')
            out[key] = int(v) if key in ('track', 'start_ms', 'duration_ms') else round(v, 3)
        if c.get('track', 0) != out['track']:
            raise FinishingError('Choose a whole overlay track number.')
        if not isinstance(out['color'], str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', out['color']):
            raise FinishingError('Choose a valid text colour.')
        if out['family'] not in FONTS or out['align'] not in ('left', 'center', 'right'):
            raise FinishingError('Choose a listed font and text alignment.')
        if out['kind'] in ('image', 'video'):
            asset = db.get(Asset, c.get('asset_id')) if c.get('asset_id') else None
            if not asset or asset.project_id != project_id or asset.type != out['kind']:
                raise FinishingError('Use matching image or video media from this project’s Media Pool.')
            out['asset_id'] = asset.id
            out.pop('text', None)
            if out['kind'] == 'video':
                source_in = out.get('source_in_ms', 0)
                volume = out.get('volume', 100)
                if isinstance(source_in, bool) or not isinstance(source_in, (int, float)) or not math.isfinite(source_in) or source_in < 0:
                    raise FinishingError('Video source start must be a non-negative number.')
                if not asset.duration_ms or source_in + out['duration_ms'] > asset.duration_ms + 50:
                    raise FinishingError('The video layer extends beyond its source. Shorten it or move the source start earlier.')
                if isinstance(volume, bool) or not isinstance(volume, (int, float)) or not math.isfinite(volume) or not 0 <= volume <= 200:
                    raise FinishingError('Video layer volume must be between 0 and 200%.')
                if not isinstance(out.get('mute', True), bool):
                    raise FinishingError('Video layer mute must be on or off.')
                out.update(source_in_ms=int(source_in), mute=out.get('mute', True), volume=round(volume, 3))
        else:
            text = out.get('text', '')
            if not isinstance(text, str) or len(text) > 500:
                raise FinishingError('Text clips support up to 500 characters.')
            out['text'] = text
            out.pop('asset_id', None)
        if out['kind'] != 'video' and any(k in c for k in ('source_in_ms', 'mute', 'volume')):
            raise FinishingError('Source start, mute and volume are only for video layers.')
        name = out.get('name', '')
        if not isinstance(name, str):
            raise FinishingError('Clip name must be text.')
        out['name'] = name[:200]
        result.append(out)
    return result


def text_raster(clip, frame_w, frame_h):
    """Wrap into the chosen width; preserve alpha. Same PNG in editor and export."""
    style = {k: clip.get(k, DEFAULTS.get(k)) for k in ('kind', 'text', 'width', 'size', 'color', 'family', 'align')}
    key = hashlib.sha256(json.dumps([style, frame_w, frame_h, 1], sort_keys=True).encode()).hexdigest()
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f'{key}.png'
    if path.exists():
        return path
    width = max(8, round(frame_w * clip['width'] / 100))
    size = max(8, round(clip['size'] * frame_h / 1080))
    font = load_font(str(_font_path(clip['family'], bool(re.search(r'[\u0600-\u06ff]', clip['text'])))), size, layout_engine=ImageFont.Layout.BASIC)
    stroke = max(1, round(size / 22)) if clip['kind'] == 'text_plus' else 0
    pad = max(4, stroke * 3)
    # Character wrapping also handles a long single word or Arabic text without spaces.
    lines = []
    for paragraph in clip['text'].split('\n'):
        line = ''
        for char in paragraph:
            if line and font.getlength(_shape(line + char)) > max(1, width - pad * 2):
                lines.append(line); line = ''
            line += char
        lines.append(line)
    line_h = max(size + 2 * stroke, round(size * 1.3))
    height = min(frame_h * 4, max(line_h + pad * 2, line_h * len(lines) + pad * 2))
    im = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    if clip['kind'] == 'text_box':
        draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=pad * 2, fill=(30, 34, 42, 220))
    for i, line in enumerate(lines):
        shaped = _shape(line)
        tw = font.getlength(shaped)
        x = pad if clip['align'] == 'left' else width - pad - tw if clip['align'] == 'right' else (width - tw) / 2
        draw.text((x, pad + i * line_h), shaped, font=font, fill=clip['color'], stroke_width=stroke, stroke_fill='#111111', anchor='lt')
    temp = path.with_name(f'{key}.{uuid.uuid4().hex}.png')
    im.save(temp); temp.replace(path)
    return path


def export_layer_times(clips, project, scenes, scene_paths):
    """Empty starter scenes are skipped on export. Keep layers over their intended footage."""
    from app.render.audio_edit import effective_ms
    from app.render.media import media_duration_ms
    authored, cursor, previous = {}, 0, None
    for scene in sorted(project.scenes, key=lambda s: s.order_index):
        take = next((t for t in scene.voice_takes if t.accepted), None)
        audio = effective_ms(take.measured_duration_ms, take.edit_json) if take and take.measured_duration_ms else None
        if scene.timing_mode == 'fixed' and scene.requested_duration_ms:
            duration = scene.requested_duration_ms
        elif audio:
            duration = audio + (250 if scene.lead_ms is None else scene.lead_ms) + (400 if scene.trail_ms is None else scene.trail_ms)
        else:
            duration = media_duration_ms(scene) or scene.measured_duration_ms or scene.requested_duration_ms or 4000
        duration += int(((scene.look_json or {}).get('countdown') or {}).get('seconds', 0) * 1000)
        tr = scene.transition_in_json or {}
        overlap = min(tr.get('duration_ms', 0), authored[previous.id][1] / 2, duration / 2) if previous and previous.shots and scene.shots and tr.get('type', 'cut') != 'cut' else 0
        start = cursor - overlap
        authored[scene.id] = (start, duration)
        cursor = start + duration
        previous = scene
    exported, cursor, previous_ms = {}, 0, 0
    for scene in scenes:
        duration = probe(scene_paths[scene.id]).duration_ms or 0
        tr = scene.transition_in_json or {}
        overlap = min(tr.get('duration_ms', 0), previous_ms // 2, duration // 2) if exported and tr.get('type', 'cut') != 'cut' else 0
        start = cursor - overlap
        exported[scene.id] = (start, duration)
        cursor, previous_ms = start + duration, duration
    result = []
    for clip in clips:
        ranges = []
        for i, scene in enumerate(scenes):
            start, duration = authored[scene.id]
            # Incoming footage owns an overlap, as in the live sequence player.
            until = min(start + duration, authored[scenes[i+1].id][0]) if i+1 < len(scenes) else start + duration
            begin, end = max(clip['start_ms'], start), min(clip['start_ms'] + clip['duration_ms'], until)
            if end <= begin:
                continue
            target, target_ms = exported[scene.id]
            out_from, out_to = target + begin - start, min(target + target_ms, target + end - start)
            if out_to > out_from:
                if ranges and clip['kind'] != 'video' and out_from <= ranges[-1][1] + 1:
                    ranges[-1][1] = max(ranges[-1][1], out_to)
                else:
                    ranges.append([out_from, out_to, clip.get('source_in_ms', 0) + begin - clip['start_ms']])
        result.extend({**clip, 'start_ms': int(start), 'duration_ms': int(end-start), **({'source_in_ms': int(source)} if clip['kind'] == 'video' else {})} for start, end, source in ranges)
    return result


def render_layer_clips(movie, project, cancel_check=None, scenes=None, scene_paths=None):
    clips = (project.finishing_json or {}).get('layer_clips', [])
    if not clips:
        return movie
    from app.db.database import SessionLocal
    from app.db.models import Asset, Project, Scene
    if scenes is not None and scene_paths is not None and not ((project.finishing_json or {}).get("free_timeline") or {}).get("enabled"):
        with SessionLocal() as db:
            live_project = db.get(Project, project.id)
            if not live_project:
                raise ValueError('This project no longer exists.')
            clips = export_layer_times(clips, live_project, [db.get(Scene, s.id) for s in scenes], scene_paths)
    info = probe(movie)
    duration = (info.duration_ms or 0) / 1000
    args = ['-y', '-i', movie]
    graphs, audio_graphs, audio_labels, prev = [], [], [], '0:v'
    # Track 1 is above track 2. On a shared track later clips are on top.
    with SessionLocal() as db:
        for c in sorted(clips, key=lambda c: -c['track']):
            if c['start_ms'] / 1000 >= duration:
                continue
            if c['kind'] in ('image', 'video'):
                asset = db.get(Asset, c['asset_id'])
                if not asset or asset.project_id != project.id:
                    raise ValueError('Overlay media is missing. Restore it or remove its clip.')
                src = Path(MEDIA_DIR) / asset.storage_key
            else:
                src = text_raster(c, info.width, info.height)
            n = len(graphs) + 1
            if c['kind'] == 'video':
                args += ['-i', str(src)]
            else:
                args += ['-loop', '1', '-framerate', str(project.fps), '-t', str(duration), '-i', str(src)]
            width = max(2, round(info.width * c['width'] / 100))
            start, length = c['start_ms'] / 1000, c['duration_ms'] / 1000
            source_start = c.get('source_in_ms', 0) / 1000
            timing = f'trim=start={source_start}:duration={length},setpts=PTS-STARTPTS+{start}/TB,fps={project.fps},' if c['kind'] == 'video' else ''
            fx = f'[{n}:v]{timing}scale={width}:-1,format=rgba,setsar=1'
            if c['kind'] == 'video' and not c.get('mute', True) and probe(str(src)).has_audio:
                audio_graphs.append(f'[{n}:a]atrim=start={source_start}:duration={length},asetpts=PTS-STARTPTS,volume={c.get("volume",100)/100},aresample=48000,aformat=channel_layouts=stereo,adelay={c["start_ms"]}:all=1[layeraudio{n}]')
                audio_labels.append(f'[layeraudio{n}]')
            if c['rotation']:
                angle = c['rotation'] * math.pi / 180
                fx += f",rotate={angle}:c=none:ow=rotw({angle}):oh=roth({angle})"
            fx += f",colorchannelmixer=aa={c['opacity']/100}[layer{n}];[{prev}][layer{n}]overlay=x=W*{c['x']/100}-w/2:y=H*{c['y']/100}-h/2:enable='gte(t,{c['start_ms']/1000})*lt(t,{(c['start_ms']+c['duration_ms'])/1000})':eof_action=pass:repeatlast=0[v{n}]"
            graphs.append(fx); prev = f'v{n}'
    if not graphs:
        return movie
    out = Path(movie).with_name(Path(movie).stem + '.layers.' + uuid.uuid4().hex[:8] + '.mp4')
    try:
        audio_map = ['-map', '0:a?', '-c:a', 'copy']
        if audio_labels:
            if info.has_audio:
                audio_graphs.insert(0, '[0:a]aresample=48000,aformat=channel_layouts=stereo[baseaudio]')
            else:
                audio_graphs.insert(0, f'anullsrc=r=48000:cl=stereo,atrim=duration={duration}[baseaudio]')
            audio_graphs.append('[baseaudio]' + ''.join(audio_labels) + f'amix=inputs={len(audio_labels)+1}:duration=first:normalize=0,alimiter=limit=0.95:level=false:latency=true[mixedaudio]')
            audio_map = ['-map', '[mixedaudio]', '-c:a', 'aac', '-b:a', '192k']
        run_ffmpeg([*args, '-filter_complex_threads', '1', '-filter_complex', ';'.join(graphs+audio_graphs), '-map', f'[{prev}]', *audio_map, '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p', '-t', str(duration), '-movflags', '+faststart', str(out)], cancel_check=cancel_check)
    except BaseException:
        out.unlink(missing_ok=True)
        raise
    return str(out)
