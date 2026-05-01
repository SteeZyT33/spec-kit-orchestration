import pytest
from orca.core.worktrees.identifiers import (
    derive_lane_id,
    sanitize_repo_name,
    LaneIdMode,
)
from orca.core.path_safety import PathSafetyError


class TestDeriveLaneIdBranchMode:
    def test_simple_branch_passes_through(self):
        assert derive_lane_id(branch="feature-foo", mode="branch") == "feature-foo"

    def test_slashes_replaced_with_hyphens(self):
        assert derive_lane_id(branch="feature/foo", mode="branch") == "feature-foo"

    def test_special_chars_replaced_with_underscore(self):
        assert derive_lane_id(branch="feat@2.0!", mode="branch") == "feat_2.0_"

    def test_max_length_128_enforced(self):
        long = "a" * 200
        with pytest.raises(PathSafetyError):
            derive_lane_id(branch=long, mode="branch")


class TestDeriveLaneIdLaneMode:
    def test_feature_lane_combines(self):
        assert derive_lane_id(branch="feature/015-wizard",
                              mode="lane",
                              feature="015",
                              lane="wizard") == "015-wizard"

    def test_lane_mode_requires_feature_and_lane(self):
        with pytest.raises(ValueError, match="lane mode requires"):
            derive_lane_id(branch="x", mode="lane")


class TestDeriveLaneIdAuto:
    def test_auto_with_feature_and_lane_uses_lane_mode(self):
        assert derive_lane_id(branch="x", mode="auto",
                              feature="015", lane="wiz") == "015-wiz"

    def test_auto_without_feature_uses_branch_mode(self):
        assert derive_lane_id(branch="x/y", mode="auto") == "x-y"


class TestSanitizeRepoName:
    def test_clean_name_passes(self):
        assert sanitize_repo_name("orca") == "orca"

    def test_dot_replaced(self):
        # tmux target syntax uses : and .; both replaced
        assert sanitize_repo_name("my.repo") == "my_repo"

    def test_colon_replaced(self):
        assert sanitize_repo_name("repo:branch") == "repo_branch"

    def test_truncated_to_64(self):
        assert len(sanitize_repo_name("a" * 100)) == 64
