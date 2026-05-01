"""Tests for orca.core.path_safety — enforces docs/superpowers/contracts/path-safety.md."""
from __future__ import annotations

import pytest

from orca.core.path_safety import PathSafetyError


def test_path_safety_error_carries_structured_fields():
    err = PathSafetyError(
        "symlinks rejected: /tmp/x",
        field="--claude-findings-file",
        rule_violated="symlink_in_resolved_path",
        value_redacted="/tmp/x",
    )
    assert str(err) == "symlinks rejected: /tmp/x"
    assert err.field == "--claude-findings-file"
    assert err.rule_violated == "symlink_in_resolved_path"
    assert err.value_redacted == "/tmp/x"


def test_path_safety_error_to_error_detail_returns_three_keys():
    err = PathSafetyError(
        "msg", field="--feature-id", rule_violated="identifier_format",
        value_redacted="bad/value",
    )
    assert err.to_error_detail() == {
        "field": "--feature-id",
        "rule_violated": "identifier_format",
        "value_redacted": "bad/value",
    }


from orca.core.path_safety import validate_identifier


class TestValidateIdentifier:
    def test_valid_alphanumeric(self):
        assert validate_identifier("feature_001", field="--feature-id") == "feature_001"

    def test_valid_with_dots_dashes_underscores(self):
        assert validate_identifier("001-foo.bar_baz", field="--feature-id") == "001-foo.bar_baz"

    def test_rejects_empty_string(self):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_identifier("", field="--feature-id")
        assert exc_info.value.rule_violated == "identifier_empty"
        assert exc_info.value.field == "--feature-id"

    def test_rejects_dot(self):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_identifier(".", field="--feature-id")
        assert exc_info.value.rule_violated == "identifier_reserved"

    def test_rejects_double_dot(self):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_identifier("..", field="--feature-id")
        assert exc_info.value.rule_violated == "identifier_reserved"

    def test_rejects_leading_dash(self):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_identifier("-foo", field="--feature-id")
        assert exc_info.value.rule_violated == "identifier_format"

    def test_rejects_slash(self):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_identifier("foo/bar", field="--feature-id")
        assert exc_info.value.rule_violated == "identifier_format"

    def test_rejects_null_byte(self):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_identifier("foo\0bar", field="--feature-id")
        assert exc_info.value.rule_violated == "identifier_format"

    def test_rejects_traversal_attempt(self):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_identifier("..\\foo", field="--feature-id")
        assert exc_info.value.rule_violated == "identifier_format"

    def test_rejects_too_long(self):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_identifier("a" * 129, field="--feature-id")
        assert exc_info.value.rule_violated == "identifier_too_long"

    def test_max_length_default_is_128(self):
        # Exactly 128 chars: valid
        assert validate_identifier("a" * 128, field="--feature-id") == "a" * 128


from pathlib import Path

from orca.core.path_safety import validate_repo_file


class TestValidateRepoFile:
    def test_happy_path_returns_resolved(self, tmp_path: Path):
        f = tmp_path / "spec.md"
        f.write_text("hello", encoding="utf-8")
        result = validate_repo_file(f, root=tmp_path, field="--target")
        assert result == f.resolve()

    def test_accepts_string_path(self, tmp_path: Path):
        f = tmp_path / "spec.md"
        f.write_text("hello")
        result = validate_repo_file(str(f), root=tmp_path, field="--target")
        assert result == f.resolve()

    def test_rejects_symlink(self, tmp_path: Path):
        real = tmp_path / "real.md"
        real.write_text("hi")
        link = tmp_path / "link.md"
        link.symlink_to(real)
        with pytest.raises(PathSafetyError) as exc_info:
            validate_repo_file(link, root=tmp_path, field="--target")
        assert exc_info.value.rule_violated == "symlink_in_resolved_path"

    def test_rejects_path_outside_root(self, tmp_path: Path):
        outside = tmp_path.parent / "outside.md"
        outside.write_text("escape")
        try:
            with pytest.raises(PathSafetyError) as exc_info:
                validate_repo_file(outside, root=tmp_path, field="--target")
            assert exc_info.value.rule_violated == "path_outside_root"
        finally:
            outside.unlink(missing_ok=True)

    def test_rejects_directory(self, tmp_path: Path):
        d = tmp_path / "subdir"
        d.mkdir()
        with pytest.raises(PathSafetyError) as exc_info:
            validate_repo_file(d, root=tmp_path, field="--target")
        assert exc_info.value.rule_violated == "not_a_regular_file"

    def test_rejects_missing_when_must_exist(self, tmp_path: Path):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_repo_file(tmp_path / "missing.md", root=tmp_path, field="--target")
        assert exc_info.value.rule_violated == "does_not_exist"

    def test_rejects_oversized(self, tmp_path: Path):
        f = tmp_path / "big.md"
        f.write_bytes(b"x" * 1024)
        with pytest.raises(PathSafetyError) as exc_info:
            validate_repo_file(f, root=tmp_path, field="--target", max_bytes=512)
        assert exc_info.value.rule_violated == "size_cap_exceeded"

    def test_must_exist_false_allows_missing(self, tmp_path: Path):
        # must_exist=False is for forward-looking writes; size/type checks skipped
        result = validate_repo_file(
            tmp_path / "future.md", root=tmp_path, field="--target", must_exist=False
        )
        assert result == (tmp_path / "future.md").resolve()


from orca.core.path_safety import validate_repo_dir


class TestValidateRepoDir:
    def test_happy_path_returns_resolved(self, tmp_path: Path):
        d = tmp_path / "feature-001"
        d.mkdir()
        result = validate_repo_dir(d, root=tmp_path, field="--feature-dir")
        assert result == d.resolve()

    def test_rejects_symlink(self, tmp_path: Path):
        real = tmp_path / "real-dir"
        real.mkdir()
        link = tmp_path / "link-dir"
        link.symlink_to(real, target_is_directory=True)
        with pytest.raises(PathSafetyError) as exc_info:
            validate_repo_dir(link, root=tmp_path, field="--feature-dir")
        assert exc_info.value.rule_violated == "symlink_in_resolved_path"

    def test_rejects_path_outside_root(self, tmp_path: Path):
        outside = tmp_path.parent / "outside-dir"
        outside.mkdir()
        try:
            with pytest.raises(PathSafetyError) as exc_info:
                validate_repo_dir(outside, root=tmp_path, field="--feature-dir")
            assert exc_info.value.rule_violated == "path_outside_root"
        finally:
            outside.rmdir()

    def test_rejects_regular_file(self, tmp_path: Path):
        f = tmp_path / "file.md"
        f.write_text("hi")
        with pytest.raises(PathSafetyError) as exc_info:
            validate_repo_dir(f, root=tmp_path, field="--feature-dir")
        assert exc_info.value.rule_violated == "not_a_directory"

    def test_rejects_missing_when_must_exist(self, tmp_path: Path):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_repo_dir(tmp_path / "missing", root=tmp_path, field="--feature-dir")
        assert exc_info.value.rule_violated == "does_not_exist"

    def test_must_exist_false_allows_missing(self, tmp_path: Path):
        result = validate_repo_dir(
            tmp_path / "future-dir", root=tmp_path,
            field="--feature-dir", must_exist=False,
        )
        assert result == (tmp_path / "future-dir").resolve()
