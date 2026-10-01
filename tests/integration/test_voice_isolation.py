"""AI voice isolation: real MDX-Net model (Kim_Vocal_2.onnx), quality metric, API, cache, video input.

Downloads the model (~67 MB) from GitHub releases on first run into SCENEFORGE_VOICE_MODEL_DIR
(or a temp folder). Skips with a message only when github.com is unreachable.

Quality check: a synthetic speech-like voice (glottal harmonics shaped by moving vowel
formants, syllable envelopes, pauses, consonant noise) is mixed at equal loudness with
loud music (saw-pad chords, square bass, kick, snare and hi-hat noise bursts). The
isolated output must improve the voice SDR by at least 6 dB over the mix.
"""
import io, os, pathlib, subprocess, sys, tempfile, time, wave
import numpy as np
root = pathlib.Path(__file__).resolve().parents[2]
tmp = tempfile.TemporaryDirectory(); os.environ['SCENEFORGE_DATA_DIR'] = tmp.name
t = pathlib.Path(tmp.name)
os.environ.setdefault('SCENEFORGE_VOICE_MODEL_DIR', str(t / 'models'))
sys.path.insert(0, str(root / 'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.render import voice_isolation as vi
n = 0
def check(name, ok):
    global n
    assert ok, name
    n += 1; print('PASS ' + name, flush=True)

SR = 44100
VOWELS = [[(800, 80), (1150, 90), (2900, 120), (3900, 130)], [(400, 60), (1700, 80), (2600, 100), (3700, 120)],
          [(270, 60), (2300, 100), (3000, 120), (3700, 130)], [(450, 70), (800, 80), (2830, 100), (3800, 130)],
          [(325, 50), (700, 60), (2530, 170), (3500, 180)]]


def speech(seconds, seed=1):
    rng = np.random.default_rng(seed); nn = int(seconds * SR); tt = np.arange(nn) / SR
    syl = np.zeros(nn); fr = [np.zeros(nn) for _ in range(4)]; bw = [np.zeros(nn) for _ in range(4)]; fric = np.zeros(nn)
    pos = int(0.2 * SR)
    while pos < nn:
        for _ in range(rng.integers(4, 9)):
            d = int(rng.uniform(0.14, 0.26) * SR)
            if pos + d > nn:
                break
            v = VOWELS[rng.integers(len(VOWELS))]
            syl[pos:pos + d] = np.sin(np.pi * np.linspace(0, 1, d)) ** 0.6
            for k in range(4):
                fr[k][pos:pos + d] = v[k][0] * rng.uniform(0.95, 1.05); bw[k][pos:pos + d] = v[k][1]
            if rng.random() < 0.35:
                fd = int(0.05 * SR); s = max(0, pos - fd // 2); fric[s:s + fd] = np.hanning(fd)[:len(fric[s:s + fd])] * 0.5
            pos += d + int(rng.uniform(0.01, 0.05) * SR)
        pos += int(rng.uniform(0.25, 0.5) * SR)
    ker = np.hanning(int(0.03 * SR)); ker /= ker.sum()
    for k in range(4):
        fr[k] = np.convolve(fr[k], ker, mode='same'); fr[k][fr[k] < 100] = [500, 1500, 2500, 3500][k]
    f0 = np.clip(140 + 30 * np.sin(2 * np.pi * 0.35 * tt) + 15 * np.sin(2 * np.pi * 1.7 * tt + 1) + rng.normal(0, 1, nn).cumsum() * 0.002, 90, 240)
    ph = 2 * np.pi * np.cumsum(f0) / SR; out = np.zeros(nn)
    for h in range(1, 45):
        fh = h * f0; amp = np.zeros(nn)
        for k in range(4):
            amp += (1.0 / (1 + ((fh - fr[k]) / (bw[k] + 60)) ** 2)) * [1, 0.7, 0.35, 0.2][k]
        out += amp * (fh < 8000) / h ** 0.6 * np.sin(h * ph + rng.uniform(0, 2 * np.pi))
    out *= syl * (1 + 0.1 * np.sin(2 * np.pi * 5 * tt))
    nz = rng.normal(0, 1, nn); out += (nz - np.convolve(nz, np.ones(4) / 4, mode='same')) * fric * 2.0
    return (out / (np.max(np.abs(out)) + 1e-9) * 0.5).astype(np.float32)


def music(seconds, seed=2):
    rng = np.random.default_rng(seed); nn = int(seconds * SR); tt = np.arange(nn) / SR; out = np.zeros((2, nn))
    chords = [[220, 277.2, 329.6], [196, 246.9, 293.7], [174.6, 220, 261.6], [164.8, 207.7, 246.9]]
    for i in range(int(np.ceil(seconds / 2))):
        s, e = int(i * 2 * SR), min(nn, int((i + 1) * 2 * SR)); x = tt[s:e] - tt[s]
        env = np.minimum(1, x / 0.02) * np.exp(-x * 0.4)
        for j, f in enumerate(chords[i % 4]):
            for h in range(1, 12):
                pan = 0.5 + 0.3 * np.sin(j + h); tone = env * np.sin(2 * np.pi * f * h * x + h) / h
                out[0, s:e] += tone * pan; out[1, s:e] += tone * (1 - pan)
        out[:, s:e] += env * np.sign(np.sin(2 * np.pi * chords[i % 4][0] / 2 * x)) * 0.3
    for i in range(int(seconds / 0.5)):
        s = int(i * 0.5 * SR); d = min(int(0.25 * SR), nn - s); x = np.arange(d) / SR
        out[:, s:s + d] += np.sin(2 * np.pi * (50 + 120 * np.exp(-x * 30)) * x) * np.exp(-x * 12) * 1.5
        hs = s + int(0.25 * SR); hd = min(int(0.06 * SR), nn - hs)
        if hd > 0:
            z = rng.normal(0, 1, hd); out[:, hs:hs + hd] += (z - np.convolve(z, np.ones(3) / 3, mode='same')) * np.exp(-np.arange(hd) / SR * 60) * 0.6
        if i % 2:
            sd = min(int(0.15 * SR), nn - s); out[:, s:s + sd] += rng.normal(0, 1, sd) * np.exp(-np.arange(sd) / SR * 25) * 0.7
    return (out / (np.max(np.abs(out)) + 1e-9)).astype(np.float32)


def sdr(ref, est):
    ref = ref.astype(np.float64).ravel(); est = est.astype(np.float64).ravel()
    return 10 * np.log10(np.sum(ref ** 2) / (np.sum((ref - est) ** 2) + 1e-12))


def corr(a, b):
    a = a.ravel() - a.mean(); b = b.ravel() - b.mean()
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))


def mixture(seconds):
    v = speech(seconds); voice = np.stack([v, v]); m = music(seconds)
    m = m * np.sqrt(np.mean(voice ** 2) / np.mean(m ** 2))  # music as loud as the voice (0 dB)
    mix = voice + m; peak = np.max(np.abs(mix))
    return voice / peak * 0.9, mix / peak * 0.9


try:
    vi.ensure_model()
except vi.VoiceIsolationError as e:
    import requests
    try: requests.head('https://github.com', timeout=10); reachable = True
    except Exception: reachable = False
    if not reachable:
        print(f'SKIP test_voice_isolation: github.com is unreachable, so the model cannot be downloaded ({e})'); sys.exit(0)
    raise
check('model is present after first use (exact size, MD5 verified, no .partial left)',
      vi.model_path().stat().st_size == vi.MODEL['bytes'] and not list(vi.model_dir().glob('*.partial')))

# --- quality: SDR improvement over the mix on 10 s of voice + loud music
voice, mix = mixture(10)
t0 = time.time(); est = vi.separate(mix.astype(np.float32)); dt = time.time() - t0
mix_sdr, est_sdr = sdr(voice, mix), sdr(voice, est)
print(f'QUALITY voice SDR: mix {mix_sdr:.2f} dB -> isolated {est_sdr:.2f} dB (+{est_sdr - mix_sdr:.2f} dB); '
      f'correlation with clean voice: mix {corr(voice, mix):.3f} -> isolated {corr(voice, est):.3f}; '
      f'{dt:.1f} s for 10 s of audio ({dt / 10:.2f} s per second)', flush=True)
check('isolation improves voice SDR by at least 6 dB over the mix', est_sdr - mix_sdr >= 6)
check('isolated output correlates with the clean voice clearly better than the mix', corr(voice, est) > corr(voice, mix) + 0.1)
music_only = vi.separate((mix - voice).astype(np.float32))
check('music alone is suppressed by at least 20 dB', 10 * np.log10(np.sum(music_only ** 2) / np.sum((mix - voice) ** 2)) < -20)

# --- API
def write_wav(path, stereo, sr=SR):
    pcm = (np.clip(stereo.T, -1, 1) * 32767).astype('<i2')
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())

