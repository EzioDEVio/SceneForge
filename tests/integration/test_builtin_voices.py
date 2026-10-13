"""Voices without Docker (0.9.4-beta.3): built-in Kokoro (real model, real synthesis),
Gemini voices (Google AI Studio key; HTTP mocked, no paid or keyed calls) and an optional
Voicebox connection (local API mocked). Downloads the Kokoro files (~120 MB) once into
SCENEFORGE_KOKORO_DIR or a temporary folder."""
import base64, io, json, os, pathlib, sys, tempfile, threading, wave
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

root = pathlib.Path(__file__).resolve().parents[2]
tmp = tempfile.TemporaryDirectory()
os.environ['SCENEFORGE_DATA_DIR'] = tmp.name
os.environ['SCENEFORGE_SD_AUTOSTART'] = '0'
os.environ.setdefault('SCENEFORGE_KOKORO_DIR', str(pathlib.Path(tmp.name) / 'kokoro'))
sys.path.insert(0, str(root / 'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.providers import kokoro_builtin, gemini_tts, voicebox

checks = 0
def check(name, ok):
    global checks
    assert ok, name
    checks += 1
    print('PASS ' + name, flush=True)

with TestClient(app) as c:
    pid = c.post('/api/projects', json={'title': 'Voices without Docker'}).json()['id']
    sid = c.get(f'/api/projects/{pid}').json()['scenes'][0]['id']
    c.patch(f'/api/scenes/{sid}', json={'spoken_text': 'In Bell Labs, a story began that changed the world.'})

    # ---- built-in Kokoro ----
    if not kokoro_builtin.installed():
        r = c.post('/api/local-speech/kokoro_builtin/connect')
        check('connecting before the download explains the one-time download', r.status_code == 409 and 'MB' in r.json()['detail'])
        kokoro_builtin.download()
    check('Kokoro files are present and verified', kokoro_builtin.installed() and c.get('/api/local-speech/kokoro_builtin/status').json()['installed'])
    con = c.post('/api/local-speech/kokoro_builtin/connect').json()
    check('built-in Kokoro connects without Docker or a key', con['status'] == 'ready' and 'af_heart' in con['voices'])
    voices = c.get(f"/api/providers/profile/{con['profile']['id']}/voices").json()['voices']
    check('voices carry their language', any(v['id'] == 'ff_siwis' and v['language'] == 'fr' for v in voices) and all(v['language'] for v in voices))
    take = c.post(f'/api/scenes/{sid}/voice-takes/service', json={'provider_id': con['profile']['id'], 'voice': 'af_heart', 'language': 'en', 'speed': 1.0})
    check('built-in Kokoro narration becomes the accepted take', take.status_code == 200 and take.json()['accepted'] and take.json()['measured_duration_ms'] > 1500)
    slow = c.post(f'/api/scenes/{sid}/voice-takes/service', json={'provider_id': con['profile']['id'], 'voice': 'af_heart', 'language': 'en', 'speed': 0.7}).json()
    check('speaking speed changes the length', slow['measured_duration_ms'] > take.json()['measured_duration_ms'] * 1.2)
    bad = c.post(f'/api/scenes/{sid}/voice-takes/service', json={'provider_id': con['profile']['id'], 'voice': 'ff_siwis', 'language': 'en', 'speed': 1.0})
    check('a voice of another language is refused with a reason', bad.status_code == 502 and 'French' in bad.text)
    c.patch(f'/api/scenes/{sid}', json={'spoken_text': 'مرحبا بالعالم'})
    ar = c.post(f'/api/scenes/{sid}/voice-takes/service', json={'provider_id': con['profile']['id'], 'voice': 'af_heart', 'language': 'en', 'speed': 1.0})
    check('Arabic is sent to Chatterbox or Gemini instead', ar.status_code == 502 and 'Arabic' in ar.text)

    # ---- Gemini voices (mocked HTTP) ----
    pcm = (b'\x00\x10' * 24000)   # one second of 24 kHz mono PCM
    wav = io.BytesIO()
    with wave.open(wav, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
    calls = []
    class Resp:
        def __init__(self, status, payload): self.status_code, self._p, self.ok = status, payload, status < 400
        def json(self): return self._p
    def fake_post(url, headers=None, json=None, timeout=None, **kw):
        calls.append((url, headers, json))
        if url.endswith('/interactions'):
            return Resp(200, {'steps': [{'type': 'model_output', 'content': [{'type': 'audio', 'data': base64.b64encode(wav.getvalue()).decode()}]}]})
        raise AssertionError(url)
    # This test machine has no OS credential store; stand in for it (the real store is tested in test_credentials).
    from app.api import providers as providers_api
    from app.providers import speech_http
    vault = {}
    def obscure(k): vault['keyring:fixture'] = k; return 'keyring:fixture'
    patch.object(providers_api, 'obscure', side_effect=obscure).start()
    patch.object(providers_api, 'reveal', side_effect=lambda ref: vault.get(ref, '')).start()
    patch.object(speech_http, 'reveal', side_effect=lambda ref: vault.get(ref, '')).start()
    r = c.post('/api/providers', json={'capability': 'speech', 'name': 'gemini_tts', 'api_key': 'fixture-ai-studio-key', 'base_url': '', 'model': ''})
    check('Gemini voices save with an AI Studio key', r.status_code == 200 and r.json()['configured'])
    gid = r.json()['id']
    names = [v['id'] for v in c.get(f'/api/providers/profile/{gid}/voices').json()['voices']]
    check('30 Gemini voices are offered', len(names) == 30 and 'Kore' in names)
    with patch.object(gemini_tts.requests, 'post', side_effect=fake_post):
        g = c.post(f'/api/scenes/{sid}/voice-takes/service', json={'provider_id': gid, 'voice': 'Kore', 'language': 'ar', 'speed': 1.0})
    check('Gemini narrates Arabic text into an accepted take', g.status_code == 200 and g.json()['provider'] == 'gemini_tts' and 900 < g.json()['measured_duration_ms'] < 1200)
    url, headers, body = calls[-1]
    check('the request uses the key header, the chosen voice and the text', headers['x-goog-api-key'] == 'fixture-ai-studio-key'
          and body['generation_config']['speech_config'][0]['voice'] == 'Kore' and body['input'][0]['content'][0]['text'] == 'مرحبا بالعالم')
    def fallback_post(url, headers=None, json=None, timeout=None, **kw):
        if url.endswith('/interactions'):
            return Resp(404, {'error': {'message': 'not found'}})
        return Resp(200, {'candidates': [{'content': {'parts': [{'inlineData': {'mimeType': 'audio/L16;rate=24000', 'data': base64.b64encode(pcm).decode()}}]}}]})
    with patch.object(gemini_tts.requests, 'post', side_effect=fallback_post):
        g2 = c.post(f'/api/scenes/{sid}/voice-takes/service', json={'provider_id': gid, 'voice': 'Puck', 'language': 'ar', 'speed': 1.0})
    check('older accounts fall back to generateContent audio', g2.status_code == 200 and g2.json()['measured_duration_ms'] > 900)
    with patch.object(gemini_tts.requests, 'post', return_value=Resp(429, {'error': {'message': 'quota'}})):
        q = c.post(f'/api/scenes/{sid}/voice-takes/service', json={'provider_id': gid, 'voice': 'Kore', 'language': 'ar', 'speed': 1.0})
    check('a used-up free limit is explained', q.status_code == 502 and 'free limit' in q.text)

    # ---- Voicebox (local API mocked) ----
    r = c.post('/api/local-speech/voicebox/connect')
    check('Voicebox not running is explained', r.status_code == 503 and 'voicebox.sh' in r.text)
    class VB(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype='application/json'):
            self.send_response(code); self.send_header('Content-Type', ctype); self.end_headers(); self.wfile.write(body)
        def do_GET(self):
            if self.path == '/profiles': self._send(200, json.dumps([{'id': 'p1', 'name': 'Narrator', 'language': 'en'}]).encode())
            elif self.path == '/audio/g1': self._send(200, wav.getvalue(), 'audio/wav')
            else: self._send(404, b'{}')
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            VB.last = payload
            self._send(200, json.dumps({'id': 'g1', 'profile_id': payload['profile_id'], 'audio_path': 'x.wav'}).encode())
        def log_message(self, *a): pass
    srv = HTTPServer(('127.0.0.1', 0), VB)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    with patch.object(voicebox, 'DEFAULT_URL', f'http://127.0.0.1:{srv.server_address[1]}'):
        vb = c.post('/api/local-speech/voicebox/connect').json()
        check('a running Voicebox connects and lists its profiles', vb['voices'] == ['p1'])
        t = c.post(f'/api/scenes/{sid}/voice-takes/service', json={'provider_id': vb['profile']['id'], 'voice': 'p1', 'language': 'en', 'speed': 1.0})
    check('Voicebox narration is fetched and saved as a take', t.status_code == 200 and t.json()['provider'] == 'voicebox' and VB.last['profile_id'] == 'p1')
    srv.shutdown()
print(f'{checks} built-in and optional voice checks passed')
