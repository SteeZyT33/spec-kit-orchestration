"""Filesystem watcher with watchdog-preferred / polling fallback.

Watches .orca/worktrees/. On change, calls on_change(path) on a background
thread, debounced by coalesce_window seconds.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

OnChange = Callable[[Path | None], None]
logger = logging.getLogger(__name__)


class Watcher:
    def __init__(
        self,
        repo_root: Path,
        on_change: OnChange,
        *,
        poll_interval: float = 5.0,
        coalesce_window: float = 0.5,
        force_polling: bool = False,
    ) -> None:
        self.repo_root = repo_root
        self.on_change = on_change
        self.poll_interval = poll_interval
        self.coalesce_window = coalesce_window
        self._stop_event = threading.Event()
        self._debounce_lock = threading.Lock()
        self._pending_timer: threading.Timer | None = None
        self._observer = None
        self._poll_thread: threading.Thread | None = None

        watchdog_started = False if force_polling else self._try_start_watchdog()
        if not watchdog_started:
            self._start_polling()

    def _try_start_watchdog(self) -> bool:
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except Exception:
            return False
        targets = [self.repo_root / ".orca" / "worktrees"]
        active = [p for p in targets if p.exists()]
        if not active:
            return False
        parent = self
        class _H(FileSystemEventHandler):
            def on_any_event(self, event):  # type: ignore[override]
                if event.is_directory:
                    return
                parent._schedule(Path(event.src_path))
        try:
            self._observer = Observer()
            handler = _H()
            for t in active:
                self._observer.schedule(handler, str(t), recursive=True)
            self._observer.start()
            return True
        except Exception:
            self._observer = None
            return False

    def _start_polling(self) -> None:
        def loop() -> None:
            while not self._stop_event.wait(self.poll_interval):
                try:
                    self.on_change(None)
                except Exception:
                    logger.exception("watcher polling cb failed")
        self._poll_thread = threading.Thread(target=loop, daemon=True,
                                              name="tui-poll")
        self._poll_thread.start()

    def _schedule(self, p: Path) -> None:
        with self._debounce_lock:
            if self._pending_timer is not None:
                self._pending_timer.cancel()
            self._pending_timer = threading.Timer(
                self.coalesce_window, self._fire, args=(p,),
            )
            self._pending_timer.daemon = True
            self._pending_timer.start()

    def _fire(self, p: Path) -> None:
        try:
            self.on_change(p)
        except Exception:
            logger.exception("watcher fire cb failed")

    def stop(self) -> None:
        self._stop_event.set()
        if self._pending_timer is not None:
            try:
                self._pending_timer.cancel()
            except Exception:
                pass
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=1.0)
            except Exception:
                pass
        if self._poll_thread is not None and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=1.0)
