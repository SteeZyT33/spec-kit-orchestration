"""Tests for the ORCA banner animation module."""
from __future__ import annotations

from orca import banner_anim


class FakeTTY:
    def __init__(self, is_tty: bool) -> None:
        self._is_tty = is_tty
        self.buffer: list[str] = []

    def isatty(self) -> bool:
        return self._is_tty

    def write(self, s: str) -> int:  # noqa: D401
        self.buffer.append(s)
        return len(s)

    def flush(self) -> None:
        pass


def test_final_art_matches_readme_shape():
    """Sanity: final frame has 6 lines with expected art characters."""
    assert len(banner_anim.FINAL_ART) == 6
    assert banner_anim.FINAL_ART[0].strip() == "."
    # Blowhole line contains the colon
    assert "___:____" in banner_anim.FINAL_ART[2]
    # Wave line is all ~ and ^ plus spaces
    assert set(banner_anim.FINAL_ART[5].replace(" ", "")) <= {"~", "^"}


def test_body_display_is_top_to_bottom_visual_order():
    """BODY_DISPLAY must match the final frame's top-to-bottom layout.

    Blowhole+tail sits at the top of the head (index 0), belly+eye sits
    just above the waves (index 2). Matches FINAL_ART rows 2..4.
    """
    assert "___:____" in banner_anim.BODY_DISPLAY[0]   # top of head
    assert "," in banner_anim.BODY_DISPLAY[1]          # forehead (comma on quote line)
    assert "O" in banner_anim.BODY_DISPLAY[2]          # belly+eye just above waves


def test_body_display_matches_final_art_region():
    """The three BODY_DISPLAY rows equal FINAL_ART rows 2..4."""
    assert banner_anim.BODY_DISPLAY == banner_anim.FINAL_ART[2:5]


def test_body_bottom_up_alias_points_to_display():
    """Backwards-compat alias: BODY_BOTTOM_UP is BODY_DISPLAY."""
    assert banner_anim.BODY_BOTTOM_UP is banner_anim.BODY_DISPLAY


def test_wave_line_width():
    """Every wave line is exactly WAVE_WIDTH characters."""
    for phase in range(0, 20):
        assert len(banner_anim.wave_line(phase)) == banner_anim.WAVE_WIDTH


def test_wave_line_only_uses_wave_chars():
    """Wave line contains only ~ and ^."""
    for phase in range(0, 10):
        assert set(banner_anim.wave_line(phase)) <= {"~", "^"}


def test_wave_line_shifts_with_phase():
    """Phase change produces a different (or at least cyclically different) line."""
    # Phase 0 and phase 4 should be identical (period 4 cycle)
    assert banner_anim.wave_line(0) == banner_anim.wave_line(4)
    # Phase 0 and phase 1 should differ
    assert banner_anim.wave_line(0) != banner_anim.wave_line(1)


def test_static_writes_all_art_lines():
    """static() emits every FINAL_ART line verbatim, one per line."""
    fake = FakeTTY(is_tty=False)
    banner_anim.static(writer=fake.write)
    output = "".join(fake.buffer)
    for art_line in banner_anim.FINAL_ART:
        assert art_line in output
    # Lines terminated with newline
    assert output.count("\n") == len(banner_anim.FINAL_ART)


def test_final_art_matches_readme_canonical():
    """FINAL_ART must byte-for-byte match the README banner.

    README art is the single source of truth; any change here should be
    a deliberate README update. Pins the shape so future refactors can't
    silently drift the alignment.
    """
    expected = (
        "       .",
        "      \":\"",
        "    ___:____     |\"\\/\"|",
        "  ,'        `.    \\  /",
        "  |  O        \\___/  |",
        "~^~^~^~^~^~^~^~^~^~^~^~",
    )
    assert banner_anim.FINAL_ART == expected


def test_static_produces_no_leading_space():
    """The first line of static output starts at col 1 (no extra indent)."""
    fake = FakeTTY(is_tty=False)
    banner_anim.static(writer=fake.write)
    output = "".join(fake.buffer)
    lines = output.split("\n")
    # First line is FINAL_ART[0] which starts with 7 spaces then "."
    # Should NOT have additional leading space from the writer itself.
    assert lines[0] == banner_anim.FINAL_ART[0]


def test_static_emits_no_ansi_codes():
    """static() output is plain text — no color escapes."""
    fake = FakeTTY(is_tty=False)
    banner_anim.static(writer=fake.write)
    output = "".join(fake.buffer)
    assert "\033[" not in output


def test_should_animate_static_flag_wins(monkeypatch):
    """--static always disables animation even in a TTY."""
    monkeypatch.setattr(banner_anim.sys.stdout, "isatty", lambda: True)
    monkeypatch.delenv("CI", raising=False)
    assert banner_anim.should_animate(["--static"]) is False


