"""Optional isolated Chatterbox Multilingual service; models load on first request."""
import io
import os
import threading
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

app = FastAPI(title='SceneForge Chatterbox bridge')
lock = threading.Lock()
model = None
last_error = None
loading = False

class Speech(BaseModel):
    input: str = Field(min_length=1, max_length=10000)
    language: str = 'en'
    voice: str = 'default'
    speed: float = Field(default=1, ge=0.5, le=2)
    response_format: str = 'wav'

@app.get('/health')
def health():
    return {'service':'chatterbox','model_ready':model is not None,'loading':loading,'last_error':last_error}

@app.get('/v1/audio/voices')
def voices():
    return {'voices': [{'id': 'default'}]}

@app.post('/v1/audio/speech')
def speech(body: Speech):
    global model, last_error, loading
    try:
        import torch
        import soundfile as sf
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        if body.voice != 'default' or body.response_format != 'wav':
            raise HTTPException(400, 'This bridge supports the default voice and WAV output.')
        with lock:
            loading = True
            last_error = None
            if model is None:
                model = ChatterboxMultilingualTTS.from_pretrained(device=os.environ.get('CHATTERBOX_DEVICE', 'cuda' if torch.cuda.is_available() else 'cpu'))
            wav = model.generate(body.input, language_id=body.language)
            # Change tempo without pitch shift. Model speed is not a native parameter.
            import librosa
            samples = wav.squeeze().detach().cpu().numpy()
            if body.speed != 1: samples = librosa.effects.time_stretch(samples, rate=body.speed)
            out = io.BytesIO()
            sf.write(out, samples, model.sr, format='WAV', subtype='PCM_16')
            return Response(out.getvalue(), media_type='audio/wav')
    except HTTPException:
        raise
    except Exception as exc:
        import logging
        logging.exception('Chatterbox synthesis failed')
        last_error = f'{type(exc).__name__}: {exc}'
        raise HTTPException(503, 'Chatterbox could not generate speech: ' + last_error[:600] + '. Run DIAGNOSE_VOICE.bat for the complete service log.') from exc
    finally:
        loading = False
