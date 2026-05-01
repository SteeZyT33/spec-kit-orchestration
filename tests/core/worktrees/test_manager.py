import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from orca.core.worktrees.config import WorktreesConfig
from orca.core.worktrees.manager import (
    WorktreeManager, CreateRequest, CreateResult, IdempotencyError,
)


def _init_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "--allow-empty",
                    "--no-verify", "-m", "init"], check=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                        **__import__("os").environ})
    return tmp_path


@pytest.fixture
def repo(tmp_path):
    return _init_repo(tmp_path)


class TestCreateHappyPath:
    def test_creates_worktree_branch_sidecar_registry(self, repo):
        cfg = WorktreesConfig()
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=False)
        req = CreateRequest(branch="feature-foo", from_branch=None,
                            feature=None, lane=None, agent="none",
                            prompt=None, extra_args=[])
        result = mgr.create(req)
        assert isinstance(result, CreateResult)
        assert result.lane_id == "feature-foo"
        # Worktree directory exists
        assert (repo / ".orca" / "worktrees" / "feature-foo").is_dir()
        # Sidecar exists
        assert (repo / ".orca" / "worktrees" / "feature-foo.json").exists()
        # Registry entry exists
        reg = json.loads((repo / ".orca" / "worktrees" / "registry.json").read_text())
        assert reg["schema_version"] == 2
        assert reg["lanes"][0]["lane_id"] == "feature-foo"
        # Branch was created
        git_check = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--verify", "feature-foo"],
            capture_output=True, check=True,
        )
        assert git_check.returncode == 0


def _existing_lane(repo: Path, branch: str) -> tuple[str, Path]:
    """Helper: bring a lane into the (yes, yes, yes, yes) state."""
    cfg = WorktreesConfig()
    mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                          run_tmux=False, run_setup=False)
    req = CreateRequest(branch=branch, from_branch=None, feature=None, lane=None,
                        agent="none", prompt=None, extra_args=[])
    result = mgr.create(req)
    return result.lane_id, result.worktree_path


