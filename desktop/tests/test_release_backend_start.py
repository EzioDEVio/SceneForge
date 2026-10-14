"""The desktop backend entry point starts and announces itself the way Electron expects.

0.9.4-beta.3 to beta.9 crashed right here in every packaged build ("cannot access free variable
'json'"): a local import inside main() shadowed the module import used by the start-up
announcement. The packaged smoke test only runs in the Release workflow, so this runs the same
entry point from source in the regular checks."""
import json, os, pathlib, queue, secrets, subprocess, sys, tempfile, threading, time, unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class BackendStartTest(unittest.TestCase):
    def test_announces_ready_with_a_port_and_exits_when_the_parent_closes(self):
        with tempfile.TemporaryDirectory() as data:
            env = {**os.environ, 'SCENEFORGE_DESKTOP_TOKEN': secrets.token_hex(24), 'SCENEFORGE_DATA_DIR': data,
                   'PYTHONPATH': str(ROOT / 'backend')}
            proc = subprocess.Popen([sys.executable, str(ROOT / 'backend' / 'desktop_entry.py')], cwd=ROOT / 'backend', env=env,
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            out: queue.Queue = queue.Queue()
            threading.Thread(target=lambda: [out.put(l) for l in proc.stdout] + [out.put(None)], daemon=True).start()
            lines, ready, deadline = [], None, time.monotonic() + 90
            try:
                # Read on a thread: a backend that starts but never announces must fail, not hang.
                while ready is None and time.monotonic() < deadline:
                    try:
                        line = out.get(timeout=max(0.1, deadline - time.monotonic()))
                    except queue.Empty:
                        break
                    if line is None:
                        break
                    lines.append(line)
                    if line.startswith('SCENEFORGE_READY '):
                        ready = json.loads(line.split(' ', 1)[1])
                self.assertIsNotNone(ready, 'no SCENEFORGE_READY line; output:\n' + ''.join(lines))
                self.assertIsInstance(ready.get('port'), int)
                self.assertNotIn('Traceback', ''.join(lines))
                proc.stdin.close()          # Electron closing: the backend must shut down by itself
                self.assertEqual(proc.wait(timeout=30), 0)
            finally:
                if proc.poll() is None:
                    proc.kill()


if __name__ == '__main__':
    unittest.main()
