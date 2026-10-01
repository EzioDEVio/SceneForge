"""In-memory ring buffer of recent backend log lines, for Help → Export diagnostics.

The desktop app also writes the backend's stdout/stderr to <data>/logs/desktop-backend.log;
this buffer covers browser/dev runs where nothing captures the process output.
"""
from __future__ import annotations

import collections
import logging
import threading

MAX_LINES = 2000
_lines: collections.deque[str] = collections.deque(maxlen=MAX_LINES)
_lock = threading.Lock()


class RingHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
        except Exception:  # noqa: BLE001 - logging must never raise
            return
        with _lock:
            _lines.append(line)


_handler = RingHandler()
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))


def install() -> None:
    """Attach to the root logger and to uvicorn's loggers (which do not propagate)."""
    import sys
    root = logging.getLogger()
    if not root.handlers:
        # Adding any handler disables Python's "last resort" stderr output for warnings;
        # keep that output (the desktop app captures stderr into desktop-backend.log).
        err = logging.StreamHandler(sys.stderr)
        err.setLevel(logging.WARNING)
        root.addHandler(err)
    # uvicorn.error propagates into "uvicorn"; "uvicorn" and "uvicorn.access" do not reach the root.
    for name in ("", "uvicorn", "uvicorn.access"):
        lg = logging.getLogger(name)
        if _handler not in lg.handlers:
            lg.addHandler(_handler)


def tail(n: int = 500) -> list[str]:
    with _lock:
        return list(_lines)[-n:]
