"""A system proxy (Windows Internet Options, VPN, antivirus web shield) must not stop
SceneForge reaching voice engines on this computer. Owner report 2026-10-12: Chatterbox
container running, app said "Voice service unavailable"."""
import os, pathlib, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

root = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'backend'))
os.environ['SCENEFORGE_DATA_DIR'] = tempfile.mkdtemp(prefix='sf-proxy-')


class Voices(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
        self.wfile.write(b'{"voices":[{"id":"default"}]}')

    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length') or 0))
        self.send_response(200); self.send_header('Content-Type', 'audio/wav'); self.end_headers(); self.wfile.write(b'RIFFfake')

    def log_message(self, *a):
        pass


server = HTTPServer(('127.0.0.1', 0), Voices)
port = server.server_address[1]
threading.Thread(target=server.serve_forever, daemon=True).start()
for k in ('NO_PROXY', 'no_proxy'):
    os.environ.pop(k, None)
os.environ['HTTP_PROXY'] = os.environ['http_proxy'] = 'http://127.0.0.1:9'   # a dead system proxy

import requests
from app.providers import speech_http
try:
    requests.get(f'http://127.0.0.1:{port}/v1/audio/voices', timeout=3)
    print('NOTE plain requests reached the engine (proxy ignored on this platform)')
except requests.RequestException:
    print('PASS reproduced: plain requests to 127.0.0.1 fail through a system proxy')

profile = SimpleNamespace(name='chatterbox', base_url=f'http://127.0.0.1:{port}', secret_ref='', model='chatterbox')
assert speech_http.list_voices(profile) == ['default']
print('PASS voice list reaches the local engine despite the system proxy')
audio = speech_http.synthesize(profile, 'Hello there', 'default', 'en', 1.0)
assert audio == b'RIFFfake'
print('PASS speech generation reaches the local engine despite the system proxy')

down = SimpleNamespace(name='chatterbox', base_url='http://127.0.0.1:9', secret_ref='', model='chatterbox')
try:
    speech_http.list_voices(down)
    raise AssertionError('expected an error')
except ValueError as e:
    assert 'Nothing is answering at http://127.0.0.1:9' in str(e) and 'Start Chatterbox' in str(e), e
print('PASS a stopped engine is reported with its address and how to start it')

from app.api import local_speech
local_speech.ENGINES['chatterbox'] = (f'http://127.0.0.1:{port}', 'chatterbox')
status = local_speech.engine_status('chatterbox')
assert status['reachable'] is True, status
print('PASS engine status check also bypasses the system proxy')
server.shutdown()
print('4 local-engine proxy checks passed')
