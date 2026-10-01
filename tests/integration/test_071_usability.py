"""0.7.1 usability pack, backend half: the AI model manager and Export diagnostics.

Model manager: GET /api/models lists Whisper, every cutout model and the voice isolation model
with size/downloaded/bundled/folder; DELETE removes a downloaded file and drops the in-memory
session; bundled models and models used by a running job are refused; POST .../download runs
the module's own ensure function in a background thread (mocked here: no network) and reports
progress through GET .../download.
Diagnostics: GET /api/diagnostics.zip holds the documented files, counts rows without content,
and never contains a planted provider API key, a planted environment SECRET, the desktop token
or a key-shaped string that reached the log, neither in the raw zip bytes nor in any
decompressed member.
"""
import io, json, logging, os, pathlib, sys, tempfile, threading, time, zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
tmp = tempfile.TemporaryDirectory()
T = pathlib.Path(tmp.name)
os.environ['SCENEFORGE_DATA_DIR'] = str(T / 'data')
os.environ['SCENEFORGE_SD_AUTOSTART'] = '0'
os.environ['SCENEFORGE_MODEL_DIR'] = str(T / 'models' / 'whisper')
os.environ['SCENEFORGE_CUTOUT_MODEL_DIR'] = str(T / 'models' / 'cutout')
os.environ['SCENEFORGE_VOICE_MODEL_DIR'] = str(T / 'models' / 'voice')
PLANTED_ENV_SECRET = 'planted-env-secret-4b1d9e77c2'
os.environ['SCENEFORGE_TEST_SECRET'] = PLANTED_ENV_SECRET
os.environ['ACME_API_KEY'] = 'planted-acme-api-key-0c9e1f'
sys.path.insert(0, str(ROOT / 'backend'))

from fastapi.testclient import TestClient  # noqa: E402
from app.security import secrets  # noqa: E402
from app.main import app  # noqa: E402
from app.render import cutout, voice_isolation as vi  # noqa: E402
from app.providers import transcribe  # noqa: E402
import app.config as config  # noqa: E402

# Set after the app is imported so the desktop session middleware stays off for the client,
# while the diagnostics scrubber still sees the token in the environment.
DESKTOP_TOKEN = 'desktop-session-token-91aa0c7e5d3b'
os.environ['SCENEFORGE_DESKTOP_TOKEN'] = DESKTOP_TOKEN


class MemoryVault:
    """Stands in for the OS credential store (the real one is covered by test_credentials.py)."""
    def __init__(self): self.d = {}
    def set_password(self, s, k, v): self.d[(s, k)] = v
    def get_password(self, s, k): return self.d.get((s, k))
    def delete_password(self, s, k): self.d.pop((s, k), None)


_vault = MemoryVault()
secrets.vault = lambda: _vault

n = 0
def check(name, ok):
    global n
    assert ok, name
    n += 1
    print('PASS ' + name, flush=True)


def fake_model(path: pathlib.Path, size: int = 1_500_000):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'wb') as fh:
        fh.write(b'\0' * size)


