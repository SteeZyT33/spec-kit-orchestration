from __future__ import annotations

import json
from pathlib import Path

import pytest

from speckit_orca import capability_packs
from speckit_orca.capability_packs import (
    BUILTIN_PACKS,
    load_manifest_overrides,
    resolve_effective_packs,
    scaffold_manifest,
    validate_registry,
)


def test_flow_state_is_not_enabled_without_specs_dir(tmp_path: Path) -> None:
    packs = {pack.id: pack for pack in resolve_effective_packs(tmp_path)}

    assert packs["flow-state"].enabled is False
    assert packs["flow-state"].evidence == []


def test_flow_state_is_enabled_when_specs_dir_exists(tmp_path: Path) -> None:
    (tmp_path / "specs").mkdir()

    packs = {pack.id: pack for pack in resolve_effective_packs(tmp_path)}

    assert packs["flow-state"].enabled is True
    assert packs["flow-state"].evidence == ["specs/ directory present"]


def test_validate_registry_rejects_disabling_always_on_pack(tmp_path: Path) -> None:
    manifest = tmp_path / ".specify" / "orca" / "capability-packs.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"review": {"enabled": False, "reason": "bad override"}}), encoding="utf-8")

    issues = validate_registry(tmp_path)

    assert "review: always-on packs may not be disabled by manifest" in issues


def test_validate_registry_rejects_empty_owned_behaviors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    broken = dict(BUILTIN_PACKS)
    broken["review"] = capability_packs.CapabilityPackDefinition(
        id="review",
        purpose="Review lifecycle ownership",
        status="core",
        activation_mode="always-on",
        affected_commands=("speckit.orca.code-review",),
        prerequisites=(),
        owned_behaviors=(),
    )
    monkeypatch.setattr(capability_packs, "BUILTIN_PACKS", broken)

    issues = validate_registry(tmp_path)

    assert "review: owned_behaviors must not be empty" in issues


def test_load_manifest_overrides_accepts_top_level_map(tmp_path: Path) -> None:
    manifest = tmp_path / "capability-packs.json"
    manifest.write_text(json.dumps({"worktrees": True}), encoding="utf-8")

    overrides = load_manifest_overrides(manifest)

    assert overrides["worktrees"].enabled is True


def test_scaffold_manifest_reports_missing_template(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class MissingPath(Path):
        _flavour = type(Path())._flavour

        def exists(self) -> bool:  # type: ignore[override]
            return False

    monkeypatch.setattr(capability_packs, "Path", MissingPath)

    with pytest.raises(FileNotFoundError, match="Capability pack template not found"):
        scaffold_manifest(tmp_path)
