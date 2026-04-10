from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


VALID_PACK_STATUSES = {"core", "optional", "experimental", "downstream"}
VALID_ACTIVATION_MODES = {"always-on", "config-enabled", "experimental-only"}
DEFAULT_MANIFEST_RELATIVE_PATH = Path(".specify/orca/capability-packs.json")


@dataclass(frozen=True)
class CapabilityPackDefinition:
    id: str
    purpose: str
    status: str
    activation_mode: str
    affected_commands: tuple[str, ...]
    prerequisites: tuple[str, ...]
    owned_behaviors: tuple[str, ...]


@dataclass
class CapabilityPackValidationIssue:
    pack_id: str
    message: str


@dataclass(frozen=True)
class CapabilityPackOverride:
    enabled: bool
    reason: str | None = None


@dataclass
class EffectiveCapabilityPack:
    id: str
    purpose: str
    status: str
    activation_mode: str
    enabled: bool
    activation_source: str
    affected_commands: list[str]
    prerequisites: list[str]
    owned_behaviors: list[str]
    evidence: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    override_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


BUILTIN_PACKS: dict[str, CapabilityPackDefinition] = {
    "brainstorm-memory": CapabilityPackDefinition(
        id="brainstorm-memory",
        purpose="Durable idea capture, revisit detection, and downstream linking for brainstorm artifacts.",
        status="optional",
        activation_mode="config-enabled",
        affected_commands=("speckit.orca.brainstorm", "speckit.specify", "speckit.plan"),
        prerequisites=("brainstorm/ directory or explicit brainstorm-memory workflow intent",),
        owned_behaviors=("numbered brainstorm records", "overview regeneration", "downstream idea links"),
    ),
    "flow-state": CapabilityPackDefinition(
        id="flow-state",
        purpose="Artifact-first workflow stage computation and next-step guidance shared across commands.",
        status="optional",
        activation_mode="config-enabled",
        affected_commands=(
            "speckit.orca.assign",
            "speckit.orca.code-review",
            "speckit.orca.cross-review",
            "speckit.orca.pr-review",
            "speckit.orca.self-review",
        ),
        prerequisites=("spec artifacts under specs/<feature>/",),
        owned_behaviors=("current-stage computation", "review milestone separation", "resume guidance"),
    ),
    "worktrees": CapabilityPackDefinition(
        id="worktrees",
        purpose="Provider-agnostic lane metadata and worktree-aware workflow context.",
        status="optional",
        activation_mode="config-enabled",
        affected_commands=(
            "speckit.orca.assign",
            "speckit.orca.code-review",
            "speckit.orca.cross-review",
            "speckit.orca.pr-review",
            "speckit.orca.self-review",
        ),
        prerequisites=(".specify/orca/worktrees/registry.json",),
        owned_behaviors=("lane registry", "lane status reporting", "worktree context enrichment"),
    ),
    "review": CapabilityPackDefinition(
        id="review",
        purpose="Review lifecycle ownership across code-review, cross-review, pr-review, and self-review.",
        status="core",
        activation_mode="always-on",
        affected_commands=(
            "speckit.orca.code-review",
            "speckit.orca.cross-review",
            "speckit.orca.pr-review",
            "speckit.orca.self-review",
        ),
        prerequisites=(),
        owned_behaviors=("review staging", "review artifact production", "feedback loop processing"),
    ),
    "yolo": CapabilityPackDefinition(
        id="yolo",
        purpose="Downstream end-to-end orchestration across brainstorm, spec, implementation, review, and PR handoff.",
        status="downstream",
        activation_mode="experimental-only",
        affected_commands=("speckit.orca.yolo",),
        prerequisites=("stable pack boundaries", "review architecture", "context handoffs"),
        owned_behaviors=("stage orchestration", "resume/start-from control", "PR-completion handoff"),
    ),
}


def _default_manifest_path(root: Path) -> Path:
    return root / DEFAULT_MANIFEST_RELATIVE_PATH


def _normalize_override(raw: Any, pack_id: str) -> CapabilityPackOverride:
    if isinstance(raw, bool):
        return CapabilityPackOverride(enabled=raw)
    if not isinstance(raw, dict):
        raise ValueError(f"Pack override for '{pack_id}' must be a boolean or object")
    enabled = raw.get("enabled")
    if not isinstance(enabled, bool):
        raise ValueError(f"Pack override for '{pack_id}' must define boolean 'enabled'")
    reason = raw.get("reason")
    if reason is not None and not isinstance(reason, str):
        raise ValueError(f"Pack override reason for '{pack_id}' must be a string")
    return CapabilityPackOverride(enabled=enabled, reason=reason.strip() or None if isinstance(reason, str) else None)


