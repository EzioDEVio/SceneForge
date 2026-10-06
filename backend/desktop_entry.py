"""Frozen backend entrypoint. Bind an OS-selected loopback port; exit with the shell."""
import faulthandler, json, os, socket, sys, threading, time

# NumPy/OpenCV on Windows (OpenBLAS): loading them for the first time on a request worker
# thread can hang the whole backend. Limit the maths libraries to one thread and load them
# once, here, on the main thread before the server starts.
for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_var, "1")


def preload():
    for name in ("numpy", "PIL.Image", "cv2"):
        start = time.time()
        try:
            __import__(name)
            print(f"preloaded {name} in {time.time() - start:.2f}s", file=sys.stderr, flush=True)
        except Exception as e:  # OpenCV is only needed for photo tools; report and carry on
            print(f"could not preload {name}: {e}", file=sys.stderr, flush=True)


class HangWatch:
    """ASGI wrapper + watchdog thread: if any request runs longer than `limit` seconds,
    write every thread's stack to the log once for that request, so a hang is diagnosable."""
    def __init__(self, app, limit=20):
        self.app, self.limit, self.active, self.lock, self.n = app, limit, {}, threading.Lock(), 0
        threading.Thread(target=self._watch, daemon=True).start()

    async def __call__(self, scope, receive, send):
        path = scope.get("path") or ""
        # Event streams and media streams are long by design; dumping every thread's stack for
        # them filled the log (0.9.1: tens of thousands of lines from /api/jobs/<id>/events).
        if scope.get("type") != "http" or path.endswith("/events") or path.endswith("/stream") or "/preview-media" in path:
            return await self.app(scope, receive, send)
        with self.lock:
            self.n += 1; rid = self.n
            self.active[rid] = [f"{scope.get('method')} {scope.get('path')}", time.time(), False]
        try:
            return await self.app(scope, receive, send)
        finally:
            with self.lock:
                self.active.pop(rid, None)

    def _watch(self):
        while True:
            time.sleep(2)
            with self.lock:
                slow = [(rid, r) for rid, r in self.active.items() if not r[2] and time.time() - r[1] > self.limit]
                for _, r in slow:
                    r[2] = True
            for rid, (what, started, _) in slow:
                print(f"SCENEFORGE_HANG request #{rid} {what} has run {time.time() - started:.0f}s; all thread stacks follow", file=sys.stderr, flush=True)
                faulthandler.dump_traceback(file=sys.stderr, all_threads=True)


def main():
    if len(sys.argv)>1 and sys.argv[1]=='--install-local-ai':
        if len(sys.argv)!=5:raise SystemExit('Expected components, workspace and GPU flag.')
        os.environ['SCENEFORGE_DATA_DIR']=sys.argv[3]
        if getattr(sys,'frozen',False):
            from pathlib import Path
            os.environ['SCENEFORGE_RESOURCE_DIR']=str(Path(sys.executable).resolve().parents[1]/'app-resources')
        from app.db.database import init_db
        from app.managed_ai import install
        init_db()
        components=[v for v in sys.argv[2].split(',') if v]
        raise SystemExit(0 if install(components,sys.argv[4]=='1') else 1)
    if len(os.environ.get('SCENEFORGE_DESKTOP_TOKEN', '')) < 32:
        raise RuntimeError('Desktop backend requires a per-launch authentication token.')
    preload()
    import uvicorn
    from app.main import app
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 0)); sock.listen(128)
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(HangWatch(app), host='127.0.0.1', port=port, log_level='warning', access_log=False, loop='asyncio', http='h11', ws='none'))

    def announce():
        while not server.started and not server.should_exit: time.sleep(.05)
        if server.started: print('SCENEFORGE_READY ' + json.dumps({'port': port}), flush=True)

    def parent_closed():
        # Electron holds stdin open for the lifetime of its owned backend.
        sys.stdin.buffer.read(); server.should_exit = True
    threading.Thread(target=announce, daemon=True).start()
    threading.Thread(target=parent_closed, daemon=True).start()
    try: server.run(sockets=[sock])
    finally: sock.close()


if __name__ == '__main__':
    main()
