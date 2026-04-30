"""Wizard for `orca adopt`: detection + (optionally interactive) prompts.

Builds a default `Manifest` based on host detection (or explicit `--host`
override) and writes it to `<repo_root>/.orca/adoption.toml`. The wizard
is intentionally non-interactive when invoked with `--force` so tests
and CI can exercise it without stdin mocking.
"""
from __future__ import annotations

from pathlib import Path

from orca.core.adoption.manifest import (
    SUPPORTED_HOST_SYSTEMS,
    SUPPORTED_SCHEMA_VERSION,
    ClaudeMdConfig,
    ConstitutionConfig,
    HostConfig,
    Manifest,
    OrcaConfig,
    ReversalConfig,
    SlashCommandsConfig,
    write_manifest,
)
from orca.core.host_layout.detect import detect

DEFAULT_CAPABILITIES = [
    "cross-agent-review",
    "citation-validator",
    "contradiction-detector",
    "completion-gate",
    "worktree-overlap-check",
    "flow-state-projection",
]
DEFAULT_SLASH_COMMANDS = [
    "review-spec", "review-code", "review-pr", "gate", "cite", "doctor",
]

_HOST_DEFAULTS: dict[str, dict[str, str | None]] = {
    "spec-kit": {
        "feature_dir_pattern": "specs/{feature_id}",
        "agents_md_path": "CLAUDE.md",
        "review_artifact_dir": "specs",
        "constitution_path": ".specify/memory/constitution.md",
    },
    "openspec": {
        "feature_dir_pattern": "openspec/changes/{feature_id}",
        "agents_md_path": "AGENTS.md",
        "review_artifact_dir": "openspec/changes",
        "constitution_path": None,
    },
    "superpowers": {
        "feature_dir_pattern": "docs/superpowers/specs/{feature_id}",
        "agents_md_path": "AGENTS.md",
        "review_artifact_dir": "docs/superpowers/reviews",
        "constitution_path": "docs/superpowers/constitution.md",
    },
    "bare": {
        "feature_dir_pattern": "docs/orca-specs/{feature_id}",
        "agents_md_path": "AGENTS.md",
        "review_artifact_dir": "docs/orca-specs/_reviews",
        "constitution_path": None,
    },
}


def build_default_manifest(
    repo_root: Path,
    *,
    host_override: str | None = None,
) -> Manifest:
    """Construct a Manifest using detection + sensible defaults."""
    if host_override is not None:
        if host_override not in SUPPORTED_HOST_SYSTEMS:
            raise ValueError(
                f"--host={host_override!r} not in {sorted(SUPPORTED_HOST_SYSTEMS)}"
            )
        system = host_override
    else:
        layout = detect(repo_root)
        # Map adapter type back to host_system string.
        from orca.core.host_layout import (
            BareLayout,
            OpenSpecLayout,
            SpecKitLayout,
            SuperpowersLayout,
        )
        type_map = {
            BareLayout: "bare",
            OpenSpecLayout: "openspec",
            SpecKitLayout: "spec-kit",
            SuperpowersLayout: "superpowers",
        }
        system = type_map[type(layout)]

    defaults = _HOST_DEFAULTS[system]
    host = HostConfig(
        system=system,  # type: ignore[arg-type]
        feature_dir_pattern=defaults["feature_dir_pattern"],  # type: ignore[arg-type]
        agents_md_path=defaults["agents_md_path"],  # type: ignore[arg-type]
        review_artifact_dir=defaults["review_artifact_dir"],  # type: ignore[arg-type]
        constitution_path=defaults["constitution_path"],
    )

    return Manifest(
        schema_version=SUPPORTED_SCHEMA_VERSION,
        host=host,
        orca=OrcaConfig(
            state_dir=".orca",
            installed_capabilities=list(DEFAULT_CAPABILITIES),
        ),
        slash_commands=SlashCommandsConfig(
            namespace="orca",
            enabled=list(DEFAULT_SLASH_COMMANDS),
            disabled=[],
        ),
        claude_md=ClaudeMdConfig(policy="section"),
        constitution=ConstitutionConfig(policy="respect-existing"),
        reversal=ReversalConfig(backup_dir=".orca/adoption-backup"),
    )


def run_adopt(
    *,
    repo_root: Path,
    host_override: str | None = None,
    plan_only: bool = False,
    force: bool = False,
    reset: bool = False,
) -> Path:
    """Build manifest, write to disk, return path to manifest.

    With --force, prompts are skipped (defaults used).
    With --reset, existing manifest is backed up and regenerated.
    Without --plan-only, the caller is expected to also run apply.
    """
    manifest_path = repo_root / ".orca" / "adoption.toml"

    if manifest_path.exists() and not reset and not force:
        raise FileExistsError(
            f"manifest already exists at {manifest_path}; pass --reset to regenerate"
        )

    if manifest_path.exists() and (reset or force):
        # Back up before overwriting under either flag. force was
        # previously a silent overwrite; per PR #70 review, both flags
        # now produce a recoverable .toml.backup.
        backup = manifest_path.with_suffix(".toml.backup")
        manifest_path.replace(backup)

    manifest = build_default_manifest(repo_root, host_override=host_override)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    write_manifest(manifest, manifest_path)
    return manifest_path
