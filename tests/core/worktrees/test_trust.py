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


# --- Task 14: trust prompt flow ---
import io
import sys
from unittest.mock import patch

from orca.core.worktrees.trust import (
    check_or_prompt, TrustOutcome, TrustDecision,
)


class TestCheckOrPrompt:
    def test_already_trusted_returns_trusted(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ORCA_TRUST_LEDGER", str(tmp_path / "l.json"))
        ledger = TrustLedger.load()
        ledger.record(repo_key="k", script_path="s", sha="abc")
        ledger.save()

        out = check_or_prompt(repo_key="k", script_path="s", sha="abc",
                              script_text="echo hi",
                              decision=TrustDecision(trust_hooks=False, record=False),
                              interactive=True)
        assert out == TrustOutcome.TRUSTED

    def test_trust_hooks_bypass_without_record(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ORCA_TRUST_LEDGER", str(tmp_path / "l.json"))
        out = check_or_prompt(repo_key="k", script_path="s", sha="abc",
                              script_text="echo hi",
                              decision=TrustDecision(trust_hooks=True, record=False),
                              interactive=False)
        assert out == TrustOutcome.BYPASSED
        # Ledger unchanged
        ledger = TrustLedger.load()
        assert not ledger.is_trusted("k", "s", "abc")

    def test_trust_hooks_with_record_persists(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ORCA_TRUST_LEDGER", str(tmp_path / "l.json"))
        out = check_or_prompt(repo_key="k", script_path="s", sha="abc",
                              script_text="echo hi",
                              decision=TrustDecision(trust_hooks=True, record=True),
                              interactive=False)
        assert out == TrustOutcome.RECORDED
        ledger = TrustLedger.load()
        assert ledger.is_trusted("k", "s", "abc")

    def test_non_interactive_unknown_refuses(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ORCA_TRUST_LEDGER", str(tmp_path / "l.json"))
        out = check_or_prompt(repo_key="k", script_path="s", sha="abc",
                              script_text="echo hi",
                              decision=TrustDecision(trust_hooks=False, record=False),
                              interactive=False)
        assert out == TrustOutcome.REFUSED_NONINTERACTIVE

    def test_interactive_yes_records_and_returns_recorded(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ORCA_TRUST_LEDGER", str(tmp_path / "l.json"))
        with patch("sys.stdin", io.StringIO("y\n")):
            out = check_or_prompt(repo_key="k", script_path="s", sha="abc",
                                  script_text="echo hi",
                                  decision=TrustDecision(trust_hooks=False, record=False),
                                  interactive=True)
        assert out == TrustOutcome.RECORDED

    def test_interactive_no_returns_declined(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ORCA_TRUST_LEDGER", str(tmp_path / "l.json"))
        with patch("sys.stdin", io.StringIO("n\n")):
            out = check_or_prompt(repo_key="k", script_path="s", sha="abc",
                                  script_text="echo hi",
                                  decision=TrustDecision(trust_hooks=False, record=False),
                                  interactive=True)
        assert out == TrustOutcome.DECLINED


class TestConcurrentRecord:
    def test_concurrent_record_does_not_lose_writes(self, tmp_path,
                                                     monkeypatch):
        """Two threads each call check_or_prompt(... record=True) with
        different script_paths; both must end up in the ledger."""
        import threading
        monkeypatch.setenv("ORCA_TRUST_LEDGER", str(tmp_path / "l.json"))

        def _record(script_path: str, sha: str) -> None:
            check_or_prompt(
                repo_key="repo", script_path=script_path, sha=sha,
                script_text="echo hi",
                decision=TrustDecision(trust_hooks=True, record=True),
                interactive=False,
            )

        # Launch many threads recording distinct entries simultaneously.
        threads = [
            threading.Thread(target=_record,
                             args=(f"/p/script-{i}", f"sha{i}"))
            for i in range(8)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        ledger = TrustLedger.load()
        for i in range(8):
            assert ledger.is_trusted("repo", f"/p/script-{i}", f"sha{i}"), (
                f"entry {i} lost to concurrent write"
            )
