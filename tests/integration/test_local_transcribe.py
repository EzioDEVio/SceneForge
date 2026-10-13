"""Local Whisper fallback paths without downloading or loading model weights."""
import pathlib
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))

from app.providers import transcribe


checks = 0


def check(name, ok):
    global checks
    assert ok, name
    checks += 1
    print('PASS ' + name, flush=True)


class FakeWhisper:
    def __init__(self, retry_empty=False, no_word_times=False, blank_word=False):
        self.retry_empty = retry_empty
        self.no_word_times = no_word_times
        self.blank_word = blank_word
        self.calls = []

    def transcribe(self, path, **kwargs):
        self.calls.append({'path': path, **kwargs})
        if self.retry_empty and kwargs['vad_filter']:
            return iter(()), SimpleNamespace(language='en')
        if self.no_word_times:
            words = [SimpleNamespace(word=' ', start=.4, end=.6)] if self.blank_word else None
            rows = [SimpleNamespace(text='Clear speech here', start=.4, end=1.6, words=words)]
        else:
            word = SimpleNamespace(word=' Hello', start=.4, end=.8)
            rows = [SimpleNamespace(text=' Hello', start=.4, end=.8, words=[word])]
        return iter(rows), SimpleNamespace(language='en')


fake_module = SimpleNamespace(WhisperModel=lambda *args, **kwargs: None)
with patch.dict(sys.modules, {'faster_whisper': fake_module}):
    model = FakeWhisper(retry_empty=True, no_word_times=True)
    with patch.object(transcribe, '_LOCAL_MODEL', model), patch.object(transcribe, '_normalize_local_audio', return_value='normalized.wav'), patch.object(transcribe, '_decode_pcm16k', side_effect=lambda p: {'decoded': p}):
        result = transcribe._local('speech.wav', 'en')
    check('manual language is passed through to local Whisper',
          len(model.calls) == 2 and all(call['language'] == 'en' for call in model.calls)
          and all(call['path'] == {'decoded': 'normalized.wav'} for call in model.calls)
          and all(call['condition_on_previous_text'] is False for call in model.calls))
    check('empty VAD pass retries clean audio without VAD',
          model.calls[0]['vad_filter'] is True and model.calls[1]['vad_filter'] is False and result['text'] == 'Clear speech here')
    check('recognized text without word alignment still yields editable timed captions',
          result['word_timing'] == 'estimated' and len(result['words']) == 3
          and result['words'][0][1] == 400 and result['words'][-1][2] == 1600)

    aligned = FakeWhisper()
    with patch.object(transcribe, '_LOCAL_MODEL', aligned), patch.object(transcribe, '_normalize_local_audio', return_value='normalized.wav'), patch.object(transcribe, '_decode_pcm16k', side_effect=lambda p: {'decoded': p}):
        exact = transcribe._local('speech.wav', None)
    check('normal local word timestamps are preserved',
          exact['word_timing'] == 'whisper' and exact['words'] == [['Hello', 400, 800]])

    blank = FakeWhisper(no_word_times=True, blank_word=True)
    with patch.object(transcribe, '_LOCAL_MODEL', blank), patch.object(transcribe, '_normalize_local_audio', return_value='normalized.wav'), patch.object(transcribe, '_decode_pcm16k', side_effect=lambda p: {'decoded': p}):
        estimated = transcribe._local('speech.wav', 'en')
    check('blank word-alignment entries fall back to estimated phrase timing',
          estimated['word_timing'] == 'estimated' and len(estimated['words']) == 3)

import numpy as np


class SongWhisper:
    """VAD keeps only a few sung words of a 3:19 song; without VAD every line is heard."""
    def __init__(self):
        self.calls = []

    def transcribe(self, audio, **kwargs):
        self.calls.append(kwargs['vad_filter'])
        n = 6 if kwargs['vad_filter'] else 320
        lyric = 'hear the call of the north'.split()
        rows = []
        for i in range(0, n, 3):
            ws = [SimpleNamespace(word=' ' + lyric[(i + k) % 6] + str((i + k) // 6), start=(i + k) * .6, end=(i + k) * .6 + .5) for k in range(min(3, n - i))]
            rows.append(SimpleNamespace(text=' '.join(w.word.strip() for w in ws), start=ws[0].start, end=ws[-1].end, words=ws))
        return iter(rows), SimpleNamespace(language='en')


class LoopWhisper:
    def transcribe(self, audio, **kwargs):
        ws = [SimpleNamespace(word=' ' + x, start=i * .5, end=i * .5 + .4) for i, x in enumerate(('thank you ' * 30 + 'the end').split())]
        return iter([SimpleNamespace(text='x', start=0, end=30, words=ws)]), SimpleNamespace(language='en')


with patch.dict(sys.modules, {'faster_whisper': fake_module}):
    song = SongWhisper()
    with patch.object(transcribe, '_LOCAL_MODEL', song), patch.object(transcribe, '_normalize_local_audio', return_value='n.wav'), \
         patch.object(transcribe, '_decode_pcm16k', return_value=np.zeros(199 * 16000, np.float32)):
        sung = transcribe._local('song.wav', 'en')
    check('a song where VAD keeps few words is transcribed again without VAD and the fuller pass is kept',
          song.calls == [True, False] and len(sung['words']) >= 300)
    with patch.object(transcribe, '_LOCAL_MODEL', LoopWhisper()), patch.object(transcribe, '_normalize_local_audio', return_value='n.wav'), \
         patch.object(transcribe, '_decode_pcm16k', return_value=np.zeros(30 * 16000, np.float32)):
        looped = transcribe._local('music.wav', 'en')
    check('a line Whisper repeats endlessly over music is kept at most three times',
          [w[0] for w in looped['words']] == ['thank', 'you'] * 3 + ['the', 'end'])

import subprocess, tempfile, os
with tempfile.TemporaryDirectory() as d:
    wav = os.path.join(d, 'tone.wav')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=f=440:d=1.5:r=44100', '-ac', '2', wav], check=True)
    samples = transcribe._decode_pcm16k(wav)
    check('audio is decoded with FFmpeg to mono 16 kHz float samples (no PyAV)',
          isinstance(samples, np.ndarray) and samples.dtype == np.float32 and abs(len(samples) - 24000) < 400 and 0.05 < float(np.abs(samples).max()) <= 1.0)
    src = pathlib.Path(transcribe.__file__).read_text()
    check('local transcription passes samples, never a file path, to Faster-Whisper', '_LOCAL_MODEL.transcribe(audio,' in src)
print(f'{checks} local-transcription checks passed')
