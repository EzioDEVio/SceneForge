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
    with patch.object(transcribe, '_LOCAL_MODEL', model), patch.object(transcribe, '_normalize_local_audio', return_value='normalized.wav'):
        result = transcribe._local('speech.wav', 'en')
    check('manual language is passed through to local Whisper',
          len(model.calls) == 2 and all(call['language'] == 'en' for call in model.calls)
          and all(call['path'] == 'normalized.wav' for call in model.calls)
          and all(call['condition_on_previous_text'] is False for call in model.calls))
    check('empty VAD pass retries clean audio without VAD',
          model.calls[0]['vad_filter'] is True and model.calls[1]['vad_filter'] is False and result['text'] == 'Clear speech here')
    check('recognized text without word alignment still yields editable timed captions',
          result['word_timing'] == 'estimated' and len(result['words']) == 3
          and result['words'][0][1] == 400 and result['words'][-1][2] == 1600)

    aligned = FakeWhisper()
    with patch.object(transcribe, '_LOCAL_MODEL', aligned), patch.object(transcribe, '_normalize_local_audio', return_value='normalized.wav'):
        exact = transcribe._local('speech.wav', None)
    check('normal local word timestamps are preserved',
          exact['word_timing'] == 'whisper' and exact['words'] == [['Hello', 400, 800]])

    blank = FakeWhisper(no_word_times=True, blank_word=True)
    with patch.object(transcribe, '_LOCAL_MODEL', blank), patch.object(transcribe, '_normalize_local_audio', return_value='normalized.wav'):
        estimated = transcribe._local('speech.wav', 'en')
    check('blank word-alignment entries fall back to estimated phrase timing',
          estimated['word_timing'] == 'estimated' and len(estimated['words']) == 3)

print(f'{checks} local-transcription checks passed')
