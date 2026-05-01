"""Apply executor: read manifest -> snapshot -> apply surfaces -> write state."""
from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path

from orca.core.adoption.manifest import Manifest, load_manifest
from orca.core.adoption.policies.claude_md import apply_section
from orca.core.adoption.snapshot import snapshot_files
from orca.core.adoption.state import AdoptionState, FileEntry, load_state, write_state


def apply(*, repo_root: Path) -> AdoptionState:
    """Execute the manifest at <repo_root>/.orca/adoption.toml.

    Idempotent: re-running with no manifest changes produces no file diffs
    (state.json is rewritten with same content).
    """
    manifest_path = repo_root / ".orca" / "adoption.toml"
    manifest = load_manifest(manifest_path)
    manifest_hash = _hash_bytes(manifest_path.read_bytes())

    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    applied_at = dt.datetime.now(dt.timezone.utc).isoformat()

    # Idempotency guard: if state.json exists with matching manifest_hash
    # and all surface files already match recorded post_hash, this apply is
    # a no-op. Preserve the original backup_timestamp so revert can still
    # restore the true pre-apply state. (Required for revert idempotency.)
    state_path = repo_root / ".orca" / "adoption-state.json"
    surfaces = _enumerate_surfaces(repo_root, manifest)
    prior_state = load_state(state_path) if state_path.exists() else None
    if prior_state is not None and prior_state.manifest_hash == manifest_hash:
        rel_to_post = {f.rel_path: f.post_hash for f in prior_state.files}
        all_match = True
        for path, _ in surfaces:
            rel = str(path.relative_to(repo_root))
            if rel not in rel_to_post:
                all_match = False
                break
            current = _hash_bytes(path.read_bytes()) if path.exists() else ""
            if current != rel_to_post[rel]:
                all_match = False
                break
        if all_match:
            return prior_state

    backup_dir = repo_root / manifest.reversal.backup_dir / timestamp

    snapshotted = snapshot_files(
        [path for path, _ in surfaces], backup_dir, repo_root=repo_root
    )
    pre_hash_by_rel = {e.rel_path: e.pre_hash for e in snapshotted}

    for path, payload in surfaces:
        _apply_surface(path, payload, manifest)

    # Track every surface in state.json (even ones that didn't pre-exist)
    # so revert can either restore from backup or delete the orca-created
    # file. snapshot_files() only emits entries for files present pre-apply;
    # for files orca created from scratch, pre_hash is empty.
    final_entries = []
    for path, _ in surfaces:
        try:
            rel = str(path.relative_to(repo_root))
        except ValueError:
            continue
        post = _hash_bytes(path.read_bytes()) if path.exists() else ""
        final_entries.append(
            FileEntry(
                rel_path=rel,
                pre_hash=pre_hash_by_rel.get(rel, ""),
                post_hash=post,
            )
        )

    state = AdoptionState(
        manifest_hash=manifest_hash,
        applied_at=applied_at,
        backup_timestamp=timestamp,
        files=final_entries,
    )
    write_state(state, repo_root / ".orca" / "adoption-state.json")

    # Worktree manager is default-on per spec; future schema bump will gate
    # this on `[orca] enabled_features`. For v1 we always seed the config.
    from orca.core.worktrees.config import write_default_config
    write_default_config(repo_root)

    return state


_NAMESPACE_POINTER = "See `ORCA.md` for orca details.\n"


def _enumerate_surfaces(
    repo_root: Path, manifest: Manifest
) -> list[tuple[Path, str]]:
    """Return (path, payload) pairs for each surface to apply.

    For policy=namespace this enumerates BOTH ORCA.md (full content) and
    AGENTS.md (pointer line). Both are tracked in state.json so revert
    can restore pre-apply versions or remove orca-created ones.
    """
    surfaces: list[tuple[Path, str]] = []
    if manifest.claude_md.policy == "skip":
        return surfaces
    agents_md = repo_root / manifest.host.agents_md_path
    payload = _build_orca_section(manifest)
    if manifest.claude_md.policy == "namespace":
        orca_md = agents_md.parent / "ORCA.md"
        surfaces.append((orca_md, payload))
        surfaces.append((agents_md, _NAMESPACE_POINTER))
    else:
        surfaces.append((agents_md, payload))
    return surfaces


def _build_orca_section(manifest: Manifest) -> str:
    lines = ["Orca is installed in this repo.", ""]
    lines.append(
        f"- Capabilities: {', '.join(manifest.orca.installed_capabilities)}"
    )
    for cmd in manifest.slash_commands.enabled:
        if manifest.slash_commands.namespace:
            lines.append(f"- /{manifest.slash_commands.namespace}:{cmd}")
        else:
            lines.append(f"- /{cmd}")
    return "\n".join(lines) + "\n"


def _apply_surface(path: Path, payload: str, manifest: Manifest) -> None:
    if manifest.claude_md.policy == "section":
        apply_section(path, payload, section_marker=manifest.claude_md.section_marker)
    elif manifest.claude_md.policy == "append":
        existing = path.read_text() if path.exists() else ""
        path.write_text(existing.rstrip("\n") + "\n\n" + payload)
    elif manifest.claude_md.policy == "namespace":
        if path.name == "ORCA.md":
            path.write_text(payload)
        else:
            existing = path.read_text() if path.exists() else ""
            if "ORCA.md" not in existing:
                sep = "\n" if existing and not existing.endswith("\n") else ""
                path.write_text(existing + sep + payload)


def _hash_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()
