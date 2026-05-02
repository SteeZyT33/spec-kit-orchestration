"""Watcher: polling fallback fires the callback at the configured interval."""
from __future__ import annotations

import threading
from pathlib import Path

from orca.tui.watcher import Watcher


def test_watcher_polling_fallback_fires_callback(tmp_path: Path):
    fired = threading.Event()
    def cb(_p):
        fired.set()
    w = Watcher(tmp_path, cb, poll_interval=0.1, force_polling=True)
    try:
        assert fired.wait(timeout=1.0), "watcher did not fire"
    finally:
        w.stop()