with TestClient(app) as c:
    # ------------------------------------------------------------------ model listing
    r = c.get('/api/models')
    check('GET /api/models answers', r.status_code == 200)
    listing = r.json()
    kinds = {(m['kind'], m['id']) for m in listing['models']}
    check('the listing covers Whisper, every cutout model and the voice isolation model',
          ('whisper', transcribe.WHISPER_MODEL) in kinds and all(('cutout', k) in kinds for k in cutout.MODELS) and ('voice', 'kim_vocal_2') in kinds)
    check('every model reports name, purpose, size, downloaded, bundled and folder',
          all({'name', 'purpose', 'bytes', 'downloaded', 'bundled', 'folder', 'approx_mb'} <= set(m) for m in listing['models']))
    check('nothing is downloaded in a fresh model folder', not any(m['downloaded'] for m in listing['models']) and listing['total_bytes'] == 0)
    check('model folders follow the environment overrides',
          {m['folder'] for m in listing['models']} == {os.environ['SCENEFORGE_MODEL_DIR'], os.environ['SCENEFORGE_CUTOUT_MODEL_DIR'], os.environ['SCENEFORGE_VOICE_MODEL_DIR']})

    # ------------------------------------------------------------------ delete a downloaded cutout model
    human = cutout.model_dir() / cutout.MODELS['human']['file']
    fake_model(human)
    cutout._sessions[str(human)] = object()      # as if a cutout had loaded it
    m = next(x for x in c.get('/api/models').json()['models'] if x['id'] == 'human')
    check('a downloaded cutout model shows as downloaded with its size on disk', m['downloaded'] and m['bytes'] == 1_500_000 and not m['bundled'])
    check('total disk use counts it', c.get('/api/models').json()['total_bytes'] == 1_500_000)
    r = c.delete('/api/models/cutout/human')
    check('DELETE removes the downloaded file', r.status_code == 200 and r.json()['removed'] and r.json()['freed_bytes'] == 1_500_000 and not human.exists())
    check('deleting drops the in-memory cutout session', str(human) not in cutout._sessions)
    check('deleting a model that is not downloaded is a harmless no-op', c.delete('/api/models/cutout/human').json()['removed'] is False)
    check('unknown models are 404', c.delete('/api/models/cutout/nope').status_code == 404 and c.delete('/api/models/foo/bar').status_code == 404)

    # ------------------------------------------------------------------ bundled models are refused
    res = T / 'resources'
    bundled = res / 'models' / 'cutout' / cutout.MODELS['u2netp']['file']
    fake_model(bundled)
    old_res = config.RESOURCE_DIR
    config.RESOURCE_DIR = res
    try:
        m = next(x for x in c.get('/api/models').json()['models'] if x['id'] == 'u2netp')
        check('a model shipped with the installer is reported as bundled', m['bundled'] and m['downloaded'] and m['folder'] == str(bundled.parent))
        r = c.delete('/api/models/cutout/u2netp')
        check('deleting a bundled model is refused and the file stays', r.status_code == 409 and 'bundled' in r.json()['detail'] and bundled.exists())
        check('bundled models are not counted as removable downloads', c.get('/api/models').json()['downloaded_bytes'] == 0)
    finally:
        config.RESOURCE_DIR = old_res

    # ------------------------------------------------------------------ in use by a running job is refused
    fake_model(vi.model_path(), vi.MODEL['bytes'])
    check('the voice isolation model shows as downloaded', next(x for x in c.get('/api/models').json()['models'] if x['kind'] == 'voice')['downloaded'])
    from app.api import voice_isolation as api_vi
    api_vi._jobs['busy-job'] = {'status': 'running', 'progress': 10, 'stage': 'isolating', 'asset_id': 'x'}
    r = c.delete('/api/models/voice/kim_vocal_2')
    check('deleting a model while a voice isolation job runs is refused', r.status_code == 409 and vi.model_path().exists())
    api_vi._jobs.pop('busy-job')
    vi._sessions[str(vi.model_path())] = object()
    r = c.delete('/api/models/voice/kim_vocal_2')
    check('after the job, the voice model deletes and its session is dropped', r.status_code == 200 and not vi.model_path().exists() and str(vi.model_path()) not in vi._sessions)

    # ------------------------------------------------------------------ whisper delete resets the cache
    wdir = transcribe.model_dir() / 'models--Systran--faster-whisper-base' / 'snapshots' / 'x'
    fake_model(wdir / 'model.bin', 2_000_000)
    transcribe._LOCAL_MODEL = object()
    m = next(x for x in c.get('/api/models').json()['models'] if x['kind'] == 'whisper')
    check('a downloaded Whisper model shows its folder size', m['downloaded'] and m['bytes'] >= 2_000_000)
    transcribe._ACTIVE_RUNS += 1      # as if captions were being transcribed right now
    r = c.delete(f'/api/models/whisper/{transcribe.WHISPER_MODEL}')
    check('deleting Whisper while local captions run is refused', r.status_code == 409 and transcribe.model_dir().exists())
    transcribe._ACTIVE_RUNS -= 1
    r = c.delete(f'/api/models/whisper/{transcribe.WHISPER_MODEL}')
    check('deleting Whisper removes the folder and the loaded model', r.status_code == 200 and not transcribe.model_dir().exists() and transcribe._LOCAL_MODEL is None)

    # ------------------------------------------------------------------ download in the background (mocked, no network)
    gate = threading.Event()
    real_ensure = cutout.ensure_model
    def fake_ensure(model):
        cutout._progress[model] = {'done': 400_000, 'total': 1_000_000}
        gate.wait(10)
        fake_model(cutout.model_dir() / cutout.MODELS[model]['file'])
        cutout._progress.pop(model, None)
        return cutout.model_dir() / cutout.MODELS[model]['file']
    cutout.ensure_model = fake_ensure
    try:
        r = c.post('/api/models/cutout/isnet/download')
        check('POST download starts a background download', r.status_code == 200 and r.json()['status'] == 'running')
        time.sleep(0.2)
        st = c.get('/api/models/cutout/isnet/download').json()
        check('download progress is reported from the module progress', st['status'] == 'running' and st['done'] == 400_000 and st['total'] == 1_000_000)
        check('a model being downloaded cannot be deleted', c.delete('/api/models/cutout/isnet').status_code == 409)
        check('a second POST while downloading does not start another', c.post('/api/models/cutout/isnet/download').json()['status'] == 'running')
        gate.set()
        for _ in range(50):
            st = c.get('/api/models/cutout/isnet/download').json()
            if st['status'] != 'running':
                break
            time.sleep(0.1)
        check('the download finishes and the model shows as downloaded', st['status'] == 'done' and st['downloaded'])
        check('POST download of a downloaded model reports done', c.post('/api/models/cutout/isnet/download').json()['status'] == 'done')
    finally:
        cutout.ensure_model = real_ensure
    def failing_ensure():
        raise vi.VoiceIsolationError('Could not download (test)')
    real_vi = vi.ensure_model
    vi.ensure_model = failing_ensure
    try:
        c.post('/api/models/voice/kim_vocal_2/download')
        for _ in range(50):
            st = c.get('/api/models/voice/kim_vocal_2/download').json()
            if st['status'] != 'running':
                break
            time.sleep(0.05)
        check('a failed download reports its error', st['status'] == 'error' and 'test' in st['error'])
    finally:
        vi.ensure_model = real_vi

    # ------------------------------------------------------------------ diagnostics zip
    PLANTED_KEY = 'fixture-provider-key-7f3a9c51e2'
    r = c.post('/api/providers', json={'capability': 'image', 'name': 'openai', 'api_key': PLANTED_KEY, 'model': 'gpt-image-1'})
    check('a provider with a planted API key is saved', r.status_code == 200, )
    from app.db.database import SessionLocal
    from app.db.models import ProviderProfile
    with SessionLocal() as db:
        ref = db.query(ProviderProfile).filter_by(name='openai').first().secret_ref
    check('the planted key lives in the credential store, not the database', ref.startswith('keyring:') and _vault.d)
    SHAPED = 'sk-' + 'Q' * 40
    logging.getLogger('app.test').warning('a careless log line with %s and %s and %s', PLANTED_KEY, SHAPED, PLANTED_ENV_SECRET)
    (config.LOGS_DIR / 'desktop-backend.log').write_text(f'started\nheader token {DESKTOP_TOKEN}\nkey {PLANTED_KEY}\nready\n')
    p = c.post('/api/projects', json={'title': 'Diagnostics project', 'aspect': '16:9'})
    check('a project exists for row counts', p.status_code in (200, 201))

    r = c.get('/api/diagnostics.zip')
    check('GET /api/diagnostics.zip answers with a zip attachment',
          r.status_code == 200 and r.headers['content-type'] == 'application/zip' and 'attachment' in r.headers['content-disposition'])
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(z.namelist())
    expected = {'README.txt', 'system.json', 'settings.json', 'models.json', 'whisper_check.json', 'database.json', 'jobs.json', 'logs/backend-recent.log', 'logs/desktop-backend.log'}
    check('the zip holds every documented file', expected <= names)
    system = json.loads(z.read('system.json'))
    from app.main import BUILD_ID
    check('system.json has build, OS, Python and FFmpeg versions',
          system['build'] == BUILD_ID and system['platform'] and system['python'].startswith('3.') and 'ffmpeg' in system['ffmpeg'].lower())
    check('system.json includes the hardware probe result', isinstance(system.get('hardware'), dict) and 'detected' in system['hardware'])
    counts = json.loads(z.read('database.json'))
    check('database.json has row counts only', counts.get('projects') == 1 and all(isinstance(v, int) for v in counts.values()))
    check('the database counts contain no project content', b'Diagnostics project' not in r.content and all(b'Diagnostics project' not in z.read(nm) for nm in names))
    check('jobs.json is a list of job outcomes', isinstance(json.loads(z.read('jobs.json')), list))
    models = json.loads(z.read('models.json'))
    check('models.json is the model manager listing', {m['kind'] for m in models['models']} == {'whisper', 'cutout', 'voice'})
    check('whisper_check.json is the Whisper self-check', 'checks' in json.loads(z.read('whisper_check.json')))
    settings = json.loads(z.read('settings.json'))
    prov = settings['providers'][0]
    check('providers appear only as name/capability/model/configured', prov['name'] == 'openai' and prov['configured'] is True and 'secret_ref' not in prov and 'api_key' not in prov)
    check('secret-looking environment variables are left out', not any(k in settings['environment'] for k in ('SCENEFORGE_TEST_SECRET', 'ACME_API_KEY', 'SCENEFORGE_DESKTOP_TOKEN'))
          and 'SCENEFORGE_DATA_DIR' in settings['environment'])
    check('README explains the contents', b'database.json' in z.read('README.txt') and b'no API keys' in z.read('README.txt'))
    check('the planted log line reached the zip, redacted', b'careless log line' in z.read('logs/backend-recent.log'))
    planted = [PLANTED_KEY, PLANTED_ENV_SECRET, 'planted-acme-api-key-0c9e1f', DESKTOP_TOKEN, SHAPED, ref, ref[8:]]
    raw = r.content
    check('no planted secret appears in the raw zip bytes', not any(s.encode() in raw for s in planted))
    leaked = [(nm, s) for nm in names for s in planted if s.encode() in z.read(nm)]
    check('no planted secret appears in any decompressed file (API key, env SECRET, desktop token, key-shaped log text, keyring ref)', not leaked)
    check('the desktop log tail is included with the token redacted', b'[redacted]' in z.read('logs/desktop-backend.log') and b'ready' in z.read('logs/desktop-backend.log'))

print(f'{n} 0.7.1 usability checks passed (model manager and diagnostics).')
