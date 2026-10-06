"""Non-destructive, source-clock audio censorship. No transcript or provider calls."""
import math


def clean_ranges(raw, source_ms=None):
    if not isinstance(raw, list) or len(raw) > 100:
        raise ValueError('Use up to 100 censor ranges.')
    out = []
    for row in raw:
        if not isinstance(row, dict) or set(row) - {'start_ms', 'end_ms', 'mode'}:
            raise ValueError('Censor ranges need start, end and Bleep or Mute.')
        a, b, mode = row.get('start_ms'), row.get('end_ms'), row.get('mode', 'bleep')
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (a, b)):
            raise ValueError('Censor times must be finite numbers.')
        if a < 0 or b-a < 20 or b > (source_ms or 86_400_000) or mode not in ('bleep', 'mute'):
            raise ValueError('Keep censor ranges inside the source, at least 20 ms long; choose Bleep or Mute.')
        out.append({'start_ms': round(a), 'end_ms': round(b), 'mode': mode})
    out.sort(key=lambda r: r['start_ms'])
    if any(a['end_ms'] > b['start_ms'] for a, b in zip(out, out[1:])):
        raise ValueError('Censor ranges cannot overlap. Review or remove overlapping ranges.')
    return out


def censor_filter(rows, offset_ms=0):
    if not rows:
        return ''
    expr = 'val(ch)'
    for r in reversed(rows):
        start, end = (r['start_ms']-offset_ms)/1000, (r['end_ms']-offset_ms)/1000
        tone = '0' if r['mode'] == 'mute' else '0.15*sin(2*PI*1000*t)'
        expr = f'if(gte(t,{start:.3f})*lt(t,{end:.3f}),{tone},{expr})'
    return f"aeval=exprs='{expr}':c=same"
