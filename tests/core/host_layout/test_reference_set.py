"""Reference-set auto-discovery for citation-validator default --reference-set."""
from __future__ import annotations

from pathlib import Path

from orca.core.host_layout.reference_set import discover


def test_discover_finds_canonical_artifacts(tmp_path: Path) -> None:
    fd = tmp_path / "001-feature"
    fd.mkdir()
    for name in ("plan.md", "data-model.md", "research.md", "quickstart.md", "tasks.md"):
        (fd / name).write_text("# stub\n")
    paths = discover(fd)
    assert sorted(p.name for p in paths) == sorted([
        "data-model.md", "plan.md", "quickstart.md", "research.md", "tasks.md",
    ])


def test_discover_skips_missing_artifacts(tmp_path: Path) -> None:
    fd = tmp_path / "001-feature"
    fd.mkdir()
    (fd / "plan.md").write_text("# stub\n")
    paths = discover(fd)
    assert [p.name for p in paths] == ["plan.md"]


def test_discover_includes_contracts(tmp_path: Path) -> None:
    fd = tmp_path / "001-feature"
    (fd / "contracts").mkdir(parents=True)
    (fd / "plan.md").write_text("# p\n")
    (fd / "contracts" / "api.md").write_text("# c\n")
    (fd / "contracts" / "events.md").write_text("# e\n")
    paths = discover(fd)
    names = [p.name for p in paths]
    assert "plan.md" in names
    assert "api.md" in names
    assert "events.md" in names


def test_discover_returns_absolute_paths(tmp_path: Path) -> None:
    fd = tmp_path / "001-feature"
    fd.mkdir()
    (fd / "plan.md").write_text("# p\n")
    paths = discover(fd)
    assert all(p.is_absolute() for p in paths)


def test_discover_empty_when_feature_dir_missing(tmp_path: Path) -> None:
    paths = discover(tmp_path / "nonexistent")
    assert paths == []


def test_discover_canonical_order(tmp_path: Path) -> None:
    """Canonical artifacts come before contracts, in a stable order."""
    fd = tmp_path / "001-feature"
    (fd / "contracts").mkdir(parents=True)
    for name in ("tasks.md", "plan.md", "data-model.md"):
        (fd / name).write_text("# s\n")
    (fd / "contracts" / "z.md").write_text("# z\n")
    (fd / "contracts" / "a.md").write_text("# a\n")

    paths = discover(fd)
    # Canonical order: plan, data-model, research, quickstart, tasks (existing first)
    # Then contracts/ in sorted order
    names = [p.name for p in paths]
    canonical = [n for n in ("plan.md", "data-model.md", "research.md", "quickstart.md", "tasks.md") if n in names]
    contract_names = sorted(["a.md", "z.md"])

    assert names[:len(canonical)] == canonical
    assert names[len(canonical):] == contract_names
