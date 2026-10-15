"""Security hardening from the CodeQL / Dependabot review (October 2026).

- safe_join keeps request-built paths inside their folder (path traversal);
- requests with ids that would leave the media folder are refused with 400, not written;
- the script parser's stage-direction patterns stay fast on hostile input (ReDoS);
- Voicebox requests only go to this computer (SSRF), also for an address saved earlier;
- the diagnostic espeak voice only accepts known voice names (argument injection);
- asset stream URLs encode the id.
No providers, no downloads."""
import os, pathlib, sys, tempfile, time

ROOT = pathlib.Path(__file__).resolve().parents[2]
work = tempfile.TemporaryDirectory(); os.environ['SCENEFORGE_DATA_DIR'] = work.name
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.security.paths import safe_join, UnsafePathError
from app.domain.import_parser import _strip_non_narration
from app.providers import voicebox, local_offline_tts
from app.render.ffmpeg_utils import FFmpegError
n = 0


def check(name, ok):
    global n
    assert ok, name; n += 1; print('PASS ' + name, flush=True)


def refused(fn):
    try:
        fn()
    except (UnsafePathError, voicebox.VoiceboxError, FFmpegError):
        return True
    return False


base = pathlib.Path(work.name) / 'media'
check('safe_join keeps ordinary names inside the folder', safe_join(base, 'p1', 'a.png') == base.resolve() / 'p1' / 'a.png'
      or str(safe_join(base, 'p1', 'a.png')).startswith(os.path.abspath(base)))
for bad in ('..', '../x', 'a/../../x', '/etc/passwd', 'C:\\Windows' if os.name == 'nt' else '/tmp', '', 'a\x00b'):
    check(f'safe_join refuses {bad!r}', refused(lambda: safe_join(base, bad, 'f.txt')))
check('safe_join refuses the folder itself', refused(lambda: safe_join(base, '.')))

with TestClient(app) as c:
    r = c.post('/api/projects/..%2F..%2Fescape/music-fit', json={})
    check('a project id that would leave the media folder is refused', r.status_code in (400, 404, 405))
    p = c.post('/api/projects', json={'title': 'Hardening', 'aspect': '16:9'}).json()
    r = c.post(f"/api/projects/{p['id']}/stickers/..%2F..%2Fsecret")
    check('an unknown sticker id is refused before any file is written', r.status_code in (400, 404, 405) and not list(pathlib.Path(work.name).rglob('secret*')))
    r = c.put('/api/local-speech/voicebox/address', json={'url': 'http://10.0.0.5:17493'})
    check('Voicebox on another machine is refused', r.status_code == 400 and 'this computer' in r.text)
    r = c.put('/api/local-speech/voicebox/address', json={'url': 'http://localhost:17493'})
    check('Voicebox on this computer is accepted', r.status_code == 200)

hostile = '(pause ' * 40000
t0 = time.monotonic(); _strip_non_narration(hostile); dt = time.monotonic() - t0
check(f'stage-direction stripping stays fast on 280k hostile characters ({dt:.3f}s; was ~5 s)', dt < 0.5)
check('stage directions are still removed', _strip_non_narration('Hi (pause 2s) there [music up] (beat) end') == 'Hi  there   end')

for url in ('http://192.168.1.4:17493', 'http://evil.example', 'http://127.0.0.1.evil.example:1', 'http://user:pw@127.0.0.1:1', 'file:///etc/passwd'):
    check(f'Voicebox requests refuse {url}', refused(lambda: voicebox._base(url)))
check('Voicebox default and loopback addresses are kept', voicebox._base(None) == voicebox.DEFAULT_URL and voicebox._base('http://localhost:9') == 'http://localhost:9'
      and voicebox._base('http://[::1]:17493') == 'http://[::1]:17493')
st = voicebox.status('http://192.168.1.4:17493')
check('a remote Voicebox address saved earlier shows a reason instead of failing', st['running'] is False and 'this computer' in st['reason'])

for vid in ('../health', 'a/b', 'x?y=1', 'a#b', '', 'é', 'a' * 129):
    check(f'a Voicebox voice id {vid[:12]!r} is refused before any request', refused(lambda: voicebox._profile_ref(vid)))
check('plain Voicebox voice ids are kept', voicebox._profile_ref('3f2b9c1e-7a4d-4e1b-9c2a-0d8e6f5a1b2c') == '3f2b9c1e-7a4d-4e1b-9c2a-0d8e6f5a1b2c')


class _EL:
    name, base_url, secret_ref, model = 'elevenlabs', '', '', None


from app.providers import speech_http
for vid in ('../../v1/user', 'a/b', 'x?y', 'a' * 65):
    try:
        speech_http.synthesize_with_alignment(_EL(), 'hi', vid, 'en', 1.0); ok = False
    except ValueError as e:
        ok = 'Select an ElevenLabs voice' in str(e)
    check(f'an ElevenLabs voice id {vid[:14]!r} is refused before any request', ok)

check('the diagnostic voice refuses unknown names (nothing from the request reaches the command line)',
      refused(lambda: local_offline_tts.synthesize('hello', str(pathlib.Path(work.name) / 'x.wav'), voice='--help')))

import re as _re, shutil, subprocess
main_cjs = (ROOT / 'desktop' / 'main.cjs').read_text(encoding='utf-8')
zip_fn = _re.search(r'const isDiagnosticsZip=.*', main_cjs).group(0)
check('the desktop app only saves the diagnostics report when it is a zip', 'isDiagnosticsZip(zip)' in main_cjs)
if shutil.which('node'):
    js = zip_fn + ("\nconst z=Buffer.concat([Buffer.from([0x50,0x4b,3,4]),Buffer.alloc(40)]);"
                   "console.log([isDiagnosticsZip(z),isDiagnosticsZip(Buffer.from('<html>error</html>')),"
                   "isDiagnosticsZip(Buffer.alloc(51*1024*1024)),isDiagnosticsZip(null)].join(','))")
    out = subprocess.run(['node', '-e', js], capture_output=True, text=True).stdout.strip()
    check(f'diagnostics zip check accepts a zip and refuses html, oversize and nothing ({out})', out == 'true,false,false,false')

api_ts = (ROOT / 'frontend' / 'src' / 'api.ts').read_text(encoding='utf-8')
check('asset stream URLs encode the id', 'assets/${encodeURIComponent(assetId)}/stream' in api_ts)
print(f'{n} security hardening checks passed')