class TestStateCubeRows:
    # Row 2: branch yes, no worktree, no sidecar, no registry
    def test_branch_exists_no_worktree_refuses_without_reuse(self, repo):
        subprocess.run(["git", "-C", str(repo), "branch", "preexisting"], check=True)
        cfg = WorktreesConfig()
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=False)
        req = CreateRequest(branch="preexisting", from_branch=None,
                            feature=None, lane=None, agent="none",
                            prompt=None, extra_args=[])
        with pytest.raises(IdempotencyError, match="branch"):
            mgr.create(req)

    def test_branch_exists_no_worktree_succeeds_with_reuse(self, repo):
        subprocess.run(["git", "-C", str(repo), "branch", "preexisting"], check=True)
        cfg = WorktreesConfig()
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=False)
        req = CreateRequest(branch="preexisting", from_branch=None,
                            feature=None, lane=None, agent="none",
                            prompt=None, extra_args=[], reuse_branch=True)
        result = mgr.create(req)
        assert result.lane_id == "preexisting"

    # Row 5: fully registered → idempotent attach
    def test_fully_registered_attaches_idempotent(self, repo):
        lane_id, wt = _existing_lane(repo, "feature-foo")
        cfg = WorktreesConfig()
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=False)
        req = CreateRequest(branch="feature-foo", from_branch=None,
                            feature=None, lane=None, agent="none",
                            prompt=None, extra_args=[])
        result = mgr.create(req)
        assert result.lane_id == lane_id
        # Worktree wasn't recreated
        assert wt.exists()

    # Row 6: branch yes, sidecar yes, no worktree → refuse without --reuse-branch
    def test_branch_yes_sidecar_yes_no_worktree_refuses(self, repo):
        lane_id, wt = _existing_lane(repo, "feature-foo")
        # Force-remove the worktree leaving sidecar+registry+branch behind
        shutil.rmtree(wt)
        subprocess.run(["git", "-C", str(repo), "worktree", "prune"], check=True)
        cfg = WorktreesConfig()
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=False)
        req = CreateRequest(branch="feature-foo", from_branch=None,
                            feature=None, lane=None, agent="none",
                            prompt=None, extra_args=[])
        with pytest.raises(IdempotencyError, match="stale"):
            mgr.create(req)

    # Row 7: no branch, sidecar/registry yes → auto-clean; refuse without --recreate
    def test_no_branch_orphan_sidecar_refuses_without_recreate(self, repo):
        lane_id, wt = _existing_lane(repo, "feature-foo")
        # Delete branch + worktree externally
        shutil.rmtree(wt)
        subprocess.run(["git", "-C", str(repo), "worktree", "prune"], check=True)
        subprocess.run(["git", "-C", str(repo), "branch", "-D", "feature-foo"],
                       check=True)
        cfg = WorktreesConfig()
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=False)
        req = CreateRequest(branch="feature-foo", from_branch=None,
                            feature=None, lane=None, agent="none",
                            prompt=None, extra_args=[])
        with pytest.raises(IdempotencyError, match="recreate"):
            mgr.create(req)

    def test_no_branch_orphan_sidecar_succeeds_with_recreate(self, repo):
        lane_id, wt = _existing_lane(repo, "feature-foo")
        shutil.rmtree(wt)
        subprocess.run(["git", "-C", str(repo), "worktree", "prune"], check=True)
        subprocess.run(["git", "-C", str(repo), "branch", "-D", "feature-foo"],
                       check=True)
        cfg = WorktreesConfig()
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=False)
        req = CreateRequest(branch="feature-foo", from_branch=None,
                            feature=None, lane=None, agent="none",
                            prompt=None, extra_args=[], recreate_branch=True)
        result = mgr.create(req)
        assert result.lane_id == lane_id
        assert wt.exists()

    # Row 3: worktree at canonical path, no sidecar (operator created via
    # plain `git worktree add` directly) → adopt
    def test_row_3_worktree_at_canonical_path_no_sidecar_adopts(self, repo):
        cfg = WorktreesConfig()
        wt_root = repo / ".orca" / "worktrees"
        wt_root.mkdir(parents=True)
        canonical = wt_root / "feature-foo"
        # Plain git worktree add at the canonical path with NO orca state
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "-b",
             "feature-foo", str(canonical), "main"],
            check=True, capture_output=True,
        )
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=False)
        req = CreateRequest(branch="feature-foo", from_branch=None,
                            feature=None, lane=None, agent="none",
                            prompt=None, extra_args=[])
        result = mgr.create(req)
        # Sidecar + registry now exist for the previously-bare worktree
        assert result.lane_id == "feature-foo"
        assert (wt_root / "feature-foo.json").exists()
        # The original worktree directory was reused (not recreated)
        assert canonical.exists()

    # Row 4: worktree exists at a NON-canonical path (operator did
    # `git worktree add ../scratch foo`) → refuse
    def test_row_4_worktree_at_non_canonical_path_refuses(self, repo, tmp_path_factory):
        scratch = tmp_path_factory.mktemp("elsewhere") / "wt"
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "-b",
             "feature-foo", str(scratch), "main"],
            check=True, capture_output=True,
        )
        cfg = WorktreesConfig()
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=False)
        req = CreateRequest(branch="feature-foo", from_branch=None,
                            feature=None, lane=None, agent="none",
                            prompt=None, extra_args=[])
        with pytest.raises(IdempotencyError, match="unexpected path"):
            mgr.create(req)

    # Row 8: sidecar's branch field disagrees with --branch arg → refuse
    def test_row_8_sidecar_branch_mismatch_refuses(self, repo):
        lane_id, wt = _existing_lane(repo, "feature-foo")
        # Create another invocation with the SAME lane-id (via --feature/--lane)
        # but a different branch. derive_lane_id with feature='015' lane='wiz'
        # in lane mode → '015-wiz'. To force a collision we instead poke the
        # sidecar to advertise a different branch and re-call create.
        from orca.core.worktrees.registry import (
            sidecar_path, read_sidecar, write_sidecar, Sidecar,
        )
        wt_root = repo / ".orca" / "worktrees"
        sc = read_sidecar(sidecar_path(wt_root, lane_id))
        # Rewrite sidecar with a different branch claim
        mutated = Sidecar(**{**sc.__dict__, "branch": "different-branch"})
        write_sidecar(wt_root, mutated)

        cfg = WorktreesConfig()
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=False)
        # Now ask to create the same lane-id for the original branch:
        req = CreateRequest(branch="feature-foo", from_branch=None,
                            feature=None, lane=None, agent="none",
                            prompt=None, extra_args=[])
        with pytest.raises(IdempotencyError, match="already registered"):
            mgr.create(req)