_, short_mix = mixture(4)
write_wav(t / 'dialogue.wav', short_mix)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=0x405060:s=320x180:d=4:r=30', '-i', str(t / 'dialogue.wav'),
                '-shortest', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(t / 'interview.mp4')], check=True, capture_output=True)
client = TestClient(app).__enter__()
st = client.get('/api/voice-isolation/status').json()
check('status reports folder, downloaded model and its size', st['folder'] == str(vi.model_dir()) and st['downloaded'] and st['bytes'] == vi.MODEL['bytes'] and st['url'].startswith('https://github.com/'))
p = client.post('/api/projects', json={'title': 'Voice iso', 'aspect': '16:9'}).json(); pid = p['id']
up = lambda f: client.post('/api/assets/upload', params={'project_id': pid}, files={'file': (f, open(t / f, 'rb'))}).json()
audio, video = up('dialogue.wav'), up('interview.mp4')
orig_bytes = client.get(f"/api/assets/{audio['id']}/stream").content

check('strength above 100 is rejected', client.post(f"/api/assets/{audio['id']}/isolate-voice", json={'strength': 101}).status_code == 422)
check('negative strength is rejected', client.post(f"/api/assets/{audio['id']}/isolate-voice", json={'strength': -1}).status_code == 422)
check('unknown asset is 404', client.post('/api/assets/nope/isolate-voice', json={}).status_code == 404)

