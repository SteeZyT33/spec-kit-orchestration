import json
import subprocess
from pathlib import Path

import pytest

from orca.core.worktrees.config import WorktreesConfig
from orca.core.worktrees.manager import WorktreeManager, CreateRequest, CreateResult


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