def load_manifest_overrides(manifest_path: Path) -> dict[str, CapabilityPackOverride]:
    if not manifest_path.exists():
        return {}
    if not manifest_path.is_file():
        raise ValueError(f"Capability pack manifest is not a file: {manifest_path}")

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read capability pack manifest: {manifest_path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Capability pack manifest must be a JSON object")

    pack_overrides = payload.get("packs", payload)
    if not isinstance(pack_overrides, dict):
        raise ValueError("Capability pack manifest 'packs' must be a JSON object")

    overrides: dict[str, CapabilityPackOverride] = {}
    for pack_id, raw_override in pack_overrides.items():
        if pack_id not in BUILTIN_PACKS:
            raise ValueError(f"Unknown capability pack override '{pack_id}'")
        overrides[pack_id] = _normalize_override(raw_override, pack_id)
    return overrides


def _heuristic_enabled(pack: CapabilityPackDefinition, root: Path) -> tuple[bool, list[str]]:
    evidence: list[str] = []

    if pack.id == "brainstorm-memory":
        brainstorm_dir = root / "brainstorm"
        if brainstorm_dir.is_dir():
            evidence.append("brainstorm/ directory present")
            return True, evidence
        return False, evidence

    if pack.id == "worktrees":
        registry_path = root / ".specify" / "orca" / "worktrees" / "registry.json"
        if registry_path.exists():
            evidence.append(".specify/orca/worktrees/registry.json present")
            return True, evidence
        return False, evidence

    if pack.id == "flow-state":
        specs_dir = root / "specs"
        if specs_dir.is_dir():
            evidence.append("specs/ directory present")
            return True, evidence
        return False, evidence

    if pack.status == "core":
        return True, evidence

    return False, evidence


def resolve_effective_packs(root: Path, manifest_path: Path | None = None) -> list[EffectiveCapabilityPack]:
    root = root.resolve()
    manifest_path = manifest_path or _default_manifest_path(root)
    overrides = load_manifest_overrides(manifest_path)
    results: list[EffectiveCapabilityPack] = []

    for pack in BUILTIN_PACKS.values():
        warnings: list[str] = []
        override = overrides.get(pack.id)
        enabled = False
        source = "inferred"
        evidence: list[str] = []
        override_reason = override.reason if override else None

        if pack.activation_mode == "always-on":
            enabled = True
            source = "core-default"
            if override and not override.enabled:
                warnings.append("always-on pack cannot be disabled; override ignored")
            elif override and override.enabled:
                warnings.append("always-on pack is already enabled by default")
        elif pack.activation_mode == "experimental-only":
            if override and override.enabled:
                enabled = True
                source = "experimental"
                evidence.append("explicit experimental opt-in")
            else:
                enabled = False
                source = "config" if override and not override.enabled else "inferred"
        else:
            if override is not None:
                enabled = override.enabled
                source = "config"
                evidence.append("explicit manifest override")
            else:
                enabled, heuristic_evidence = _heuristic_enabled(pack, root)
                evidence.extend(heuristic_evidence)
                source = "core-default" if pack.status == "core" else "inferred"

        results.append(
            EffectiveCapabilityPack(
                id=pack.id,
                purpose=pack.purpose,
                status=pack.status,
                activation_mode=pack.activation_mode,
                enabled=enabled,
                activation_source=source,
                affected_commands=list(pack.affected_commands),
                prerequisites=list(pack.prerequisites),
                owned_behaviors=list(pack.owned_behaviors),
                evidence=evidence,
                warnings=warnings,
                override_reason=override_reason,
            )
        )

    return results


def validate_registry(root: Path, manifest_path: Path | None = None) -> list[str]:
    issues: list[str] = []
    for definition in BUILTIN_PACKS.values():
        if definition.status not in VALID_PACK_STATUSES:
            issues.append(f"{definition.id}: invalid status '{definition.status}'")
        if definition.activation_mode not in VALID_ACTIVATION_MODES:
            issues.append(f"{definition.id}: invalid activation mode '{definition.activation_mode}'")
        if not definition.affected_commands:
            issues.append(f"{definition.id}: affected_commands must not be empty")
        if not definition.owned_behaviors:
            issues.append(f"{definition.id}: owned_behaviors must not be empty")
        if definition.status == "downstream" and definition.activation_mode == "always-on":
            issues.append(f"{definition.id}: downstream pack must not be always-on")

    manifest_path = manifest_path or _default_manifest_path(root.resolve())
    try:
        overrides = load_manifest_overrides(manifest_path)
        packs = resolve_effective_packs(root, manifest_path)
    except ValueError as exc:
        issues.append(str(exc))
    else:
        for pack_id, override in overrides.items():
            definition = BUILTIN_PACKS[pack_id]
            if definition.activation_mode == "always-on" and not override.enabled:
                issues.append(f"{pack_id}: always-on packs may not be disabled by manifest")
    return issues


def scaffold_manifest(root: Path, manifest_path: Path | None = None, force: bool = False) -> Path:
    root = root.resolve()
    manifest_path = manifest_path or _default_manifest_path(root)
    if manifest_path.exists() and not force:
        raise FileExistsError(f"Capability pack manifest already exists: {manifest_path}")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    template_path = Path(__file__).resolve().parent / "templates" / "capability-packs.example.json"
    if not template_path.exists():
        template_path = Path(__file__).resolve().parents[2] / "templates" / "capability-packs.example.json"
    if not template_path.exists():
        raise FileNotFoundError("Capability pack template not found in package or repository templates/")
    manifest_path.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")
    return manifest_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect Orca capability pack definitions and activation.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_shared_args(target: argparse.ArgumentParser) -> None:
        target.add_argument("--root", default=".", help="Repository root to inspect")
        target.add_argument("--manifest", help="Override manifest path (defaults to .specify/orca/capability-packs.json)")

    list_parser = subparsers.add_parser("list", help="List effective capability packs")
    add_shared_args(list_parser)
    list_parser.add_argument("--json", action="store_true", help="Render JSON output")

    show_parser = subparsers.add_parser("show", help="Show a single effective capability pack")
    add_shared_args(show_parser)
    show_parser.add_argument("pack_id", help="Capability pack identifier")
    show_parser.add_argument("--json", action="store_true", help="Render JSON output")

    validate_parser = subparsers.add_parser("validate", help="Validate the built-in registry and manifest overrides")
    add_shared_args(validate_parser)
    validate_parser.add_argument("--json", action="store_true", help="Render JSON output")

    scaffold_parser = subparsers.add_parser("scaffold", help="Write a starter capability pack manifest")
    add_shared_args(scaffold_parser)
    scaffold_parser.add_argument("--force", action="store_true", help="Overwrite an existing manifest")
    return parser


def _render_text(packs: list[EffectiveCapabilityPack]) -> str:
    lines: list[str] = []
    for pack in packs:
        status = "enabled" if pack.enabled else "disabled"
        lines.append(f"{pack.id}: {status} ({pack.activation_source}, {pack.activation_mode}, {pack.status})")
        lines.append(f"  purpose: {pack.purpose}")
        lines.append(f"  commands: {', '.join(pack.affected_commands)}")
        if pack.prerequisites:
            lines.append(f"  prerequisites: {', '.join(pack.prerequisites)}")
        if pack.evidence:
            lines.append(f"  evidence: {', '.join(pack.evidence)}")
        if pack.override_reason:
            lines.append(f"  override_reason: {pack.override_reason}")
        if pack.warnings:
            lines.append(f"  warnings: {', '.join(pack.warnings)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    manifest_path = Path(args.manifest).resolve() if args.manifest else None

    try:
        if args.command == "scaffold":
            path = scaffold_manifest(root, manifest_path=manifest_path, force=args.force)
            print(path)
            return 0

        if args.command == "validate":
            issues = validate_registry(root, manifest_path=manifest_path)
            if args.json:
                print(json.dumps({"valid": not issues, "issues": issues}, indent=2))
            else:
                if issues:
                    print("Capability pack validation failed:")
                    for issue in issues:
                        print(f"- {issue}")
                else:
                    print("Capability pack validation passed.")
            return 1 if issues else 0

        packs = resolve_effective_packs(root, manifest_path=manifest_path)
        if args.command == "show":
            matching = [pack for pack in packs if pack.id == args.pack_id]
            if not matching:
                print(f"Unknown capability pack: {args.pack_id}", file=sys.stderr)
                return 1
            if args.json:
                print(json.dumps(matching[0].to_dict(), indent=2))
            else:
                print(_render_text(matching))
            return 0

        if args.json:
            print(json.dumps([pack.to_dict() for pack in packs], indent=2))
        else:
            print(_render_text(packs))
        return 0
    except (FileExistsError, FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
