"""Manifest schema, TOML I/O, validation.

The manifest at `.orca/adoption.toml` is the source of truth for an
adopted orca install. See spec 015 for the schema rationale.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

import tomli_w

SUPPORTED_SCHEMA_VERSION = 1
SUPPORTED_HOST_SYSTEMS = frozenset({"spec-kit", "openspec", "superpowers", "bare"})
SUPPORTED_CLAUDE_MD_POLICIES = frozenset({"append", "section", "namespace", "skip"})
SUPPORTED_CONSTITUTION_POLICIES = frozenset({"respect-existing", "merge", "skip"})
NAMESPACE_RE = re.compile(r"^[a-z][a-z0-9-]*$")
RESERVED_NAMESPACE_PREFIXES = ("speckit-", "claude-")


class ManifestError(ValueError):
    """Raised when manifest schema is invalid."""


@dataclass(frozen=True)
class HostConfig:
    system: Literal["spec-kit", "openspec", "superpowers", "bare"]
    feature_dir_pattern: str
    agents_md_path: str
    review_artifact_dir: str
    constitution_path: str | None = None


@dataclass(frozen=True)
class OrcaConfig:
    state_dir: str
    installed_capabilities: list[str]


@dataclass(frozen=True)
class SlashCommandsConfig:
    namespace: str
    enabled: list[str]
    disabled: list[str]


@dataclass(frozen=True)
class ClaudeMdConfig:
    policy: Literal["append", "section", "namespace", "skip"]
    section_marker: str = "## Orca"
    namespace_prefix: str = "orca:"


@dataclass(frozen=True)
class ConstitutionConfig:
    policy: Literal["respect-existing", "merge", "skip"]


@dataclass(frozen=True)
class ReversalConfig:
    backup_dir: str


@dataclass(frozen=True)
class Manifest:
    schema_version: int
    host: HostConfig
    orca: OrcaConfig
    slash_commands: SlashCommandsConfig
    claude_md: ClaudeMdConfig
    constitution: ConstitutionConfig
    reversal: ReversalConfig


def _require(d: dict[str, Any], key: str, ctx: str) -> Any:
    if key not in d:
        raise ManifestError(f"missing {ctx}.{key}")
    return d[key]


def load_manifest(path: Path) -> Manifest:
    """Read and validate a manifest from disk.

    Raises ManifestError on any schema violation; the message names the
    specific field that failed.
    """
    raw = path.read_bytes()
    if not raw:
        raise ManifestError("manifest file is empty")
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"TOML parse failed: {exc}") from exc

    schema_version = _require(data, "schema_version", "")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ManifestError(
            f"schema_version={schema_version} not supported; "
            f"this orca expects {SUPPORTED_SCHEMA_VERSION}"
        )

    host_raw = _require(data, "host", "")
    host_system = _require(host_raw, "system", "host")
    if host_system not in SUPPORTED_HOST_SYSTEMS:
        raise ManifestError(
            f"host.system={host_system!r} not in {sorted(SUPPORTED_HOST_SYSTEMS)}"
        )
    pattern = _require(host_raw, "feature_dir_pattern", "host")
    if "{feature_id}" not in pattern:
        raise ManifestError(
            "host.feature_dir_pattern must contain literal {feature_id}"
        )

    host = HostConfig(
        system=host_system,
        feature_dir_pattern=pattern,
        agents_md_path=_require(host_raw, "agents_md_path", "host"),
        review_artifact_dir=_require(host_raw, "review_artifact_dir", "host"),
        constitution_path=host_raw.get("constitution_path"),
    )

    orca_raw = _require(data, "orca", "")
    orca = OrcaConfig(
        state_dir=_require(orca_raw, "state_dir", "orca"),
        installed_capabilities=list(_require(orca_raw, "installed_capabilities", "orca")),
    )

    sc_raw = _require(data, "slash_commands", "")
    namespace = _require(sc_raw, "namespace", "slash_commands")
    if not NAMESPACE_RE.match(namespace):
        raise ManifestError(
            f"slash_commands.namespace={namespace!r} must match [a-z][a-z0-9-]*"
        )
    if any(namespace.startswith(p) for p in RESERVED_NAMESPACE_PREFIXES):
        raise ManifestError(
            f"slash_commands.namespace={namespace!r} starts with reserved prefix"
        )

    slash_commands = SlashCommandsConfig(
        namespace=namespace,
        enabled=list(_require(sc_raw, "enabled", "slash_commands")),
        disabled=list(_require(sc_raw, "disabled", "slash_commands")),
    )

    cm_raw = _require(data, "claude_md", "")
    cm_policy = _require(cm_raw, "policy", "claude_md")
    if cm_policy not in SUPPORTED_CLAUDE_MD_POLICIES:
        raise ManifestError(
            f"claude_md.policy={cm_policy!r} not in {sorted(SUPPORTED_CLAUDE_MD_POLICIES)}"
        )
    claude_md = ClaudeMdConfig(
        policy=cm_policy,
        section_marker=cm_raw.get("section_marker", "## Orca"),
        namespace_prefix=cm_raw.get("namespace_prefix", "orca:"),
    )

    co_raw = _require(data, "constitution", "")
    co_policy = _require(co_raw, "policy", "constitution")
    if co_policy not in SUPPORTED_CONSTITUTION_POLICIES:
        raise ManifestError(
            f"constitution.policy={co_policy!r} not in {sorted(SUPPORTED_CONSTITUTION_POLICIES)}"
        )
    constitution = ConstitutionConfig(policy=co_policy)

    rev_raw = _require(data, "reversal", "")
    reversal = ReversalConfig(
        backup_dir=_require(rev_raw, "backup_dir", "reversal"),
    )

    return Manifest(
        schema_version=schema_version,
        host=host,
        orca=orca,
        slash_commands=slash_commands,
        claude_md=claude_md,
        constitution=constitution,
        reversal=reversal,
    )


def write_manifest(manifest: Manifest, path: Path) -> None:
    """Serialize manifest to TOML; atomic write."""
    payload: dict[str, Any] = {
        "schema_version": manifest.schema_version,
        "host": {
            "system": manifest.host.system,
            "feature_dir_pattern": manifest.host.feature_dir_pattern,
            "agents_md_path": manifest.host.agents_md_path,
            "review_artifact_dir": manifest.host.review_artifact_dir,
        },
        "orca": {
            "state_dir": manifest.orca.state_dir,
            "installed_capabilities": list(manifest.orca.installed_capabilities),
        },
        "slash_commands": {
            "namespace": manifest.slash_commands.namespace,
            "enabled": list(manifest.slash_commands.enabled),
            "disabled": list(manifest.slash_commands.disabled),
        },
        "claude_md": {
            "policy": manifest.claude_md.policy,
            "section_marker": manifest.claude_md.section_marker,
            "namespace_prefix": manifest.claude_md.namespace_prefix,
        },
        "constitution": {"policy": manifest.constitution.policy},
        "reversal": {"backup_dir": manifest.reversal.backup_dir},
    }
    if manifest.host.constitution_path is not None:
        payload["host"]["constitution_path"] = manifest.host.constitution_path

    encoded = tomli_w.dumps(payload).encode("utf-8")
    tmp = path.with_suffix(path.suffix + ".partial")
    tmp.write_bytes(encoded)
    tmp.replace(path)
