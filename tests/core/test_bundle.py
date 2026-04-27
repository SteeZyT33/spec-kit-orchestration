from __future__ import annotations

from pathlib import Path

import pytest

from orca.core.bundle import ReviewBundle, BundleError, build_bundle


def test_build_bundle_from_paths(tmp_path: Path):
    f1 = tmp_path / "a.py"
    f1.write_text("print('a')\n")
    f2 = tmp_path / "b.py"
    f2.write_text("print('b')\n")

    bundle = build_bundle(
        kind="diff",
        target=[str(f1), str(f2)],
        feature_id="001-foo",
        criteria=["correctness"],
        context=[],
    )
    assert bundle.kind == "diff"
    assert bundle.feature_id == "001-foo"
    assert len(bundle.target_paths) == 2
    assert bundle.criteria == ("correctness",)


def test_build_bundle_rejects_unknown_kind(tmp_path: Path):
    with pytest.raises(BundleError, match="unknown kind"):
        build_bundle(kind="banana", target=[], feature_id=None, criteria=[], context=[])


def test_build_bundle_rejects_missing_path(tmp_path: Path):
    with pytest.raises(BundleError, match="not found"):
        build_bundle(
            kind="spec",
            target=[str(tmp_path / "nope.md")],
            feature_id=None,
            criteria=[],
            context=[],
        )


def test_bundle_hash_stable_across_calls(tmp_path: Path):
    f = tmp_path / "a.py"
    f.write_text("print('a')\n")
    b1 = build_bundle(kind="diff", target=[str(f)], feature_id=None, criteria=[], context=[])
    b2 = build_bundle(kind="diff", target=[str(f)], feature_id=None, criteria=[], context=[])
    assert b1.bundle_hash == b2.bundle_hash


def test_bundle_hash_changes_with_content(tmp_path: Path):
    f = tmp_path / "a.py"
    f.write_text("v1\n")
    b1 = build_bundle(kind="diff", target=[str(f)], feature_id=None, criteria=[], context=[])
    f.write_text("v2\n")
    b2 = build_bundle(kind="diff", target=[str(f)], feature_id=None, criteria=[], context=[])
    assert b1.bundle_hash != b2.bundle_hash


def test_build_bundle_rejects_missing_context(tmp_path: Path):
    f = tmp_path / "a.py"
    f.write_text("ok\n")
    with pytest.raises(BundleError, match="context not found"):
        build_bundle(
            kind="diff",
            target=[str(f)],
            feature_id=None,
            criteria=[],
            context=[str(tmp_path / "missing-context.md")],
        )


def test_bundle_hash_changes_with_feature_id(tmp_path: Path):
    f = tmp_path / "a.py"
    f.write_text("v1\n")
    b1 = build_bundle(kind="diff", target=[str(f)], feature_id="001", criteria=[], context=[])
    b2 = build_bundle(kind="diff", target=[str(f)], feature_id="002", criteria=[], context=[])
    assert b1.bundle_hash != b2.bundle_hash


def test_bundle_hash_changes_with_criteria(tmp_path: Path):
    f = tmp_path / "a.py"
    f.write_text("v1\n")
    b1 = build_bundle(kind="diff", target=[str(f)], feature_id=None, criteria=["a"], context=[])
    b2 = build_bundle(kind="diff", target=[str(f)], feature_id=None, criteria=["b"], context=[])
    assert b1.bundle_hash != b2.bundle_hash


def test_render_text_includes_criteria(tmp_path: Path):
    f = tmp_path / "a.py"
    f.write_text("hi\n")
    bundle = build_bundle(
        kind="diff",
        target=[str(f)],
        feature_id=None,
        criteria=["correctness", "security"],
        context=[],
    )
    rendered = bundle.render_text()
    assert "## Review Criteria" in rendered
    assert "- correctness" in rendered
    assert "- security" in rendered


def test_render_text_includes_context_files(tmp_path: Path):
    target = tmp_path / "a.py"
    target.write_text("target_content\n")
    ctx = tmp_path / "spec.md"
    ctx.write_text("CONTEXT_MARKER_42\n")

    bundle = build_bundle(
        kind="diff",
        target=[str(target)],
        feature_id=None,
        criteria=[],
        context=[str(ctx)],
    )
    rendered = bundle.render_text()
    assert "## Context" in rendered
    assert "CONTEXT_MARKER_42" in rendered
    assert "target_content" in rendered


def test_render_text_omits_empty_criteria(tmp_path: Path):
    f = tmp_path / "a.py"
    f.write_text("hi\n")
    bundle = build_bundle(
        kind="diff", target=[str(f)], feature_id=None, criteria=[], context=[],
    )
    rendered = bundle.render_text()
    assert "## Review Criteria" not in rendered


def test_bundle_hash_and_render_immune_to_post_build_changes(tmp_path: Path):
    """Bytes are snapshotted at build time so a file mutating between
    build_bundle() and reviewer invocation can't desync the hash from
    what render_text() actually sends to the reviewer."""
    f = tmp_path / "a.py"
    f.write_text("ORIGINAL_CONTENT\n")
    bundle = build_bundle(
        kind="diff", target=[str(f)], feature_id=None, criteria=[], context=[],
    )
    original_hash = bundle.bundle_hash
    original_render = bundle.render_text()

    # Mutate the file on disk after the bundle is built.
    f.write_text("MUTATED_CONTENT\n")

    assert bundle.bundle_hash == original_hash
    assert bundle.render_text() == original_render
    assert "ORIGINAL_CONTENT" in bundle.render_text()
    assert "MUTATED_CONTENT" not in bundle.render_text()


def test_build_bundle_accepts_generator_inputs(tmp_path: Path):
    """Materialization fix: callers passing generators must work end-to-end."""
    f = tmp_path / "a.py"
    f.write_text("ok\n")
    bundle = build_bundle(
        kind="diff",
        target=(str(p) for p in [f]),
        feature_id=None,
        criteria=(c for c in ["correctness"]),
        context=(c for c in []),
    )
    assert bundle.target_paths == (Path(str(f)),)
    assert bundle.criteria == ("correctness",)
