import json
from pathlib import Path

import pytest

from orca.core.worktrees.contract import (
    ContractData,
    ContractError,
    load_contract,
)


class TestLoadContract:
    def test_returns_none_when_file_missing(self, tmp_path):
        assert load_contract(tmp_path) is None

    def test_round_trip_minimal(self, tmp_path):
        (tmp_path / ".worktree-contract.json").write_text(json.dumps({
            "schema_version": 1,
            "symlink_paths": ["specs"],
            "symlink_files": [".env"],
        }))
        c = load_contract(tmp_path)
        assert c == ContractData(
            schema_version=1,
            symlink_paths=["specs"],
            symlink_files=[".env"],
            init_script=None,
        )

    def test_full_shape_loads(self, tmp_path):
        (tmp_path / ".worktree-contract.json").write_text(json.dumps({
            "schema_version": 1,
            "symlink_paths": [".specify", "docs"],
            "symlink_files": [".env", ".env.local"],
            "init_script": ".worktree-contract/after_create.sh",
        }))
        c = load_contract(tmp_path)
        assert c is not None
        assert c.symlink_paths == [".specify", "docs"]
        assert c.init_script == ".worktree-contract/after_create.sh"
