"""ORCA banner animation — the orca rising from waves.

Runs at the start of `orca` installer output and the Kanban TUI.
Three phases, ~1.8s total:

  1. Waves-only shift (orca still underwater).
  2. Body rises bottom-up (belly → forehead → head+tail).
  3. Blowhole erupts water spout upward.

Stdlib-only (no rich/blessed/curses) so the installer footprint stays zero.
Graceful degradation: non-TTY, ``CI`` env var, or ``--static`` flag falls
back to a plain static print without delay.

Usage::

    python -m orca.banner_anim              # auto-detect
    python -m orca.banner_anim --animate    # force animation
    python -m orca.banner_anim --static     # force static

Exits 0 on success; 0 on Ctrl-C (terminal restored cleanly).
"""
from __future__ import annotations

import os
import signal
import sys
import time
from typing import Any, Callable

# Final frame — source of truth. Matches the canonical README banner
# exactly. Spout dot, quote-colon, and head-blowhole all align at col 8.
FINAL_ART: tuple[str, ...] = (
    "       .",
    "      \":\"",
    "    ___:____     |\"\\/\"|",
    "  ,'        `.    \\  /",
    "  |  O        \\___/  |",
    "~^~^~^~^~^~^~^~^~^~^~^~",
)

# Body lines in DISPLAY order (top of final frame → just above waves).
# The orca emerges bottom-up: the belly breaks the surface first, then
# the forehead, then the blowhole+tail region. During Phase 2 we reveal
# these from the END of the tuple (deepest part first) and grow the
# visible slice upward as more of the orca surfaces.
BODY_DISPLAY: tuple[str, ...] = (
    "    ___:____     |\"\\/\"|",  # blowhole + tail — top of head (emerges last)
    "  ,'        `.    \\  /",   # forehead — middle
    "  |  O        \\___/  |",    # belly + eye — just above waves (emerges first)
)

# Backwards-compat alias: older tests referenced BODY_BOTTOM_UP by name.
BODY_BOTTOM_UP = BODY_DISPLAY

# ANSI codes
CYAN = "\033[0;36m"
DIM_CYAN = "\033[2;36m"
BOLD = "\033[1m"
RST = "\033[0m"
HOME = "\033[H"
CLEAR = "\033[2J"
CLEAR_EOL = "\033[K"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"

WAVE_WIDTH = 23  # matches `~^~^~^~^~^~^~^~^~^~^~^~`
FRAME_ROWS = 7   # fixed banner height for consistent rendering


def wave_line(phase: int) -> str:
    """Wave line that visually shifts with phase.

    Pattern cycles ``~^~^`` every 4 steps. Keeping this deterministic
    makes the animation testable without timing games.
    """
    chars = []
    for i in range(WAVE_WIDTH):
        pos = (i + phase) % 4
        chars.append("~" if pos in (0, 2) else "^")
    return "".join(chars)


def _write_frame(lines: list[str], writer: Callable[[str], Any]) -> None:
    """Render one frame. Uses HOME + CLEAR_EOL so we don't flicker."""
    # Top-pad to fixed height so the banner stays anchored
    padded: list[str] = list(lines)
    while len(padded) < FRAME_ROWS:
        padded.insert(0, "")
    buf = [HOME]
    for line in padded:
        buf.append(line + CLEAR_EOL + "\n")
    writer("".join(buf))


def _safe_flush() -> None:
    """Flush stdout, ignoring errors (broken pipe, closed stream)."""
    try:
        sys.stdout.flush()
    except Exception:
        pass


def animate(
    writer: Callable[[str], Any] | None = None,
    sleeper: Callable[[float], Any] | None = None,
) -> None:
    """Play the full animation. ``writer`` and ``sleeper`` are injectable for tests."""
    _writer: Callable[[str], Any] = writer if writer is not None else sys.stdout.write
    _sleeper: Callable[[float], Any] = sleeper if sleeper is not None else time.sleep

    # Ctrl-C handler: restore cursor before exit
    def _restore(*_a: object) -> None:
        _writer(SHOW_CURSOR)
        _safe_flush()
        raise SystemExit(0)

    prev_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _restore)  # type: ignore[arg-type]

    try:
        # Initial clear only (subsequent frames use HOME)
        _writer(HIDE_CURSOR + CLEAR + HOME)
        _safe_flush()

        # Phase 1 (8 frames @ 80ms = 640ms): waves shift, orca submerged
        for frame in range(8):
            _write_frame([f"{DIM_CYAN}{wave_line(frame)}{RST}"], _writer)
            _safe_flush()
            _sleeper(0.08)

        # Phase 2 (4 frames @ 120ms = 480ms): body rises bottom-up.
        # Reveal from the END of BODY_DISPLAY so the deepest body part
        # (belly) appears first just above the waves, and subsequent
        # frames grow the visible slice UPWARD toward the blowhole.
        for reveal in range(4):
            lines: list[str] = []
            start = len(BODY_DISPLAY) - reveal
            for i, body_line in enumerate(BODY_DISPLAY):
                if i >= start:
                    lines.append(f"{BOLD}{CYAN}{body_line}{RST}")
            lines.append(f"{DIM_CYAN}{wave_line(8 + reveal)}{RST}")
            _write_frame(lines, _writer)
            _safe_flush()
            _sleeper(0.12)

        # Phase 3 (3 frames @ 150ms = 450ms): blowhole spout erupts.
        # Body is fully above water; BODY_DISPLAY iterated normally gives
        # the correct top-to-bottom visual order (blowhole → forehead → belly).
        spout_progression: list[list[str]] = [
            [],  # blowhole pressurizing
            [f"{CYAN}      \":\"{RST}"],  # first droplet
            [
                f"{CYAN}       .{RST}",
                f"{CYAN}      \":\"{RST}",
            ],  # full spout
        ]
        for spout in spout_progression:
            lines = list(spout)
            for body_line in BODY_DISPLAY:
                lines.append(f"{BOLD}{CYAN}{body_line}{RST}")
            lines.append(f"{DIM_CYAN}{wave_line(12)}{RST}")
            _write_frame(lines, _writer)
            _safe_flush()
            _sleeper(0.15)

        # Hold final frame
        _sleeper(0.30)
        _writer("\n")
    finally:
        _writer(SHOW_CURSOR)
        _safe_flush()
        signal.signal(signal.SIGINT, prev_sigint)  # type: ignore[arg-type]


def static(writer: Callable[[str], Any] | None = None) -> None:
    """Non-animated render — for non-TTY, CI, --static, or missing terminal capability."""
    _writer: Callable[[str], Any] = writer if writer is not None else sys.stdout.write
    for line in FINAL_ART:
        _writer(line + "\n")


def should_animate(argv: list[str] | None = None) -> bool:
    """Decide whether to animate based on env, argv, and TTY status."""
    if argv is None:
        argv = sys.argv[1:]
    if "--static" in argv:
        return False
    if "--animate" in argv:
        return True
    if os.environ.get("CI"):
        return False
    if os.environ.get("SPECKIT_ORCA_NO_ANIM"):
        return False
    return sys.stdout.isatty()


def main(argv: list[str] | None = None) -> int:
    if should_animate(argv):
        animate()
    else:
        static()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
