"""One deterministic reveal schedule for ASS captions and keystroke audio."""
from __future__ import annotations
import array
import math
import unicodedata
import wave
from pathlib import Path

SAMPLE_RATE = 48000
from app.config import RESOURCE_DIR
DEFAULT_KEY = RESOURCE_DIR / 'assets' / 'sfx' / 'typewriter-key.wav'


def graphemes(text: str) -> list[str]:
    """Keep combining marks, emoji modifiers/ZWJ sequences and flag pairs intact.

    Covers Arabic vowel marks and mixed Arabic/Latin captions without reversing
    logical text. This is not a complete Unicode UAX #29 implementation.
    """
    result = []
    for char in text:
        code = ord(char)
        extend = unicodedata.category(char).startswith('M') or char in ('\u200d','\ufe0f','\ufe0e') or 0x1f3fb <= code <= 0x1f3ff
        flag_pair = result and 0x1f1e6 <= code <= 0x1f1ff and len(result[-1]) == 1 and 0x1f1e6 <= ord(result[-1]) <= 0x1f1ff
        if result and (extend or result[-1].endswith('\u200d') or flag_pair): result[-1] += char
        else: result.append(char)
    return result


def reveal_schedule(text: str, duration_ms: int, font: dict) -> list[dict]:
    if not text.strip() or duration_ms <= 0: return []
    clusters = graphemes(text)
    # ASS has centisecond precision; the sound uses these exact same times.
    last_cs = max(0, (duration_ms - 1) // 10)
    delay_cs = min(last_cs, max(0, int(font.get('typewriter_delay_ms', 0))) // 10)
    legacy_span = max(200, (len(clusters) - 1) * 160)  # calm default: about six characters per second
    span_ms = max(100, int(font.get('typewriter_duration_ms', legacy_span)))
    available_cs = max(0, last_cs - delay_cs)
    span_cs = min(available_cs, span_ms // 10)
    events = []
    prefix = ''
    # Group reveals sharing a centisecond. Avoid zero-length ASS events for long text.
    for i, cluster in enumerate(clusters):
        prefix += cluster
        when = (delay_cs + round(i * span_cs / max(1, len(clusters)-1))) * 10
        audible = not cluster.isspace() and any(unicodedata.category(c)[0] not in ('M','C') for c in cluster)
        if events and events[-1]['time_ms'] == when:
            events[-1]['text'] = prefix
            events[-1]['sound'] |= audible
        else: events.append({'time_ms':when,'text':prefix,'sound':audible})
    return events


def extract_keystroke(source_wav: str | Path, output_wav: str | Path) -> str:
    """Find a sharp energy rise, isolate 80 ms, and fade the edges.

    Input must be mono, 48 kHz, signed 16-bit PCM. The caller decodes uploaded
    audio with FFmpeg, limited to the first 30 seconds.
    """
    with wave.open(str(source_wav), 'rb') as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, SAMPLE_RATE):
            raise ValueError('Keystroke input must be mono 48 kHz PCM.')
        samples = array.array('h', w.readframes(SAMPLE_RATE * 30))
    if not samples or max(map(abs, samples)) < 100: raise ValueError('No audible keystroke found in this sound file.')
    block=480
    levels=[math.sqrt(sum(v*v for v in samples[i:i+block])/len(samples[i:i+block])) for i in range(0,len(samples),block)]
    peak=max(range(len(levels)),key=lambda i:levels[i]-(levels[i-1] if i else 0))
    start=max(0,peak*block-96)
    segment=samples[start:start+3840]
    maximum=max(1,max(map(abs,segment)))
    scale=0.72*32767/maximum
    key=array.array('h')
    for i,v in enumerate(segment):
        envelope=min(1.0,i/48,max(0,(len(segment)-1-i)/288))
        key.append(int(v*scale*envelope))
    with wave.open(str(output_wav),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(SAMPLE_RATE);w.writeframes(key.tobytes())
    return str(output_wav)


def write_typing_audio(events: list[dict], duration_ms: int, key_path: str | Path, output: str | Path, volume: float = .5) -> str:
    with wave.open(str(key_path),'rb') as w:
        if (w.getnchannels(),w.getsampwidth(),w.getframerate()) != (1,2,SAMPLE_RATE): raise ValueError('Invalid keystroke sample format')
        key=array.array('h',w.readframes(w.getnframes()))
    volume=max(0,min(1,float(volume)))
    # Write sequentially, using silence between keys rather than allocating a long scene in RAM.
    cursor=0; total=max(0,round(duration_ms*SAMPLE_RATE/1000))
    audible=[e for e in events if e['sound']]
    with wave.open(str(output),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(SAMPLE_RATE)
        def silence(count):
            while count>0:
                n=min(count,SAMPLE_RATE);w.writeframesraw(b'\x00\x00'*n);count-=n
        for index,event in enumerate(audible):
            start=round(event['time_ms']*SAMPLE_RATE/1000)
            if start>=total:break
            silence(max(0,start-cursor));cursor=max(start,cursor)
            next_start=round(audible[index+1]['time_ms']*SAMPLE_RATE/1000) if index+1<len(audible) else total
            length=min(len(key),max(0,next_start-cursor),total-cursor)
            chunk=array.array('h',(int(key[i]*volume*min(1,max(0,(length-1-i)/96))) for i in range(length)))
            w.writeframesraw(chunk.tobytes());cursor+=length
        silence(total-cursor)
    return str(output)
