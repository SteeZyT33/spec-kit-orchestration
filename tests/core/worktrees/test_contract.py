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


class TestContractValidation:
    def test_schema_version_must_be_int_one(self, tmp_path):
        (tmp_path / ".worktree-contract.json").write_text(json.dumps({
            "schema_version": 2,
            "symlink_paths": [],
            "symlink_files": [],
        }))
        with pytest.raises(ContractError, match="schema_version"):
            load_contract(tmp_path)

    def test_symlink_paths_must_be_list(self, tmp_path):
        (tmp_path / ".worktree-contract.json").write_text(json.dumps({
            "schema_version": 1,
            "symlink_paths": "specs",  # str, not list
            "symlink_files": [],
        }))
        with pytest.raises(ContractError, match="symlink_paths"):
            load_contract(tmp_path)

    def test_path_traversal_rejected(self, tmp_path):
        (tmp_path / ".worktree-contract.json").write_text(json.dumps({
            "schema_version": 1,
            "symlink_paths": ["../escape"],
            "symlink_files": [],
        }))
        with pytest.raises(ContractError, match="traversal|outside"):
            load_contract(tmp_path)

    def test_absolute_paths_rejected(self, tmp_path):
        (tmp_path / ".worktree-contract.json").write_text(json.dumps({
            "schema_version": 1,
            "symlink_paths": ["/etc/passwd"],
            "symlink_files": [],
        }))
        with pytest.raises(ContractError, match="absolute|relative"):
            load_contract(tmp_path)

    def test_extensions_must_be_object_when_present(self, tmp_path):
        (tmp_path / ".worktree-contract.json").write_text(json.dumps({
            "schema_version": 1,
            "symlink_paths": [],
            "symlink_files": [],
            "extensions": 42,
        }))
        with pytest.raises(ContractError, match="extensions"):
            load_contract(tmp_path)

    def test_extensions_object_accepted_subkeys_ignored(self, tmp_path):
        (tmp_path / ".worktree-contract.json").write_text(json.dumps({
            "schema_version": 1,
            "symlink_paths": [],
            "symlink_files": [],
            "extensions": {"cmux": {"foo": "bar"}},
        }))
        # No raise; subkeys ignored in v1
        c = load_contract(tmp_path)
        assert c.symlink_paths == []


from orca.core.worktrees.contract import merge_symlinks


class TestMergeSymlinks:
    def test_host_first_then_contract_then_toml(self):
        host = ["specs", ".specify"]
        contract = ["agents", "skills"]
        toml = ["custom"]
        assert merge_symlinks(host, contract, toml) == [
            "specs", ".specify", "agents", "skills", "custom"
        ]

    def test_dedup_preserves_first_insertion(self):
        host = ["specs"]
        contract = ["specs", "agents"]  # specs is duplicate
        toml = []
        assert merge_symlinks(host, contract, toml) == ["specs", "agents"]

    def test_empty_inputs_yield_empty_output(self):
        assert merge_symlinks([], [], []) == []

    def test_none_contract_treated_as_empty(self):
        # caller may pass None when no contract is loaded
        assert merge_symlinks(["a"], None, ["b"]) == ["a", "b"]
