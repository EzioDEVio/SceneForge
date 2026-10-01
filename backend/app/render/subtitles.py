"""Generate .ass subtitle files for caption burn-in.

Style Encoding is -1: libass then detects the paragraph base direction
(Arabic-first lines lay out right-to-left) and runs the bidi algorithm across
the whole event instead of splitting it at every override tag. That matters
because each script run carries its own \\fn switch (see fontruns.py).

RTL/Arabic shaping is handled by libass (HarfBuzz + FriBidi), which this
project's target FFmpeg build has compiled in (`--enable-libass
--enable-libfribidi --enable-libharfbuzz`). We simply write correctly
ordered *logical* UTF-8 text — libass performs bidi reordering and Arabic
glyph joining at render time. We do NOT reverse characters ourselves,
which is the classic mistake that breaks shaping.
"""
from __future__ import annotations

import re

from app.config import TMP_DIR
from app.render.fontruns import tag_runs, text_scale
from app.render.typewriter import reveal_schedule


def _hex_to_ass_color(hex_color: str, alpha: int = 0) -> str:
    """ASS colors are &HAABBGGRR. hex_color is '#RRGGBB'. alpha 0=opaque."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        hex_color = "FFFFFF"
    r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
    return f"&H{alpha:02X}{b}{g}{r}"


_ALIGNMENT = {"bottom": 2, "top": 8, "middle": 5}
from app.render.fontruns import ALL_FAMILIES as LAYER_FAMILIES  # every bundled family


_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")


def _exit_loop_tags(font_json: dict, span_ms: int) -> str:
    """Exit animation (fade / pop out) and a looping pulse for one caption event."""
    tags = ""
    exit_ms = int(font_json.get("exit_ms", 400))
    exit_ms = max(50, min(exit_ms, span_ms // 3 or 50))
    ex = font_json.get("exit_animation", "none")
    if ex == "fade":
        tags += r"\fad(0,%d)" % exit_ms
    elif ex == "pop":
        tags += r"\t(%d,%d,\fscx0\fscy0\alpha&HFF&)" % (max(0, span_ms - exit_ms), span_ms)
    if font_json.get("loop") == "pulse":
        period, t, grow = 700, 0, True
        while t + period <= max(0, span_ms - (exit_ms if ex != "none" else 0)) and t < 60000:
            tags += r"\t(%d,%d,\fscx%d\fscy%d)" % (t, t + period, 106 if grow else 100, 106 if grow else 100)
            t += period; grow = not grow
    return tags


def _phrase_events(text, font_json, duration_ms, family, primary, outline, outline_w, size,
                   speech_start_ms, speech_ms, speech_segments, word_times, ts, runs, tag_runs, escape_text,
                   forced_end_ms=None):
    """CapCut-style phrase captions: a few words at a time, each phrase shown while its words
    are spoken (exact voice timing, measured speech, or an even spread), with the phrase's
    entrance, word highlight, exit and loop applied per phrase."""
    from app.render.word_timing import word_starts
    words = text.split()
    n = max(1, min(8, int(font_json.get("phrase_words", 3) or 3)))
    direction_mark = {"rtl": "\u200f", "ltr": "\u200e"}.get(font_json.get("caption_direction"), "")
    weights = [len(w) + 2 for w in words]
    if word_times and len(word_times) == len(words):
        starts = [s for s, _ in word_times]
        last_end = word_times[-1][1]
    elif speech_segments:
        starts = word_starts(weights, speech_segments)
        last_end = speech_segments[-1][1]
    else:
        start = max(0, int(speech_start_ms))
        span = max(500, int(speech_ms if speech_ms else duration_ms - start))
        starts, acc, total = [], 0.0, sum(weights)
        for w in weights:
            starts.append(int(start + span * acc / total)); acc += w
        last_end = start + span
    hi = _hex_to_ass_color(font_json.get("highlight_color", "#FFD84D"), alpha=0)
    style = font_json.get("karaoke_style", "fill") if font_json.get("karaoke") else None
    anim = font_json.get("caption_animation", "none")
    a = int(font_json.get("caption_animation_ms", 400))
    events = []
    for c in range(0, len(words), n):
        chunk = words[c:c + n]
        # Keep the phrase's text untouched for word timing, while giving libass
        # an explicit paragraph direction for mixed Arabic/Latin captions.
        if c == 0 and chunk and direction_mark:
            chunk[0] = direction_mark + chunk[0]
        c_start = starts[c]
        c_end = starts[c + n] if c + n < len(words) else min(duration_ms, int(forced_end_ms) if forced_end_ms is not None else last_end + 500)
        c_end = max(c_end, c_start + 200)
        span = c_end - c_start
        enter = _entrance_tags(anim, min(a, max(100, span // 2)))
        tail = _exit_loop_tags(font_json, span)
        head = lambda s0, s1, layer=0: f"Dialogue: {layer},{ts(s0)},{ts(s1)},Default,,0,0,0,,"
        if style in ("pop", "glow", "box", "color", "underline"):
            w_starts = [starts[c + k] for k in range(len(chunk))] + [c_end]
            for k in range(len(chunk)):
                parts = []
                for j, w in enumerate(chunk):
                    first, tagged = tag_runs(w + (" " if j < len(chunk) - 1 else ""), family, escape_text)
                    cur = j == k
                    if cur and style == "pop":
                        parts.append(f"{{\\fn{first}\\1c{hi}\\fscx122\\fscy122}}{tagged}{{\\fscx100\\fscy100}}")
                    elif cur and style == "box":
                        parts.append(f"{{\\fn{first}\\3c{hi}\\bord{max(4, size // 4)}\\blur1}}{tagged}{{\\3c{outline}\\bord{outline_w}\\blur0}}")
                    elif cur and style == "underline":
                        parts.append(f"{{\\fn{first}\\1c{hi}\\u1}}{tagged}{{\\u0}}")
                    elif cur and style == "glow":
                        parts.append(f"{{\\fn{first}\\1c{hi}\\3c{hi}\\bord3\\blur4}}{tagged}{{\\3c{outline}\\bord{outline_w}\\blur0}}")
                    else:
                        color = hi if (style == "fill" and j < k) else primary
                        parts.append(f"{{\\fn{first}\\1c{color}}}{tagged}")
                s0, s1 = w_starts[k], w_starts[k + 1]
                tags = (enter if k == 0 else "") + (_exit_loop_tags(font_json, s1 - s0) if k == len(chunk) - 1 else "")
                events.append(head(s0, s1) + ("{" + tags + "}" if tags else "") + "".join(parts) + "\n")
        elif style == "fill":
            parts = [f"{{\\1c{hi}\\2c{primary}}}"]
            ends = [starts[c + k + 1] if c + k + 1 < len(words) else last_end for k in range(len(chunk))]
            for k, w in enumerate(chunk):
                first, tagged = tag_runs(w + (" " if k < len(chunk) - 1 else ""), family, escape_text)
                parts.append(f"{{\\k{max(1, round((ends[k] - starts[c + k]) / 10))}\\fn{first}}}{tagged}")
            events.append(head(c_start, c_end) + "{" + enter + tail + "}" + "".join(parts) + "\n")
        else:
            events.append(head(c_start, c_end) + ("{" + enter + tail + "}" if enter + tail else "") + runs(" ".join(chunk), family) + "\n")
    return events


def _entrance_tags(anim: str, a: int) -> str:
    """Entrance for one phrase (letter animations become word-level pops per phrase)."""
    return {
        "fade": r"\fad(%d,0)" % a,
        "zoom": r"\fscx30\fscy30\t(0,%d,\fscx100\fscy100)" % a,
        "blur": r"\blur12\t(0,%d,\blur0)" % a,
        "bounce": r"\fscx0\fscy0\t(0,%d,\fscx115\fscy115)\t(%d,%d,\fscx100\fscy100)" % (a * 2 // 3, a * 2 // 3, a),
        "letters-pop": r"\fscx40\fscy40\alpha&HFF&\t(0,%d,\fscx110\fscy110\alpha&H00&)\t(%d,%d,\fscx100\fscy100)" % (a * 2 // 3, a * 2 // 3, a),
        "words-pop": r"\fscx40\fscy40\alpha&HFF&\t(0,%d,\fscx110\fscy110\alpha&H00&)\t(%d,%d,\fscx100\fscy100)" % (a * 2 // 3, a * 2 // 3, a),
        "letters-fade": r"\fad(%d,0)" % a, "words-fade": r"\fad(%d,0)" % a,
        "letters-flip": r"\frx90\t(0,%d,\frx0)" % a, "words-flip": r"\frx90\t(0,%d,\frx0)" % a,
        "letters-blur": r"\blur12\t(0,%d,\blur0)" % a,
        "glitch": r"\fscx130\fax0.2\t(0,%d,\fscx100\fax0)" % a,
        "wobble": r"\frz-6\t(0,%d,\frz4)\t(%d,%d,\frz0)" % (a // 2, a // 2, a),
    }.get(anim, "")


_REVEAL_MASKS = ('reveal-right', 'reveal-up', 'reveal-down', 'reveal-split')


def _reveal_mask(animation: str, layer: dict, x: float, y: float, canvas_w: int, canvas_h: int, anim_ms: int) -> str:
    """Rectangular wipe masks with ASS \\clip: the clip rectangle animates
    across an estimate of the text's box during the entrance, then snaps to
    the whole canvas so text outside the estimate is never cut off.
    reveal-right = wipe from the right edge, reveal-up = from the bottom
    upwards, reveal-down = from the top downwards, reveal-split = opens from
    the centre outwards. Straight wipes only (no rotation)."""
    size = float(layer.get('size', 64))
    lines = str(layer.get('text', '')).split('\n') or ['']
    tw = min(canvas_w, max(len(line) for line in lines) * size * 0.55 + size * 0.5)
    th = min(canvas_h, len(lines) * size * 1.3 + size * 0.4)
    align = layer.get('align', 'center')
    x1 = x if align == 'left' else x - tw if align == 'right' else x - tw / 2
    x1, x2 = max(0, x1), min(canvas_w, x1 + tw)
    y1, y2 = max(0, y - th / 2), min(canvas_h, y + th / 2)
    W, H = canvas_w, canvas_h
    start, end = {
        'reveal-right': ((x2, 0, W, H), (x1, 0, W, H)),
        'reveal-up': ((0, y2, W, H), (0, y1, W, H)),
        'reveal-down': ((0, 0, W, y1), (0, 0, W, y2)),
        'reveal-split': (((x1 + x2) / 2, 0, (x1 + x2) / 2, H), (x1, 0, x2, H)),
    }[animation]
    c = lambda r: r'\clip(%d,%d,%d,%d)' % tuple(int(round(v)) for v in r)
    return c(start) + r'\t(0,%d,%s)\t(%d,%d,%s)' % (anim_ms, c(end), anim_ms, anim_ms + 1, c((0, 0, W, H)))


def write_ass_file(
    scene_id: str,
    text: str,
    duration_ms: int,
    font_json: dict,
    canvas_w: int,
    canvas_h: int,
    out_path: str | None = None,
    typewriter: bool = False,
    speech_start_ms: int = 0,
    speech_ms: int | None = None,
    speech_segments: list[tuple[int, int]] | None = None,
    word_times: list[tuple[int, int]] | None = None,
) -> str:
    family = font_json.get("family", "Noto Naskh Arabic")
    size = int(round(int(font_json.get("size", 44)) * text_scale(family, text)))
    primary = _hex_to_ass_color(font_json.get("color", "#FFFFFF"), alpha=0)
    outline = _hex_to_ass_color(font_json.get("outline_color", "#000000"), alpha=0)
    outline_w = int(font_json.get("outline_width", 2))
    position = font_json.get("position", "bottom")
    halign = font_json.get("halign", "center")
    column = {"left": 0, "center": 1, "right": 2}.get(halign, 1)
    row = {"bottom": 1, "middle": 4, "top": 7}.get(position, 1)
    alignment = row + column
    # Shadow: depth, colour and opacity (BackColour); background box uses OutlineColour + Outline as padding.
    shadow_depth = float(font_json.get("shadow", 0) or 0)
    shadow_alpha = int(round(255 * (1 - float(font_json.get("shadow_opacity", 60)) / 100)))
    back_color = _hex_to_ass_color(font_json.get("shadow_color", "#000000"), alpha=shadow_alpha)
    background = font_json.get("background", "none")
    border_style = 3 if background == "box" else 1
    if background == "box":
        box_alpha = int(round(255 * (1 - float(font_json.get("box_opacity", 60)) / 100)))
        outline = _hex_to_ass_color(font_json.get("box_color", "#000000"), alpha=box_alpha)
        outline_w = int(font_json.get("box_padding", 10))
    bold = -1 if font_json.get("bold") else 0
    italic = -1 if font_json.get("italic") else 0
    underline = -1 if font_json.get("underline") else 0
    spacing = float(font_json.get("spacing", 0) or 0)
    # Vertical video (TikTok, Reels, Shorts): the platform's own buttons and caption cover the
    # bottom ~20 %, so captions sit higher by default; landscape keeps the usual 5.5 %.
    base = 0.2 if canvas_h > canvas_w * 1.2 else 0.055
    margin_v = max(0, int(round(canvas_h * (base + float(font_json.get("offset_y", 0) or 0) / 100))))
    side = int(round(canvas_w * (100 - float(font_json.get("max_width", 90) or 90)) / 200))
    case = font_json.get("case", "none")
    if case == "upper":
        text = text.upper()
    elif case == "lower":
        text = text.lower()
    elif case == "title":
        text = " ".join(w[:1].upper() + w[1:] for w in text.split(" "))

    def ts(ms: int) -> str:
        cs = int(round(ms)) // 10
        h = cs // 360000
        m = (cs % 360000) // 6000
        s = (cs % 6000) // 100
        c = cs % 100
        return f"{h:d}:{m:02d}:{s:02d}.{c:02d}"

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {canvas_w}
PlayResY: {canvas_h}
ScaledBorderAndShadow: yes
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{family},{size},{primary},{primary},{outline},{back_color},{bold},{italic},{underline},0,100,100,{spacing},0,{border_style},{outline_w},{shadow_depth},{alignment},{side},{side},{margin_v},-1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    def escape_text(value):
        # Neutralize ASS override injection while retaining Arabic logical order.
        return value.replace("\\", "＼").replace("{", "｛").replace("}", "｝").replace("\n", "\\N")
    def runs(value, chosen_family):
        # Explicit per-script font switches: bundled Arabic font for Arabic,
        # bundled/selected Latin font for everything else (no OS fallback).
        first, tagged = tag_runs(value, chosen_family, escape_text)
        return "{\\fn%s}%s" % (first, tagged) if tagged else ""

    direction_mark = {"rtl": "\u200f", "ltr": "\u200e"}.get(font_json.get("caption_direction"), "")
    def caption_runs(value, chosen_family):
        return runs(direction_mark + value if value and direction_mark else value, chosen_family)

    split = font_json.get("split", "full")
    caption_segments = font_json.get("caption_segments") or []
    if caption_segments and text.strip() and not typewriter:
        events = []
        transcript_words = ((font_json.get('transcript') or {}).get('words') or [])
        for segment in caption_segments:
            segment_text = str(segment.get('text') or '').strip()
            if not segment_text: continue
            start = max(0, min(duration_ms, int(segment.get('start_ms') or 0)))
            end = max(start + 100, min(duration_ms, int(segment.get('end_ms') or duration_ms)))
            if end <= start: continue
            if case == 'upper': segment_text = segment_text.upper()
            elif case == 'lower': segment_text = segment_text.lower()
            elif case == 'title': segment_text = ' '.join(w[:1].upper() + w[1:] for w in segment_text.split(' '))
            tokens = segment_text.split()
            timed = [row for row in transcript_words if isinstance(row, (list, tuple)) and len(row) >= 3 and start <= int(row[1]) < end]
            if [str(row[0]) for row in timed] != tokens: timed = []
            word_times_segment = [(int(row[1]), int(row[2])) for row in timed] or None
            segment_font = {**font_json, 'split': 'phrases', 'phrase_words': max(1, min(8, len(tokens)))}
            events.extend(_phrase_events(segment_text, segment_font, duration_ms, family, primary, outline, outline_w, size,
                                         start, end-start, [(start, end)], word_times_segment, ts, runs, tag_runs, escape_text,
                                         forced_end_ms=end))
    elif split == "phrases" and text.strip() and not typewriter:
        events = _phrase_events(text, font_json, duration_ms, family, primary, outline, outline_w, size,
                                speech_start_ms, speech_ms, speech_segments, word_times, ts, runs, tag_runs, escape_text)
    elif font_json.get("karaoke") and text.strip() and not typewriter:
        # Word-by-word highlight: each word switches from the caption colour
        # to the highlight colour as it is spoken. No word timings are
        # available from the voice engines, so the narration span is shared
        # out by word length (plus a small constant for the gap), which tracks
        # natural speech closely for captions.
        start = max(0, int(speech_start_ms))
        span = max(500, int(speech_ms if speech_ms else duration_ms - start))
        words = text.split()
        weights = [len(w) + 2 for w in words]
        total = sum(weights)
        hi = _hex_to_ass_color(font_json.get("highlight_color", "#FFD84D"), alpha=0)
        if word_times and len(word_times) == len(words):
            # Exact: the voice engine reported when each word is spoken.
            starts = [s for s, _ in word_times]
            ends = starts[1:] + [word_times[-1][1]]
        elif speech_segments:
            # Measured: words placed on the spoken parts of the narration.
            from app.render.word_timing import word_starts
            starts = word_starts(weights, speech_segments)
            ends = starts[1:] + [speech_segments[-1][1]]
        else:
            # No audio to measure: share the span out by word length.
            starts, t = [], start
            for weight in weights:
                starts.append(t)
                t += span * weight / total
            ends = starts[1:] + [start + span]
        style = font_json.get("karaoke_style", "fill")
        if style in ("pop", "glow", "box", "color", "underline"):
            # One event per word: spoken words in the highlight colour, the
            # current word popped (bigger) or glowing, the rest in the caption colour.
            tagged_words = [tag_runs((direction_mark if i == 0 else "") + w + (" " if i < len(words) - 1 else ""), family, escape_text) for i, w in enumerate(words)]
            def line(current: int, spoken: int) -> str:
                out = []
                for j, (first, tagged) in enumerate(tagged_words):
                    if j == current and style == "pop":
                        out.append(f"{{\\fn{first}\\1c{hi}\\fscx122\\fscy122}}{tagged}{{\\fscx100\\fscy100}}")
                    elif j == current and style == "box":
                        # a thick outline in the highlight colour forms a marker behind the word
                        out.append(f"{{\\fn{first}\\3c{hi}\\bord{max(4, size // 4)}\\blur1}}{tagged}{{\\3c{outline}\\bord{outline_w}\\blur0}}")
                    elif style == "color":
                        out.append(f"{{\\fn{first}\\1c{hi if j == current else primary}}}{tagged}")
                    elif style == "underline":
                        out.append(f"{{\\fn{first}\\1c{hi if j == current else primary}\\u{1 if j == current else 0}}}{tagged}")
                    else:
                        out.append(f"{{\\fn{first}\\1c{hi if j <= spoken and (j < spoken or j == current) else primary}}}{tagged}")
                return "".join(out)
            def halo(current: int) -> str:
                # Same text and layout, everything invisible except a soft
                # blurred outline around the current word (drawn underneath).
                out = []
                for j, (first, tagged) in enumerate(tagged_words):
                    if j == current:
                        out.append(f"{{\\fn{first}\\alpha&H00&\\1a&HFF&\\3c{hi}\\bord7\\blur9}}{tagged}")
                    else:
                        out.append(f"{{\\fn{first}\\alpha&HFF&}}{tagged}")
                return "".join(out)
            events = [f"Dialogue: 1,{ts(0)},{ts(starts[0])},Default,,0,0,0,,{line(-1, 0)}\n"]
            for i in range(len(words)):
                if style == "glow":
                    events.append(f"Dialogue: 0,{ts(starts[i])},{ts(ends[i])},Default,,0,0,0,,{halo(i)}\n")
                events.append(f"Dialogue: 1,{ts(starts[i])},{ts(ends[i])},Default,,0,0,0,,{line(i, i)}\n")
            events.append(f"Dialogue: 1,{ts(ends[-1])},{ts(duration_ms)},Default,,0,0,0,,{line(-1, len(words))}\n")
        else:
            parts = [f"{{\\1c{hi}\\2c{primary}\\k{max(0, round(starts[0] / 10))}}}"]
            for i, word in enumerate(words):
                first, tagged = tag_runs((direction_mark if i == 0 else "") + word + (" " if i < len(words) - 1 else ""), family, escape_text)
                parts.append(f"{{\\k{max(1, round((ends[i] - starts[i]) / 10))}\\fn{first}}}{tagged}")
            events = [f"Dialogue: 0,{ts(0)},{ts(duration_ms)},Default,,0,0,0,,{''.join(parts)}\n"]
    elif not typewriter or not text.strip():
        events = [f"Dialogue: 0,{ts(0)},{ts(duration_ms)},Default,,0,0,0,,{caption_runs(text, family)}\n"]
    else:
        schedule = reveal_schedule(text, duration_ms, font_json)
        events = []
        for i, event in enumerate(schedule):
            end = schedule[i + 1]['time_ms'] if i + 1 < len(schedule) else duration_ms
            substr = caption_runs(event['text'], family)
            events.append(f"Dialogue: 0,{ts(event['time_ms'])},{ts(end)},Default,,0,0,0,,{substr}\n")

    def unit_animated(text: str, family: str, animation: str, anim_ms: int, base: str, hi: str, base_direction: str = "") -> str:
        """Per-letter (or per-word) animation with inline ASS tags. libass keeps doing the
        layout, bidi and shaping; only timing tags are added between units. Arabic letters must
        stay joined (tags between them break shaping), so Arabic text animates by word."""
        by_word = animation.startswith('words-') or _ARABIC_RE.search(text) is not None or animation == 'shine' and _ARABIC_RE.search(text)
        units = re.findall(r'\s*\S+\s*', text) if by_word else [c for c in re.findall(r'\S\s*|\s+', text)]
        units = [u for u in units if u] or [text]
        n = len(units)
        d = int(max(120, min(450, anim_ms * 0.55)))
        kind = animation.split('-', 1)[-1] if animation != 'shine' else 'shine'
        out = []
        for i, u in enumerate(units):
            if i == 0 and base_direction:
                u = base_direction + u
            o = int((anim_ms - d) * i / (n - 1)) if n > 1 else 0
            if kind == 'fade':
                tags = r'\alpha&HFF&\t(%d,%d,\alpha&H00&)' % (o, o + d)
            elif kind == 'pop':
                m = o + int(d * 0.6)
                tags = r'\alpha&HFF&\fscx40\fscy40\t(%d,%d,\alpha&H00&\fscx118\fscy118)\t(%d,%d,\fscx100\fscy100)' % (o, m, m, o + d)
            elif kind == 'flip':
                tags = r'\alpha&HFF&\frx90\t(%d,%d,\alpha&H00&\frx0)' % (o, o + d)
            elif kind == 'blur':
                tags = r'\alpha&HFF&\blur12\t(%d,%d,\alpha&H00&\blur0)' % (o, o + d)
            else:   # shine: a highlight sweeps across, text visible throughout
                m = o + int(d * 0.4)
                tags = r'\t(%d,%d,\1c%s)\t(%d,%d,\1c%s)' % (o, m, hi, m, o + d, base)
            out.append('{' + tags + '}' + runs(u, family))
        return ''.join(out)

    # Caption entrance animation (plain captions only: typewriter and word-by-word highlight
    # already animate the captions their own way).
    cap_anim = font_json.get('caption_animation', 'none')
    if split != 'phrases' and text.strip() and not (typewriter or font_json.get('typewriter')) and events and (font_json.get('exit_animation', 'none') != 'none' or font_json.get('loop') == 'pulse'):
        # exit and loop for whole-text captions: prefix the caption line(s)
        tail = _exit_loop_tags(font_json, duration_ms)
        events = [e.replace(',Default,,0,0,0,,', ',Default,,0,0,0,,{' + tail + '}', 1) if e.startswith('Dialogue: 0,') else e for e in events]
    if split != 'phrases' and cap_anim not in (None, 'none') and text.strip() and not (typewriter or font_json.get('typewriter')) and not font_json.get('karaoke') and events:
        a = int(font_json.get('caption_animation_ms', 900))
        cap_color = _hex_to_ass_color(font_json.get('color', '#FFFFFF'))
        cap_hi = _hex_to_ass_color(font_json.get('highlight_color', '#FFD84D'), alpha=0)
        line_tags = {
            'fade': r'\fad(%d,0)' % a,
            'zoom': r'\fscx30\fscy30\t(0,%d,\fscx100\fscy100)' % a,
            'blur': r'\blur12\t(0,%d,\blur0)' % a,
            'glitch': r'\fscx130\fax0.2\t(0,%d,\fscx85\fax-0.2)\t(%d,%d,\fscx100\fax0)' % (a // 2, a // 2, a),
            'bounce': r'\fscx0\fscy0\t(0,%d,\fscx115\fscy115)\t(%d,%d,\fscx92\fscy92)\t(%d,%d,\fscx100\fscy100)' % (a // 2, a // 2, a * 3 // 4, a * 3 // 4, a),
            'wobble': r'\frz-7\t(0,%d,\frz6)\t(%d,%d,\frz-3)\t(%d,%d,\frz2)\t(%d,%d,\frz0)' % (a // 4, a // 4, a // 2, a // 2, a * 3 // 4, a * 3 // 4, a),
            'neon': (r'\alpha&HFF&\t(0,%d,\alpha&H00&)\t(%d,%d,\alpha&HB0&)\t(%d,%d,\alpha&H00&)\t(%d,%d,\alpha&H90&)\t(%d,%d,\alpha&H00&)'
                     % (a // 10, a * 15 // 100, a * 20 // 100, a * 25 // 100, a * 30 // 100, a * 45 // 100, a * 50 // 100, a * 55 // 100, a * 60 // 100)),
        }
        head = f"Dialogue: 0,{ts(0)},{ts(duration_ms)},Default,,0,0,0,,"
        if cap_anim.startswith(('letters-', 'words-')) or cap_anim == 'shine':
            events[0] = head + unit_animated(text, family, cap_anim, a, cap_color, cap_hi, direction_mark) + "\n"
        elif cap_anim in line_tags:
            events[0] = head + '{' + line_tags[cap_anim] + '}' + caption_runs(text, family) + "\n"
            if cap_anim == 'neon':
                events.insert(0, head.replace('Dialogue: 0,', 'Dialogue: 0,', 1) + '{' + line_tags['neon'] + r'\1a&HFF&\3c%s\bord6\blur10\shad0' % cap_hi + '}' + caption_runs(text, family) + "\n")

    for index, layer in enumerate(font_json.get('layers', [])):
        start = min(duration_ms, int(layer.get('start_ms', 0)))
        end = min(duration_ms, int(layer.get('end_ms', 0)) or duration_ms)
        if end <= start or not layer.get('text', '').strip(): continue
        x = float(layer.get('x', 50)) * canvas_w / 100
        y = float(layer.get('y', 50)) * canvas_h / 100
        color = _hex_to_ass_color(layer.get('color', '#FFFFFF'))
        animation = layer.get('animation', 'none')
        span = end - start
        exit_ms = min(span//2, int(layer.get('exit_ms', 0)))
        anim_ms = max(1,min(span-exit_ms, int(layer.get('animation_ms', 800))))
        position_tag = r'\pos(%.1f,%.1f)' % (x,y)
        extra = r'\fad(0,%d)' % exit_ms
        if animation == 'fade': extra = r'\fad(%d,%d)' % (anim_ms,exit_ms)
        origins={'slide':(-canvas_w*.2,y),'slide-right':(canvas_w*1.2,y),'slide-up':(x,canvas_h*1.2),'slide-down':(x,-canvas_h*.2)}
        if animation in origins:
            ox,oy=origins[animation]
            position_tag = r'\move(%.1f,%.1f,%.1f,%.1f,0,%d)' % (ox,oy,x,y,anim_ms)
        if animation=='zoom': extra += r'\fscx30\fscy30\t(0,%d,\fscx100\fscy100)' % anim_ms
        if animation=='blur': extra += r'\blur12\t(0,%d,\blur0)' % anim_ms
        if animation=='reveal': extra += r'\clip(0,0,0,%d)\t(0,%d,\clip(0,0,%d,%d))' % (canvas_h,anim_ms,canvas_w,canvas_h)
        if animation in _REVEAL_MASKS: extra += _reveal_mask(animation, layer, x, y, canvas_w, canvas_h, anim_ms)
        if animation=='glitch':
            extra += r'\fscx130\fax0.2\t(0,%d,\fscx85\fax-0.2)\t(%d,%d,\fscx100\fax0)' % (anim_ms//2,anim_ms//2,anim_ms)
        a = anim_ms
        if animation=='bounce':
            extra += r'\fscx0\fscy0\t(0,%d,\fscx115\fscy115)\t(%d,%d,\fscx92\fscy92)\t(%d,%d,\fscx100\fscy100)' % (a*50//100,a*50//100,a*75//100,a*75//100,a)
        if animation=='wobble':
            extra += r'\frz-7\t(0,%d,\frz6)\t(%d,%d,\frz-3)\t(%d,%d,\frz2)\t(%d,%d,\frz0)' % (a//4,a//4,a//2,a//2,a*3//4,a*3//4,a)
        flicker = (r'\alpha&HFF&\t(0,%d,\alpha&H00&)\t(%d,%d,\alpha&HB0&)\t(%d,%d,\alpha&H00&)\t(%d,%d,\alpha&H90&)\t(%d,%d,\alpha&H00&)'
                   % (a//10,a*15//100,a*20//100,a*25//100,a*30//100,a*45//100,a*50//100,a*55//100,a*60//100))
        if animation=='neon': extra += flicker
        hi_color = _hex_to_ass_color(layer.get('highlight', '#FFD84D'))
        align={'left':4,'center':5,'right':6}.get(layer.get('align','center'),5)
        family=layer.get('family','Noto Naskh Arabic')
        if family not in LAYER_FAMILIES: family='Noto Naskh Arabic'
        layer_size = int(round(int(layer.get('size', 64)) * text_scale(family, layer.get('text', ''))))
        if layer.get('kind') == 'text_box':
            side_margin = round(canvas_w * (100 - float(layer.get('box_width', 80))) / 200)
        else:
            side_margin = 0
        event_prefix = f"Dialogue: {index+1},{ts(start)},{ts(end)},Default,,{side_margin},{side_margin},0,,"
        overrides = r'{\an%d%s\fs%d\c%s\b%d\bord%.1f\shad%.1f\fsp%.1f%s}' % (align,position_tag,layer_size,color,int(layer.get('bold',False)),layer.get('outline_width',0),layer.get('shadow',0),float(layer.get('spacing',0) or 0),extra)
        if animation == 'typewriter':
            schedule = reveal_schedule(layer['text'],span,{'typewriter_delay_ms':0,'typewriter_duration_ms':anim_ms})
            for j,event in enumerate(schedule):
                stop = schedule[j+1]['time_ms'] if j+1<len(schedule) else span
                event_overrides=overrides if j==len(schedule)-1 else overrides.replace(r'\fad(0,%d)' % exit_ms,'')
                event_prefix_time = f"Dialogue: {index+1},{ts(start+event['time_ms'])},{ts(start+stop)},Default,,{side_margin},{side_margin},0,,"
                events.append(f"{event_prefix_time}{event_overrides}{runs(event['text'], family)}\n")
        elif animation.startswith(('letters-','words-')) or animation == 'shine':
            events.append(f"{event_prefix}{overrides}{unit_animated(layer['text'], family, animation, anim_ms, color, hi_color)}\n")
        elif animation == 'neon':
            # glow: a blurred outline in the highlight colour underneath, sharp text on top, both flickering on
            halo = overrides.replace('}', r'\1a&HFF&\3c%s\bord%d\blur10\shad0}' % (hi_color, max(4, int(layer.get('size',64)) // 10)), 1)
            events.append(f"{event_prefix}{halo}{runs(layer['text'], family)}\n")
            events.append(f"{event_prefix}{overrides}{runs(layer['text'], family)}\n")
        else:
            events.append(f"{event_prefix}{overrides}{runs(layer['text'], family)}\n")

    path = out_path or str(TMP_DIR / f"{scene_id}_captions.ass")
    with open(path, "w", encoding="utf-8-sig") as fh:
        fh.write(header)
        fh.writelines(events)
    return path
