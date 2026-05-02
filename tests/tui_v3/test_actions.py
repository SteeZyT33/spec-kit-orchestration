"""Mutation actions: subprocess shells out to orca-cli."""
from __future__ import annotations

from pathlib import Path

from orca.tui.actions import close_lane, doctor


def test_close_lane_calls_orca_cli_wt_rm(tmp_path: Path, monkeypatch):
    calls: list[list[str]] = []

    class _CP:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return _CP()

    monkeypatch.setattr("subprocess.run", fake_run)
    res = close_lane(tmp_path, branch="my-branch")
    assert calls and calls[0][:5] == ["orca-cli", "wt", "rm", "--branch", "my-branch"]
    assert res.rc == 0


def test_doctor_calls_orca_cli_wt_doctor(tmp_path: Path, monkeypatch):
    calls: list[list[str]] = []

    class _CP:
        returncode = 0
        stdout = "no issues"
        stderr = ""

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return _CP()

    monkeypatch.setattr("subprocess.run", fake_run)
    res = doctor(tmp_path)
    assert calls and calls[0][:4] == ["orca-cli", "wt", "doctor", "--reap"]
    assert res.rc == 0
