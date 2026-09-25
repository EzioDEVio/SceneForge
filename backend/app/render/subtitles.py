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

from app.config import TMP_DIR
from app.render.fontruns import tag_runs
from app.render.typewriter import reveal_schedule


def _hex_to_ass_color(hex_color: str, alpha: int = 0) -> str:
    """ASS colors are &HAABBGGRR. hex_color is '#RRGGBB'. alpha 0=opaque."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        hex_color = "FFFFFF"
    r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
    return f"&H{alpha:02X}{b}{g}{r}"


_ALIGNMENT = {"bottom": 2, "top": 8, "middle": 5}
LAYER_FAMILIES = ("Noto Naskh Arabic", "Noto Sans Arabic", "Noto Sans")


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
    size = int(font_json.get("size", 44))
    primary = _hex_to_ass_color(font_json.get("color", "#FFFFFF"), alpha=0)
    outline = _hex_to_ass_color(font_json.get("outline_color", "#000000"), alpha=0)
    outline_w = int(font_json.get("outline_width", 2))
    position = font_json.get("position", "bottom")
    alignment = _ALIGNMENT.get(position, 2)
    background = font_json.get("background", "none")
    border_style = 3 if background == "box" else 1
    back_color = _hex_to_ass_color("#000000", alpha=96) if background == "box" else "&H00000000"
    margin_v = 60

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
Style: Default,{family},{size},{primary},{primary},{outline},{back_color},0,0,0,0,100,100,0,0,{border_style},{outline_w},0,{alignment},40,40,{margin_v},-1

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

    if font_json.get("karaoke") and text.strip() and not typewriter:
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
        if style in ("pop", "glow"):
            # One event per word: spoken words in the highlight colour, the
            # current word popped (bigger) or glowing, the rest in the caption colour.
            tagged_words = [tag_runs(w + (" " if i < len(words) - 1 else ""), family, escape_text) for i, w in enumerate(words)]
            def line(current: int, spoken: int) -> str:
                out = []
                for j, (first, tagged) in enumerate(tagged_words):
                    if j == current and style == "pop":
                        out.append(f"{{\\fn{first}\\1c{hi}\\fscx122\\fscy122}}{tagged}{{\\fscx100\\fscy100}}")
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
                first, tagged = tag_runs(word + (" " if i < len(words) - 1 else ""), family, escape_text)
                parts.append(f"{{\\k{max(1, round((ends[i] - starts[i]) / 10))}\\fn{first}}}{tagged}")
            events = [f"Dialogue: 0,{ts(0)},{ts(duration_ms)},Default,,0,0,0,,{''.join(parts)}\n"]
    elif not typewriter or not text.strip():
        events = [f"Dialogue: 0,{ts(0)},{ts(duration_ms)},Default,,0,0,0,,{runs(text, family)}\n"]
    else:
        schedule = reveal_schedule(text, duration_ms, font_json)
        events = []
        for i, event in enumerate(schedule):
            end = schedule[i + 1]['time_ms'] if i + 1 < len(schedule) else duration_ms
            substr = runs(event['text'], family)
            events.append(f"Dialogue: 0,{ts(event['time_ms'])},{ts(end)},Default,,0,0,0,,{substr}\n")

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
        if animation=='glitch':
            extra += r'\fscx130\fax0.2\t(0,%d,\fscx85\fax-0.2)\t(%d,%d,\fscx100\fax0)' % (anim_ms//2,anim_ms//2,anim_ms)
        align={'left':4,'center':5,'right':6}.get(layer.get('align','center'),5)
        family=layer.get('family','Noto Naskh Arabic')
        if family not in LAYER_FAMILIES: family='Noto Naskh Arabic'
        overrides = r'{\an%d%s\fs%d\c%s\b%d\bord%.1f\shad%.1f%s}' % (align,position_tag,layer.get('size',64),color,int(layer.get('bold',False)),layer.get('outline_width',0),layer.get('shadow',0),extra)
        if animation == 'typewriter':
            schedule = reveal_schedule(layer['text'],span,{'typewriter_delay_ms':0,'typewriter_duration_ms':anim_ms})
            for j,event in enumerate(schedule):
                stop = schedule[j+1]['time_ms'] if j+1<len(schedule) else span
                event_overrides=overrides if j==len(schedule)-1 else overrides.replace(r'\fad(0,%d)' % exit_ms,'')
                events.append(f"Dialogue: {index+1},{ts(start+event['time_ms'])},{ts(start+stop)},Default,,0,0,0,,{event_overrides}{runs(event['text'], family)}\n")
        else:
            events.append(f"Dialogue: {index+1},{ts(start)},{ts(end)},Default,,0,0,0,,{overrides}{runs(layer['text'], family)}\n")

    path = out_path or str(TMP_DIR / f"{scene_id}_captions.ass")
    with open(path, "w", encoding="utf-8-sig") as fh:
        fh.write(header)
        fh.writelines(events)
    return path