r = client.post(f"/api/assets/{audio['id']}/isolate-voice", json={})
check('isolation starts as a background job', r.status_code == 200 and r.json()['status'] == 'running' and r.json()['job_id'])
job_id = r.json()['job_id']
for _ in range(600):
    j = client.get(f'/api/voice-isolation/jobs/{job_id}').json()
    if j['status'] != 'running':
        break
    time.sleep(0.5)
check('job finishes with progress 100 and a new asset', j['status'] == 'done' and j['progress'] == 100 and j['asset']['id'] != audio['id'])
iso = j['asset']
check('new asset is audio named "<orig> (voice isolated).wav"', iso['type'] == 'audio' and iso['original_filename'] == 'dialogue (voice isolated).wav' and iso['mime'] == 'audio/wav')
data = client.get(f"/api/assets/{iso['id']}/stream").content
with wave.open(io.BytesIO(data)) as w:
    fmt = (w.getframerate(), w.getnchannels(), w.getnframes())
    got = np.frombuffer(w.readframes(w.getnframes()), '<i2').reshape(-1, 2).T.astype(np.float32) / 32767
check('isolated WAV is 48 kHz stereo with the same length', fmt[0] == 48000 and fmt[1] == 2 and abs(fmt[2] / 48000 - 4) < 0.05)
check('original asset is untouched', client.get(f"/api/assets/{audio['id']}/stream").content == orig_bytes)
check('isolated asset has much less energy than the mix (music removed)', np.mean(got ** 2) < 0.75 * np.mean(short_mix ** 2))
r = client.post(f"/api/assets/{audio['id']}/isolate-voice", json={'strength': 100})
check('second request is a cache hit returning the same asset', r.json()['status'] == 'done' and r.json()['cached'] and r.json()['asset']['id'] == iso['id'])
r = client.post(f"/api/assets/{audio['id']}/isolate-voice", json={'strength': 0, 'wait': True})
check('different strength is a separate result (strength 0 keeps the original mix)', r.status_code == 200 and r.json()['asset']['id'] != iso['id'] and not r.json()['cached'])
r = client.post(f"/api/assets/{video['id']}/isolate-voice", json={'strength': 80, 'wait': True})
check('video input works (its sound is extracted) and yields an audio asset', r.status_code == 200 and r.json()['asset']['type'] == 'audio' and r.json()['asset']['original_filename'] == 'interview (voice isolated).wav' and abs(r.json()['asset']['duration_ms'] - 4000) < 150)
img = t / 'still.png'
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=red:s=64x64:d=1', '-frames:v', '1', str(img)], check=True)
check('images are rejected with a clear message', client.post(f"/api/assets/{up('still.png')['id']}/isolate-voice", json={}).status_code == 400)
check('no finished job is left running', not client.get('/api/voice-isolation/status').json()['running'])
print(f'{n} checks passed')
