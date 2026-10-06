"""Timed bundled colour artwork beside caption safe-width; independent of fonts."""
from app.render.font_runtime import load_font
from app.api.stickers import library

# Match the full bundled colour emoji catalogue; no platform font dependence.
EMOJI_IDS = tuple(item['id'] for item in library().get('items', []) if item.get('source') == 'twemoji')


def emoji_overlays(font, w, h, total_ms):
    from types import SimpleNamespace
    from app.api.stickers import sticker, sticker_file
    from app.render.overlays import DEFAULT_OVERLAY
    if not font.get('captions_enabled') or font.get('typewriter'):
        return [], {}
    rows, assets = [], {}
    for s in font.get('caption_segments') or []:
        key = s.get('emoji')
        start, end = max(0, s['start_ms']), min(total_ms, s['end_ms'])
        if key not in EMOJI_IDS or not s.get('text', '').strip() or end <= start:
            continue
        size = max(3, min(8, float(font.get('size', 44))/w*120))
        margin = 20 if h > w*1.2 else 5.5
        pos, offset = font.get('position', 'bottom'), float(font.get('offset_y', 0))
        y = (margin+offset+size*w/h/2 if pos == 'top' else 50 if pos == 'middle' else 100-margin-offset-size*w/h/2)
        from PIL import ImageFont
        from app.render.textured_text import _font_path
        import re
        try:
            face = load_font(str(_font_path(font.get('family', 'Noto Sans'), bool(re.search(r'[\u0600-\u06ff]', s['text'])))), max(8, int(font.get('size', 44))))
            text_width = max(face.getlength(line) for line in s['text'].splitlines())
        except (OSError, ValueError):
            text_width = len(s['text']) * float(font.get('size', 44)) * .55
        safe_width = w * float(font.get('max_width', 90)) / 100
        text_width = min(safe_width, text_width + (float(font.get('box_padding', 10))*2 if font.get('background') == 'box' else 0))
        align = font.get('halign', 'center')
        left = (w-safe_width)/2 if align == 'left' else (w+safe_width)/2-text_width if align == 'right' else (w-text_width)/2
        icon_width = w*size/100
        centre = left-icon_width/2-4 if s.get('emoji_side', 'right') == 'left' else left+text_width+icon_width/2+4
        x = max(size/2, min(100-size/2, centre/w*100))
        path = sticker_file(sticker(key))
        assets[key] = SimpleNamespace(type='image', width=512, height=512, path=str(path))
        rows.append({**DEFAULT_OVERLAY, 'asset_id': key, 'x': x, 'y': y, 'width': size, 'radius': 0, 'border': 0, 'shadow': 0,
                     'start_ms': start, 'end_ms': end, 'anim_in': 'none', 'anim_out': 'none', 'anim_ms': 0})
    return rows, assets
