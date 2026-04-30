"""Apply executor: read manifest -> snapshot -> apply surfaces -> write state."""
from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path

from orca.core.adoption.manifest import Manifest, load_manifest
from orca.core.adoption.policies.claude_md import apply_section
from orca.core.adoption.snapshot import snapshot_files
from orca.core.adoption.state import AdoptionState, FileEntry, write_state


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

    backup_dir = repo_root / manifest.reversal.backup_dir / timestamp

    surfaces = _enumerate_surfaces(repo_root, manifest)
    file_entries = snapshot_files(
        [path for path, _ in surfaces], backup_dir, repo_root=repo_root
    )

    for path, payload in surfaces:
        _apply_surface(path, payload, manifest)

    # Update post_hash for each entry
    final_entries = []
    for entry in file_entries:
        full = repo_root / entry.rel_path
        post = _hash_bytes(full.read_bytes()) if full.exists() else ""
        final_entries.append(
            FileEntry(rel_path=entry.rel_path, pre_hash=entry.pre_hash, post_hash=post)
        )

    state = AdoptionState(
        manifest_hash=manifest_hash,
        applied_at=applied_at,
        backup_timestamp=timestamp,
        files=final_entries,
    )
    write_state(state, repo_root / ".orca" / "adoption-state.json")
    return state


def _enumerate_surfaces(
    repo_root: Path, manifest: Manifest
) -> list[tuple[Path, str]]:
    """Return (path, payload) pairs for each surface to apply."""
    surfaces: list[tuple[Path, str]] = []
    if manifest.claude_md.policy != "skip":
        agents_md = repo_root / manifest.host.agents_md_path
        payload = _build_orca_section(manifest)
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
        # ORCA.md gets the content; AGENTS.md gets a one-line pointer.
        orca_md = path.parent / "ORCA.md"
        orca_md.write_text(payload)
        if not path.exists() or "ORCA.md" not in path.read_text():
            existing = path.read_text() if path.exists() else ""
            path.write_text(existing.rstrip("\n") + "\nSee `ORCA.md` for orca details.\n")


def _hash_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()
