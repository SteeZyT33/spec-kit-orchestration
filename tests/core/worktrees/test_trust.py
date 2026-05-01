import json
import os
from pathlib import Path

import pytest

from orca.core.worktrees.trust import (
    TrustLedger, resolve_repo_key, ledger_path,
)


class TestResolveRepoKey:
    def test_uses_remote_origin_when_present(self, tmp_path, monkeypatch):
        # Set up a fake repo with a remote
        import subprocess
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "remote", "add",
                        "origin", "git@github.com:o/r.git"], check=True)
        assert resolve_repo_key(tmp_path) == "git@github.com:o/r.git"

    def test_falls_back_to_realpath_when_no_remote(self, tmp_path):
        import subprocess
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        key = resolve_repo_key(tmp_path)
        # Falls back to the realpath of the repo
        assert Path(key).resolve() == tmp_path.resolve()


class TestLedgerPath:
    def test_default_xdg(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        monkeypatch.delenv("ORCA_TRUST_LEDGER", raising=False)
        path = ledger_path()
        assert path == tmp_path / "orca" / "worktree-trust.json"

    def test_explicit_env_overrides(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ORCA_TRUST_LEDGER", str(tmp_path / "custom.json"))
        assert ledger_path() == tmp_path / "custom.json"


class TestTrustLedger:
    def test_load_missing_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ORCA_TRUST_LEDGER", str(tmp_path / "missing.json"))
        ledger = TrustLedger.load()
        assert ledger.is_trusted("k", "/p/setup", "abc") is False

    def test_record_then_check(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ORCA_TRUST_LEDGER", str(tmp_path / "l.json"))
        ledger = TrustLedger.load()
        ledger.record(repo_key="k", script_path="/p/setup", sha="abc")
        ledger.save()

        # Reload from disk
        reloaded = TrustLedger.load()
        assert reloaded.is_trusted("k", "/p/setup", "abc") is True
        # Different SHA -> not trusted (script changed)
        assert reloaded.is_trusted("k", "/p/setup", "xyz") is False
        # Different repo -> not trusted
        assert reloaded.is_trusted("other", "/p/setup", "abc") is False

    def test_atomic_write(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ORCA_TRUST_LEDGER", str(tmp_path / "l.json"))
        ledger = TrustLedger.load()
        ledger.record(repo_key="k", script_path="s", sha="a")
        ledger.save()
        partials = list(tmp_path.glob("*.partial"))
        assert partials == []
