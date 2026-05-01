import os
import stat
from pathlib import Path

import pytest

from orca.core.worktrees.hooks import (
    HookEnv, run_hook, HookOutcome, hook_sha,
)


def _make_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


class TestRunHook:
    def test_missing_hook_returns_skipped(self, tmp_path):
        env = HookEnv(repo_root=tmp_path, worktree_dir=tmp_path / "wt",
                      branch="x", lane_id="x", lane_mode="branch",
                      feature_id=None, host_system="bare")
        outcome = run_hook(script_path=tmp_path / "missing.sh", env=env)
        assert outcome.status == "skipped"

    def test_successful_hook_completes_zero(self, tmp_path):
        wt = tmp_path / "wt"
        wt.mkdir()
        hook = tmp_path / "after_create"
        _make_executable(hook, '#!/usr/bin/env bash\nexit 0\n')

        env = HookEnv(repo_root=tmp_path, worktree_dir=wt, branch="x",
                      lane_id="x", lane_mode="branch", feature_id=None,
                      host_system="bare")
        outcome = run_hook(script_path=hook, env=env)
        assert outcome.status == "completed"
        assert outcome.exit_code == 0

    def test_failing_hook_returns_failed(self, tmp_path):
        wt = tmp_path / "wt"
        wt.mkdir()
        hook = tmp_path / "after_create"
        _make_executable(hook, '#!/usr/bin/env bash\nexit 7\n')

        env = HookEnv(repo_root=tmp_path, worktree_dir=wt, branch="x",
                      lane_id="x", lane_mode="branch", feature_id=None,
                      host_system="bare")
        outcome = run_hook(script_path=hook, env=env)
        assert outcome.status == "failed"
        assert outcome.exit_code == 7

    def test_env_contract_injected(self, tmp_path):
        wt = tmp_path / "wt"
        wt.mkdir()
        out = tmp_path / "out.txt"
        hook = tmp_path / "after_create"
        _make_executable(hook,
            '#!/usr/bin/env bash\n'
            f'echo "$ORCA_LANE_ID:$ORCA_BRANCH:$ORCA_HOST_SYSTEM" > "{out}"\n')

        env = HookEnv(repo_root=tmp_path, worktree_dir=wt, branch="feat",
                      lane_id="L1", lane_mode="branch", feature_id=None,
                      host_system="superpowers")
        outcome = run_hook(script_path=hook, env=env)
        assert outcome.status == "completed"
        assert out.read_text().strip() == "L1:feat:superpowers"

    def test_cwd_is_worktree_dir(self, tmp_path):
        wt = tmp_path / "wt"
        wt.mkdir()
        out = tmp_path / "cwd.txt"
        hook = tmp_path / "after_create"
        _make_executable(hook,
            '#!/usr/bin/env bash\n'
            f'pwd > "{out}"\n')

        env = HookEnv(repo_root=tmp_path, worktree_dir=wt, branch="x",
                      lane_id="x", lane_mode="branch", feature_id=None,
                      host_system="bare")
        run_hook(script_path=hook, env=env)
        assert out.read_text().strip() == str(wt.resolve())


class TestHookSha:
    def test_returns_sha256_hex(self, tmp_path):
        h = tmp_path / "after_create"
        h.write_text("#!/usr/bin/env bash\necho hi\n")
        sha = hook_sha(h)
        assert len(sha) == 64
        assert all(c in "0123456789abcdef" for c in sha)