def test_should_animate_animate_flag_wins_over_non_tty(monkeypatch):
    """--animate overrides non-TTY detection (useful for debugging)."""
    monkeypatch.setattr(banner_anim.sys.stdout, "isatty", lambda: False)
    monkeypatch.delenv("CI", raising=False)
    assert banner_anim.should_animate(["--animate"]) is True


def test_should_animate_ci_disables(monkeypatch):
    """CI env var forces static rendering."""
    monkeypatch.setattr(banner_anim.sys.stdout, "isatty", lambda: True)
    monkeypatch.setenv("CI", "1")
    assert banner_anim.should_animate([]) is False


def test_should_animate_speckit_opt_out(monkeypatch):
    """SPECKIT_ORCA_NO_ANIM opts out even in interactive terminals."""
    monkeypatch.setattr(banner_anim.sys.stdout, "isatty", lambda: True)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("SPECKIT_ORCA_NO_ANIM", "1")
    assert banner_anim.should_animate([]) is False


def test_should_animate_non_tty_default(monkeypatch):
    """Non-TTY default is static."""
    monkeypatch.setattr(banner_anim.sys.stdout, "isatty", lambda: False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("SPECKIT_ORCA_NO_ANIM", raising=False)
    assert banner_anim.should_animate([]) is False


def test_should_animate_tty_default(monkeypatch):
    """Interactive TTY default is animate."""
    monkeypatch.setattr(banner_anim.sys.stdout, "isatty", lambda: True)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("SPECKIT_ORCA_NO_ANIM", raising=False)
    assert banner_anim.should_animate([]) is True


def test_animate_runs_expected_frame_count():
    """animate() writes one frame per phase step plus initial setup."""
    fake = FakeTTY(is_tty=True)
    sleep_calls: list[float] = []
    banner_anim.animate(writer=fake.write, sleeper=sleep_calls.append)

    # Sleep count: 8 (phase 1) + 4 (phase 2) + 3 (phase 3) + 1 hold = 16
    assert len(sleep_calls) == 16

    # All frames together should include every body line at least once
    full_output = "".join(fake.buffer)
    for body_line in banner_anim.BODY_DISPLAY:
        assert body_line in full_output


def test_final_frame_stacks_body_right_side_up():
    """The last frame written before the hold must show body top-to-bottom.

    Regression: earlier version inverted the body because the 'emergence
    order' tuple was iterated without reversing for display.
    """
    fake = FakeTTY(is_tty=True)
    banner_anim.animate(writer=fake.write, sleeper=lambda _: None)

    # Find the final rendered frame (last HOME-prefixed chunk before SHOW_CURSOR)
    output = "".join(fake.buffer)
    # The final animated frame has spout + all 3 body lines + waves
    final_frame_start = output.rfind(banner_anim.HOME)
    final_frame = output[final_frame_start:]

    # Body lines should appear in display order (top→bottom)
    blowhole_idx = final_frame.find(banner_anim.BODY_DISPLAY[0])
    forehead_idx = final_frame.find(banner_anim.BODY_DISPLAY[1])
    belly_idx = final_frame.find(banner_anim.BODY_DISPLAY[2])

    assert blowhole_idx != -1 and forehead_idx != -1 and belly_idx != -1
    assert blowhole_idx < forehead_idx < belly_idx, (
        "Body must render top-to-bottom: blowhole → forehead → belly"
    )


def test_animate_restores_cursor_on_exit():
    """SHOW_CURSOR must appear in output so the terminal is left clean."""
    fake = FakeTTY(is_tty=True)
    banner_anim.animate(writer=fake.write, sleeper=lambda _: None)
    full_output = "".join(fake.buffer)
    assert banner_anim.SHOW_CURSOR in full_output
    assert banner_anim.HIDE_CURSOR in full_output


def test_main_static_path(monkeypatch):
    """main() with --static produces static output only."""
    monkeypatch.setattr(banner_anim.sys.stdout, "isatty", lambda: True)
    monkeypatch.delenv("CI", raising=False)
    captured: list[str] = []
    monkeypatch.setattr(banner_anim.sys.stdout, "write", captured.append)
    result = banner_anim.main(["--static"])
    assert result == 0
    output = "".join(captured)
    for art_line in banner_anim.FINAL_ART:
        assert art_line in output


def test_main_returns_zero(monkeypatch):
    """main() always returns 0 on the happy path."""
    monkeypatch.setattr(banner_anim.sys.stdout, "isatty", lambda: False)
    monkeypatch.delenv("CI", raising=False)
    captured: list[str] = []
    monkeypatch.setattr(banner_anim.sys.stdout, "write", captured.append)
    assert banner_anim.main([]) == 0
