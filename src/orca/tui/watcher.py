"""File watcher with watchdog-preferred / polling-fallback behavior.

The TUI calls `Watcher(repo_root, on_change)` once at startup. The
watcher observes the directories that back the panes:

- `specs/` (feature artifacts that influence flow-state reviews)

On any change under those trees, `on_change(path)` is invoked on a
background thread. Debounce: `coalesce_window` seconds of successive
changes collapse into one callback call.

If the `watchdog` package cannot be imported, the watcher falls back to
a polling loop that calls `on_change(None)` every `poll_interval`
seconds, with `polling_mode` set to True.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable

OnChange = Callable[[Path | None], None]

logger = logging.getLogger(__name__)


class Watcher:
    """Filesystem watcher with graceful polling fallback."""

    def __init__(
        self,
        repo_root: Path,
        on_change: OnChange,
        *,
        poll_interval: float = 5.0,
        coalesce_window: float = 0.1,
        force_polling: bool = False,
    ) -> None:
        self.repo_root = repo_root
        self.on_change = on_change
        self.poll_interval = poll_interval
        self.coalesce_window = coalesce_window
        self.force_polling = force_polling
        self._stopped = False
        self._stop_event = threading.Event()
        self._debounce_lock = threading.Lock()
        self._last_fire = 0.0
        self._pending_timer: threading.Timer | None = None
        self._observer = None  # watchdog Observer, if available
        self._poll_thread: threading.Thread | None = None
        self._has_missing_targets = False

        if self.force_polling:
            watchdog_started = False
        else:
            watchdog_started = self._try_start_watchdog()

        # Polling mode is on whenever watchdog didn't attach to everything,
        # so newly-created watch roots still get picked up via the poll loop.
        self.polling_mode = (not watchdog_started) or self._has_missing_targets
        if self.polling_mode:
            self._start_polling()

    # --- watchdog path -----------------------------------------------------

    def _try_start_watchdog(self) -> bool:
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except Exception:  # noqa: BLE001 - any import failure => polling mode
            return False

        handler_parent = self

        class _Handler(FileSystemEventHandler):
            def on_any_event(self, event):  # type: ignore[override]
                if event.is_directory:
                    return
                handler_parent._schedule_fire(Path(event.src_path))

        # Watch the directories described in the module docstring.
        # Missing roots are created as needed so the observer can attach
        # without crashing; absent parent dirs degrade to polling.
        watch_targets = [
            self.repo_root / "specs",
        ]
        active_targets = [p for p in watch_targets if p.exists()]
        missing_targets = [p for p in watch_targets if not p.exists()]
        if not active_targets:
            # Nothing to watch yet - fall back to polling so the TUI
            # still reconciles when directories appear later.
            return False

        try:
            self._observer = Observer()
            handler = _Handler()
            for target in active_targets:
                self._observer.schedule(handler, str(target), recursive=True)
            self._observer.start()
            # Note whether any targets were absent so __init__ can keep the
            # polling loop alive as a reconciler for newly-created trees.
            self._has_missing_targets = bool(missing_targets)
            return True
        except Exception:  # noqa: BLE001
            logger.debug("Failed to start watchdog observer", exc_info=True)
            self._observer = None
            return False

    # --- polling fallback -------------------------------------------------

    def _start_polling(self) -> None:
        def _loop() -> None:
            while not self._stop_event.wait(self.poll_interval):
                try:
                    self.on_change(None)
                except Exception:  # noqa: BLE001 - never raise from the thread
                    logger.exception("Watcher polling callback failed")

        self._poll_thread = threading.Thread(target=_loop, daemon=True, name="tui-poll")
        self._poll_thread.start()

    # --- debounced fire --------------------------------------------------

    def _schedule_fire(self, changed: Path) -> None:
        with self._debounce_lock:
            if self._pending_timer is not None:
                self._pending_timer.cancel()
            self._pending_timer = threading.Timer(
                self.coalesce_window,
                self._fire,
                args=(changed,),
            )
            self._pending_timer.daemon = True
            self._pending_timer.start()

    def _fire(self, changed: Path) -> None:
        try:
            self.on_change(changed)
        except Exception:  # noqa: BLE001
            logger.exception("Watcher debounced callback failed for %s", changed)

    # --- lifecycle --------------------------------------------------------

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self._stop_event.set()
        if self._pending_timer is not None:
            try:
                self._pending_timer.cancel()
            except Exception:  # noqa: BLE001
                logger.debug("Failed to cancel pending debounce timer", exc_info=True)
            self._pending_timer = None
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=1.0)
            except Exception:  # noqa: BLE001
                logger.debug(
                    "Failed to stop/join watchdog observer cleanly", exc_info=True
                )
            self._observer = None
        if self._poll_thread is not None and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=1.0)
