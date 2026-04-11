from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from speckit_orca.flow_state import STAGE_ORDER, compute_flow_state

REGISTRY_SCHEMA_VERSION = "1.0"
REGISTRY_LOCK_TIMEOUT_SECONDS = 5.0
STATUS_PRECEDENCE = {
    "registered": 0,
    "active": 1,
    "review_ready": 2,
    "pr_ready": 3,
    "blocked": 4,
    "archived": 5,
}
EVENT_TYPES = {
    "instruction",
    "ack",
    "status",
    "blocker",
    "question",
    "approval_needed",
    "handoff",
    "shutdown",
}
EVENT_ACK_STATES = {"new", "acknowledged", "resolved"}
OWNERSHIP_TYPES = {"human", "agent", "shared", "unassigned"}
DEPLOYMENT_KINDS = {"tmux", "direct-session"}
DEPLOYMENT_STATES = {"requested", "running", "detached", "missing", "stopped"}
DEPENDENCY_TARGET_KINDS = {"lane_exists", "stage_reached", "review_ready", "pr_ready", "merged"}
DEPENDENCY_STRENGTHS = {"soft", "hard"}
DEPENDENCY_STATES = {"active", "satisfied", "waived"}
ASSIGNMENT_STATES = {"active", "released", "abandoned"}
DELEGATED_STATUSES = {"pending", "in_progress", "completed", "failed"}
ACTIVE_DEPLOYMENT_STATES = {"requested", "running", "detached"}


@dataclass
class EventEnvelope:
    id: str
    timestamp: str
    lane_id: str
    sender: str
    recipient: str
    type: str
    payload: str | dict[str, Any]
    ack_status: str = "new"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LaneDependency:
    dependency_id: str
    lane_id: str
    depends_on_lane_id: str
    strength: str
    target_kind: str
    target_value: str | None
    state: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LaneAssignment:
    lane_id: str
    owner_type: str
    owner_id: str | None
    assigned_at: str
    released_at: str | None
    assignment_state: str
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LaneDeployment:
    deployment_id: str
    lane_id: str
    deployment_kind: str
    session_name: str
    state: str
    launched_by: str | None
    attached_at: str | None
    last_seen_at: str | None
    worker_cli: str | None
    notes: str
    reports_to: str = "matriarch"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LaneRecord:
    schema_version: str
    lane_id: str
    spec_id: str
    title: str
    branch: str | None
    worktree_path: str | None
    registry_revision: int
    lifecycle_state: str
    owner_type: str
    owner_id: str | None
    stage: str | None
    readiness: str | None
    dependency_ids: list[str]
    deployment_id: str | None
    mailbox_path: str
    status_reason: str
    created_at: str
    updated_at: str
    assignment_history: list[dict[str, Any]] = field(default_factory=list)
    dependencies: list[dict[str, Any]] = field(default_factory=list)
    deployment: dict[str, Any] | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DelegatedWorkItem:
    task_id: str
    lane_id: str
    title: str
    status: str
    claimed_by: str | None
    claim_token: str | None
    claimed_at: str | None
    released_at: str | None
    completed_at: str | None
    result_ref: str | None
    error_ref: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MatriarchPaths:
    repo_root: Path

    @property
    def root(self) -> Path:
        return self.repo_root / ".specify" / "orca" / "matriarch"

    @property
    def registry_path(self) -> Path:
        return self.root / "registry.json"

    @property
    def lock_path(self) -> Path:
        return self.root / "registry.lock"

    @property
    def lanes_dir(self) -> Path:
        return self.root / "lanes"

    @property
    def mailbox_dir(self) -> Path:
        return self.root / "mailbox"

    @property
    def reports_dir(self) -> Path:
        return self.root / "reports"

    @property
    def delegated_dir(self) -> Path:
        return self.root / "delegated"

    def lane_path(self, lane_id: str) -> Path:
        _validate_lane_id(lane_id)
        return self.lanes_dir / f"{lane_id}.json"

    def mailbox_root(self, lane_id: str) -> Path:
        _validate_lane_id(lane_id)
        return self.mailbox_dir / lane_id

    def mailbox_inbound(self, lane_id: str) -> Path:
        return self.mailbox_root(lane_id) / "inbound.jsonl"

    def mailbox_outbound(self, lane_id: str) -> Path:
        return self.mailbox_root(lane_id) / "outbound.jsonl"

    def reports_path(self, lane_id: str) -> Path:
        _validate_lane_id(lane_id)
        return self.reports_dir / lane_id / "events.jsonl"

    def delegated_path(self, lane_id: str) -> Path:
        _validate_lane_id(lane_id)
        return self.delegated_dir / f"{lane_id}.json"

    def delegated_lock_path(self, lane_id: str) -> Path:
        _validate_lane_id(lane_id)
        return self.delegated_dir / f"{lane_id}.lock"


class MatriarchError(RuntimeError):
    pass


# Matches the anchored filesystem-safe constraint in
# specs/010-orca-matriarch/contracts/lane-mailbox.md and event-envelope.md.
# Validators MUST do a full-string match, so lane ids and spec ids cannot
# traverse or escape the .specify/orca/ tree when concatenated into paths.
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _validate_lane_id(lane_id: str) -> str:
    if not isinstance(lane_id, str) or not _SAFE_ID_RE.fullmatch(lane_id):
        raise MatriarchError(
            f"Invalid lane_id {lane_id!r}: must match ^[A-Za-z0-9._-]+$"
        )
    return lane_id


def _validate_spec_id(spec_id: str) -> str:
    if not isinstance(spec_id, str) or not _SAFE_ID_RE.fullmatch(spec_id):
        raise MatriarchError(
            f"Invalid spec_id {spec_id!r}: must match ^[A-Za-z0-9._-]+$"
        )
    return spec_id


def _now_rfc3339() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _repo_root(start: Path | str | None = None) -> Path:
    candidate = Path(start).resolve() if start is not None else Path.cwd().resolve()
    for current in (candidate, *candidate.parents):
        if (current / ".git").exists() or (current / ".specify").exists():
            return current
    raise MatriarchError("Could not determine repository root.")


def _git_current_branch(repo_root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    branch = completed.stdout.strip()
    if branch == "HEAD":
        return None
    return branch or None


def _slug_title(spec_id: str) -> str:
    parts = spec_id.split("-", 1)
    if len(parts) == 2:
        return parts[1].replace("-", " ").strip()
    return spec_id.replace("-", " ").strip()


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    _ensure_parent(path)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent, encoding="utf-8") as tmp:
        json.dump(payload, tmp, indent=2)
        tmp.write("\n")
        temp_name = tmp.name
    Path(temp_name).replace(path)


def _read_json(path: Path, default: dict[str, Any] | list[Any] | None = None) -> Any:
    if not path.exists():
        return {} if default is None else default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MatriarchError(f"Invalid JSON: {path}") from exc


def _parse_payload(payload: str) -> str | dict[str, Any]:
    """Coerce a CLI payload argument to the event envelope's declared shape.

    The event envelope contract (010 event-envelope.md) defines `payload` as
    "string or structured object" — dict, not list. If the caller passes a
    JSON array, we preserve it as the original string so downstream senders
    see a single argv-passable payload rather than an unexpected list type.
    """
    text = payload.strip()
    if not text:
        return ""
    if text[0] != "{":
        return payload
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        return payload
    if isinstance(decoded, dict):
        return decoded
    return payload


def _acquire_lock(lock_path: Path, timeout_seconds: float = REGISTRY_LOCK_TIMEOUT_SECONDS) -> Any:
    _ensure_parent(lock_path)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    start = time.monotonic()
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except BlockingIOError:
            if time.monotonic() - start >= timeout_seconds:
                os.close(fd)
                raise MatriarchError(f"Timed out acquiring Matriarch registry lock: {lock_path}")
            time.sleep(0.05)


def _release_lock(fd: Any) -> None:
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _ensure_runtime_paths(paths: MatriarchPaths) -> None:
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.lanes_dir.mkdir(parents=True, exist_ok=True)
    paths.mailbox_dir.mkdir(parents=True, exist_ok=True)
    paths.reports_dir.mkdir(parents=True, exist_ok=True)
    paths.delegated_dir.mkdir(parents=True, exist_ok=True)


def _load_registry(paths: MatriarchPaths) -> dict[str, Any]:
    _ensure_runtime_paths(paths)
    if not paths.registry_path.exists():
        payload = {
            "schema_version": REGISTRY_SCHEMA_VERSION,
            "repo_name": paths.repo_root.name,
            "revision": 0,
            "lanes": [],
            "updated_at": _now_rfc3339(),
        }
        _write_json_atomic(paths.registry_path, payload)
        return payload
    registry = _read_json(paths.registry_path)
    if not isinstance(registry, dict):
        raise MatriarchError(f"Invalid Matriarch registry: {paths.registry_path}")
    registry.setdefault("schema_version", REGISTRY_SCHEMA_VERSION)
    registry.setdefault("repo_name", paths.repo_root.name)
    registry.setdefault("revision", 0)
    registry.setdefault("lanes", [])
    registry.setdefault("updated_at", _now_rfc3339())
    return registry


def _mutate_registry(
    paths: MatriarchPaths,
    mutator: Any,
    *,
    expected_revision: int | None = None,
) -> tuple[dict[str, Any], Any]:
    fd = _acquire_lock(paths.lock_path)
    try:
        registry = _load_registry(paths)
        revision = int(registry.get("revision", 0))
        if expected_revision is not None and revision != expected_revision:
            raise MatriarchError(
                f"Stale registry write rejected: expected revision {expected_revision}, found {revision}"
            )
        result = mutator(registry)
        registry["revision"] = revision + 1
        registry["updated_at"] = _now_rfc3339()
        _write_json_atomic(paths.registry_path, registry)
        return registry, result
    finally:
        _release_lock(fd)


def _ensure_lane_registered(registry: dict[str, Any], lane_id: str) -> None:
    lanes = registry.setdefault("lanes", [])
    if lane_id not in lanes:
        raise MatriarchError(f"Lane is not registered: {lane_id}")


def _commit_lane_record(
    paths: MatriarchPaths,
    record: LaneRecord,
    *,
    expected_revision: int | None,
    register_lane: bool = False,
) -> LaneRecord:
    fd = _acquire_lock(paths.lock_path)
    try:
        registry = _load_registry(paths)
        revision = int(registry.get("revision", 0))
        lanes = registry.setdefault("lanes", [])
        if register_lane:
            if record.lane_id in lanes:
                raise MatriarchError(f"Lane already exists in registry: {record.lane_id}")
            if paths.lane_path(record.lane_id).exists():
                raise MatriarchError(f"Lane record already exists on disk: {record.lane_id}")
            lanes.append(record.lane_id)
        else:
            _ensure_lane_registered(registry, record.lane_id)
            current_lane_revision = None
            if paths.lane_path(record.lane_id).exists():
                current_payload = _read_json(paths.lane_path(record.lane_id))
                if isinstance(current_payload, dict):
                    current_lane_revision = int(current_payload.get("registry_revision", 0))
            if expected_revision is not None and current_lane_revision != expected_revision:
                raise MatriarchError(
                    "Stale lane write rejected: "
                    f"expected revision {expected_revision}, found {current_lane_revision}"
                )
        registry["revision"] = revision + 1
        registry["updated_at"] = _now_rfc3339()
        record.registry_revision = int(registry["revision"])
        # Write the registry index BEFORE the lane file.  If we crash between
        # the two atomic renames the registry will list the lane but the lane
        # file will be missing; list_lanes() surfaces that as an error entry,
        # giving the operator a visible signal.  The reverse order would leave
        # a silent orphan lane file that blocks every subsequent registration
        # attempt for the same spec_id.
        _write_json_atomic(paths.registry_path, registry)
        _write_lane(paths, record)
        return record
    finally:
        _release_lock(fd)


def _event_id(lane_id: str, event_type: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{lane_id}-{event_type}-{timestamp}-{secrets.token_hex(4)}"


def _validate_event_type(event_type: str) -> None:
    if event_type not in EVENT_TYPES:
        raise MatriarchError(f"Unsupported event type: {event_type}")


def _append_event(path: Path, event: EventEnvelope) -> None:
    _ensure_parent(path)
    with path.open("a", encoding="utf-8") as handle:
        # Serialise concurrent appenders (multiple agents writing the same lane).
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            handle.write(json.dumps(event.to_dict(), sort_keys=True))
            handle.write("\n")
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _feature_dir(paths: MatriarchPaths, spec_id: str) -> Path:
    _validate_spec_id(spec_id)
    return paths.repo_root / "specs" / spec_id


def _flow_summary(paths: MatriarchPaths, spec_id: str) -> dict[str, Any]:
    feature_dir = _feature_dir(paths, spec_id)
    if not feature_dir.exists():
        return {
            "current_stage": None,
            "next_step": None,
            "review_milestones": [],
            "ambiguities": [],
            "evidence_summary": [],
        }
    result = compute_flow_state(feature_dir, repo_root=paths.repo_root)
    return result.to_dict()


def _review_status_map(flow_summary: dict[str, Any]) -> dict[str, str]:
    return {
        item["review_type"]: item["status"]
        for item in flow_summary.get("review_milestones", [])
        if isinstance(item, dict) and item.get("review_type")
    }


def _load_worktree_context(paths: MatriarchPaths, spec_id: str) -> dict[str, Any]:
    worktree_root = paths.repo_root / ".specify" / "orca" / "worktrees"
    registry_path = worktree_root / "registry.json"
    if not registry_path.exists():
        return {}
    registry = _read_json(registry_path)
    if not isinstance(registry, dict):
        return {}
    for lane_id in registry.get("lanes", []):
        lane_path = worktree_root / f"{lane_id}.json"
        if not lane_path.exists():
            continue
        lane = _read_json(lane_path)
        if not isinstance(lane, dict):
            continue
        if lane.get("feature") == spec_id or lane.get("id") == spec_id:
            return lane
    return {}


def _derive_effective_state(record: LaneRecord, flow_summary: dict[str, Any]) -> tuple[str, str]:
    hard_blockers = [
        item for item in record.dependencies if item.get("strength") == "hard" and item.get("state") == "active"
    ]
    if record.lifecycle_state == "archived":
        return "archived", record.status_reason or "Lane archived."
    if hard_blockers:
        return "blocked", "Hard dependencies remain unsatisfied."

    review_milestones = _review_status_map(flow_summary)
    stage = flow_summary.get("current_stage")
    if review_milestones.get("pr") == "complete":
        return "pr_ready", "PR review evidence is complete."
    if stage in {"code-review", "cross-review", "pr-review", "self-review"}:
        return "review_ready", "Implementation evidence is complete enough for review."
    if record.owner_type != "unassigned" or stage:
        return "active", "Lane has active owner or progress."
    return "registered", "Lane registered without active owner."


def _load_lane(paths: MatriarchPaths, lane_id: str) -> LaneRecord:
    lane_path = paths.lane_path(lane_id)
    if not lane_path.exists():
        raise MatriarchError(f"Unknown lane: {lane_id}")
    payload = _read_json(lane_path)
    if not isinstance(payload, dict):
        raise MatriarchError(f"Invalid lane record: {lane_path}")
    return LaneRecord(**payload)


def _write_lane(paths: MatriarchPaths, record: LaneRecord) -> None:
    payload = record.to_dict()
    _write_json_atomic(paths.lane_path(record.lane_id), payload)


def _current_worktree_path(paths: MatriarchPaths) -> str | None:
    current = Path.cwd().resolve()
    try:
        current.relative_to(paths.repo_root.resolve())
    except ValueError:
        return str(paths.repo_root.resolve())
    return str(current.resolve())


def _merged_base_ref(paths: MatriarchPaths) -> str | None:
    candidates = ("origin/main", "main", "origin/master", "master")
    for candidate in candidates:
        completed = subprocess.run(
            ["git", "-C", str(paths.repo_root), "rev-parse", "--verify", candidate],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0:
            return candidate
    return None


def _is_branch_merged(paths: MatriarchPaths, branch: str | None) -> bool:
    if not branch:
        return False
    base_ref = _merged_base_ref(paths)
    if not base_ref:
        return False
    completed = subprocess.run(
        ["git", "-C", str(paths.repo_root), "branch", "--format=%(refname:short)", "--merged", base_ref],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return False
    merged_branches = {line.strip() for line in completed.stdout.splitlines() if line.strip()}
    return branch in merged_branches


def _evaluate_dependency_state(
    paths: MatriarchPaths,
    dependency: dict[str, Any],
) -> tuple[str, str]:
    current_state = dependency.get("state", "active")
    if current_state == "waived":
        return "waived", "Dependency waived."

    target_lane_id = dependency["depends_on_lane_id"]
    upstream_path = paths.lane_path(target_lane_id)
    if not upstream_path.exists():
        return "active", f"Upstream lane is not registered: {target_lane_id}"

    upstream = _load_lane(paths, target_lane_id)
    upstream_flow = _flow_summary(paths, upstream.spec_id)
    target_kind = dependency["target_kind"]
    target_value = dependency.get("target_value")

    if target_kind == "lane_exists":
        return "satisfied", "Upstream lane exists."
    if target_kind == "stage_reached":
        current_stage = upstream_flow.get("current_stage")
        if current_stage and current_stage not in STAGE_ORDER:
            return "active", f"Upstream reported unknown stage {current_stage!r}."
        if target_value not in STAGE_ORDER:
            return "active", f"Dependency target_value {target_value!r} is not a known stage; treating as unsatisfied."
        if current_stage and STAGE_ORDER.index(current_stage) >= STAGE_ORDER.index(str(target_value)):
            return "satisfied", f"Upstream reached stage {current_stage}."
        return "active", f"Waiting for upstream stage {target_value}."

    effective_state, _ = _derive_effective_state(upstream, upstream_flow)
    if target_kind == "review_ready":
        if effective_state in {"review_ready", "pr_ready"}:
            return "satisfied", f"Upstream lane is {effective_state}."
        return "active", "Waiting for upstream review readiness."
    if target_kind == "pr_ready":
        if effective_state == "pr_ready":
            return "satisfied", f"Upstream lane is {effective_state}."
        return "active", "Waiting for upstream PR readiness."
    if target_kind == "merged":
        if _is_branch_merged(paths, upstream.branch):
            return "satisfied", f"Upstream branch {upstream.branch} is merged."
        return "active", "Waiting for upstream merge."
    raise MatriarchError(f"Unsupported dependency target kind: {target_kind}")


def _refresh_dependencies(paths: MatriarchPaths, record: LaneRecord) -> list[dict[str, Any]]:
    refreshed: list[dict[str, Any]] = []
    for dependency in record.dependencies:
        state, rationale = _evaluate_dependency_state(paths, dependency)
        updated = dict(dependency)
        updated["state"] = state
        updated["rationale"] = rationale
        refreshed.append(updated)
    record.dependencies = refreshed
    record.dependency_ids = [item["dependency_id"] for item in refreshed]
    return refreshed


def _record_warning(record: LaneRecord, warning: str) -> None:
    if warning not in record.notes:
        record.notes = f"{record.notes}\n{warning}".strip()


def register_lane(
    spec_id: str,
    *,
    repo_root: Path | str | None = None,
    branch: str | None = None,
    worktree_path: str | None = None,
    owner_type: str = "unassigned",
    owner_id: str | None = None,
    title: str | None = None,
    notes: str = "",
) -> LaneRecord:
    if owner_type not in OWNERSHIP_TYPES:
        raise MatriarchError(f"Unsupported owner type: {owner_type}")

    paths = MatriarchPaths(_repo_root(repo_root))
    _ensure_runtime_paths(paths)
    lane_id = spec_id
    existing_path = paths.lane_path(lane_id)
    if existing_path.exists():
        raise MatriarchError(f"Lane already exists: {lane_id}")

    worktree_context = _load_worktree_context(paths, spec_id)
    current_branch = branch or worktree_context.get("branch") or _git_current_branch(paths.repo_root)
    current_path = worktree_path or worktree_context.get("path") or _current_worktree_path(paths)
    mailbox_root = paths.mailbox_root(lane_id)
    mailbox_root.mkdir(parents=True, exist_ok=True)
    paths.reports_path(lane_id).parent.mkdir(parents=True, exist_ok=True)
    if not paths.delegated_path(lane_id).exists():
        _write_json_atomic(paths.delegated_path(lane_id), {"lane_id": lane_id, "tasks": []})

    flow_summary = _flow_summary(paths, spec_id)
    timestamp = _now_rfc3339()
    initial_state = "active" if owner_type != "unassigned" or flow_summary.get("current_stage") else "registered"
    assignment_history: list[dict[str, Any]] = []
    if owner_type != "unassigned":
        assignment_history.append(
            LaneAssignment(
                lane_id=lane_id,
                owner_type=owner_type,
                owner_id=owner_id,
                assigned_at=timestamp,
                released_at=None,
                assignment_state="active",
                notes="Initial registration assignment.",
            ).to_dict()
        )

    record = LaneRecord(
        schema_version=REGISTRY_SCHEMA_VERSION,
        lane_id=lane_id,
        spec_id=spec_id,
        title=title or _slug_title(spec_id),
        branch=current_branch,
        worktree_path=current_path,
        registry_revision=0,
        lifecycle_state=initial_state,
        owner_type=owner_type,
        owner_id=owner_id,
        stage=flow_summary.get("current_stage"),
        readiness="unknown",
        dependency_ids=[],
        deployment_id=None,
        mailbox_path=str(mailbox_root.relative_to(paths.repo_root)),
        status_reason="Lane registered.",
        created_at=timestamp,
        updated_at=timestamp,
        assignment_history=assignment_history,
        dependencies=[],
        deployment=None,
        notes=notes,
    )
    effective_state, reason = _derive_effective_state(record, flow_summary)
    record.lifecycle_state = effective_state
    record.status_reason = reason
    record.readiness = effective_state

    return _commit_lane_record(paths, record, expected_revision=None, register_lane=True)


def assign_lane(
    lane_id: str,
    *,
    repo_root: Path | str | None = None,
    owner_type: str,
    owner_id: str | None,
    notes: str = "",
) -> LaneRecord:
    if owner_type not in OWNERSHIP_TYPES:
        raise MatriarchError(f"Unsupported owner type: {owner_type}")
    paths = MatriarchPaths(_repo_root(repo_root))
    record = _load_lane(paths, lane_id)
    timestamp = _now_rfc3339()
    if record.assignment_history:
        last = record.assignment_history[-1]
        if last.get("assignment_state") == "active":
            last["assignment_state"] = "released"
            last["released_at"] = timestamp
    assignment = LaneAssignment(
        lane_id=lane_id,
        owner_type=owner_type,
        owner_id=owner_id,
        assigned_at=timestamp,
        released_at=None,
        assignment_state="active",
        notes=notes,
    )
    record.assignment_history.append(assignment.to_dict())
    record.owner_type = owner_type
    record.owner_id = owner_id
    record.updated_at = timestamp
    record.status_reason = "Lane assignment updated."
    if record.deployment and record.deployment.get("state") in ACTIVE_DEPLOYMENT_STATES:
        launched_by = record.deployment.get("launched_by")
        if launched_by and launched_by != owner_id:
            _record_warning(record, "Deployment owner does not match current lane owner.")
    flow_summary = _flow_summary(paths, record.spec_id)
    _refresh_dependencies(paths, record)
    record.stage = flow_summary.get("current_stage")
    effective_state, reason = _derive_effective_state(record, flow_summary)
    record.lifecycle_state = effective_state
    record.status_reason = reason
    return _commit_lane_record(paths, record, expected_revision=record.registry_revision)


def add_dependency(
    lane_id: str,
    depends_on_lane_id: str,
    *,
    repo_root: Path | str | None = None,
    strength: str = "hard",
    target_kind: str = "lane_exists",
    target_value: str | None = None,
    rationale: str = "",
) -> LaneRecord:
    if strength not in DEPENDENCY_STRENGTHS:
        raise MatriarchError(f"Unsupported dependency strength: {strength}")
    if target_kind not in DEPENDENCY_TARGET_KINDS:
        raise MatriarchError(f"Unsupported dependency target kind: {target_kind}")
    if target_kind == "stage_reached" and target_value not in STAGE_ORDER:
        raise MatriarchError(f"stage_reached dependencies require one of: {', '.join(STAGE_ORDER)}")

    paths = MatriarchPaths(_repo_root(repo_root))
    record = _load_lane(paths, lane_id)
    dependency_id = f"{lane_id}-depends-{depends_on_lane_id}-{len(record.dependencies) + 1}"
    dependency = LaneDependency(
        dependency_id=dependency_id,
        lane_id=lane_id,
        depends_on_lane_id=depends_on_lane_id,
        strength=strength,
        target_kind=target_kind,
        target_value=target_value,
        state="active",
        rationale=rationale,
    )
    record.dependencies.append(dependency.to_dict())
    record.dependency_ids.append(dependency_id)
    record.updated_at = _now_rfc3339()
    _refresh_dependencies(paths, record)
    flow_summary = _flow_summary(paths, lane_id)
    effective_state, reason = _derive_effective_state(record, flow_summary)
    record.lifecycle_state = effective_state
    record.status_reason = reason
    return _commit_lane_record(paths, record, expected_revision=record.registry_revision)


def attach_deployment(
    lane_id: str,
    *,
    repo_root: Path | str | None = None,
    deployment_kind: str,
    session_name: str,
    state: str = "running",
    worker_cli: str | None = None,
    launched_by: str | None = None,
    notes: str = "",
) -> LaneRecord:
    if deployment_kind not in DEPLOYMENT_KINDS:
        raise MatriarchError(f"Unsupported deployment kind: {deployment_kind}")
    if state not in DEPLOYMENT_STATES:
        raise MatriarchError(f"Unsupported deployment state: {state}")
    paths = MatriarchPaths(_repo_root(repo_root))
    record = _load_lane(paths, lane_id)
    timestamp = _now_rfc3339()
    deployment = LaneDeployment(
        deployment_id=f"{lane_id}-{deployment_kind}",
        lane_id=lane_id,
        deployment_kind=deployment_kind,
        session_name=session_name,
        state=state,
        launched_by=launched_by,
        attached_at=timestamp,
        last_seen_at=timestamp,
        worker_cli=worker_cli,
        notes=notes,
    )
    record.deployment = deployment.to_dict()
    record.deployment_id = deployment.deployment_id
    record.updated_at = timestamp
    if record.owner_id and launched_by and launched_by != record.owner_id:
        _record_warning(record, "Deployment launcher does not match current lane owner.")
    return _commit_lane_record(paths, record, expected_revision=record.registry_revision)


def archive_lane(
    lane_id: str,
    *,
    repo_root: Path | str | None = None,
    reason: str = "",
) -> LaneRecord:
    paths = MatriarchPaths(_repo_root(repo_root))
    record = _load_lane(paths, lane_id)
    record.lifecycle_state = "archived"
    record.status_reason = reason or "Lane archived by operator."
    record.updated_at = _now_rfc3339()
    return _commit_lane_record(paths, record, expected_revision=record.registry_revision)


def send_mailbox_event(
    lane_id: str,
    *,
    repo_root: Path | str | None = None,
    direction: str,
    sender: str,
    recipient: str,
    event_type: str,
    payload: str | dict[str, Any],
    ack_status_override: str | None = None,
) -> EventEnvelope:
    if direction not in {"to_lane", "to_matriarch"}:
        raise MatriarchError(f"Unsupported mailbox direction: {direction}")
    _validate_event_type(event_type)
    paths = MatriarchPaths(_repo_root(repo_root))
    _load_lane(paths, lane_id)
    # For ack events the default envelope state is "acknowledged"; callers that
    # need "resolved" (e.g. acknowledge_event) pass ack_status_override.
    default_ack_status = "acknowledged" if event_type == "ack" else "new"
    ack_status = ack_status_override if ack_status_override is not None else default_ack_status
    if ack_status not in EVENT_ACK_STATES:
        raise MatriarchError(f"Unsupported ack status: {ack_status}")
    event = EventEnvelope(
        id=_event_id(lane_id, event_type),
        timestamp=_now_rfc3339(),
        lane_id=lane_id,
        sender=sender,
        recipient=recipient,
        type=event_type,
        payload=payload,
        ack_status=ack_status,
    )
    path = paths.mailbox_outbound(lane_id) if direction == "to_lane" else paths.mailbox_inbound(lane_id)
    _append_event(path, event)
    return event


def acknowledge_event(
    lane_id: str,
    *,
    repo_root: Path | str | None = None,
    sender: str,
    recipient: str,
    acked_event_id: str,
    resolution: str = "acknowledged",
) -> EventEnvelope:
    if resolution not in {"acknowledged", "resolved"}:
        raise MatriarchError(f"Unsupported acknowledgment state: {resolution}")
    return send_mailbox_event(
        lane_id,
        repo_root=repo_root,
        direction="to_matriarch",
        sender=sender,
        recipient=recipient,
        event_type="ack",
        payload={"acked_event_id": acked_event_id, "ack_status": resolution},
        ack_status_override=resolution,
    )


def list_mailbox_events(
    lane_id: str,
    *,
    repo_root: Path | str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    paths = MatriarchPaths(_repo_root(repo_root))
    _load_lane(paths, lane_id)
    return {
        "inbound": _read_jsonl(paths.mailbox_inbound(lane_id)),
        "outbound": _read_jsonl(paths.mailbox_outbound(lane_id)),
    }


def emit_startup_ack(
    lane_id: str,
    *,
    repo_root: Path | str | None = None,
    sender: str,
    deployment_id: str | None = None,
    context_refs: list[str] | None = None,
) -> EventEnvelope:
    payload: dict[str, Any] = {
        "startup": True,
        "context_refs": context_refs or [],
    }
    if deployment_id:
        payload["deployment_id"] = deployment_id
    return append_report_event(
        lane_id,
        repo_root=repo_root,
        sender=sender,
        recipient="matriarch",
        event_type="ack",
        payload=payload,
    )


def append_report_event(
    lane_id: str,
    *,
    repo_root: Path | str | None = None,
    sender: str,
    recipient: str = "matriarch",
    event_type: str,
    payload: str | dict[str, Any],
) -> EventEnvelope:
    _validate_event_type(event_type)
    paths = MatriarchPaths(_repo_root(repo_root))
    _load_lane(paths, lane_id)
    event = EventEnvelope(
        id=_event_id(lane_id, event_type),
        timestamp=_now_rfc3339(),
        lane_id=lane_id,
        sender=sender,
        recipient=recipient,
        type=event_type,
        payload=payload,
        ack_status="acknowledged" if event_type == "ack" else "new",
    )
    _append_event(paths.reports_path(lane_id), event)
    return event


def _load_delegated_payload(paths: MatriarchPaths, lane_id: str) -> dict[str, Any]:
    path = paths.delegated_path(lane_id)
    if not path.exists():
        payload = {"lane_id": lane_id, "tasks": []}
        _write_json_atomic(path, payload)
        return payload
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise MatriarchError(f"Invalid delegated-work store: {path}")
    payload.setdefault("lane_id", lane_id)
    payload.setdefault("tasks", [])
    return payload


def _write_delegated_payload(paths: MatriarchPaths, lane_id: str, payload: dict[str, Any]) -> None:
    _write_json_atomic(paths.delegated_path(lane_id), payload)


def _mutate_delegated_work(paths: MatriarchPaths, lane_id: str, mutator: Any) -> DelegatedWorkItem:
    fd = _acquire_lock(paths.delegated_lock_path(lane_id))
    try:
        _load_lane(paths, lane_id)
        payload = _load_delegated_payload(paths, lane_id)
        item = mutator(payload)
        _write_delegated_payload(paths, lane_id, payload)
        return item
    finally:
        _release_lock(fd)


def create_delegated_work(
    lane_id: str,
    task_id: str,
    title: str,
    *,
    repo_root: Path | str | None = None,
) -> DelegatedWorkItem:
    paths = MatriarchPaths(_repo_root(repo_root))
    _load_lane(paths, lane_id)
    def _mutator(payload: dict[str, Any]) -> DelegatedWorkItem:
        for item in payload["tasks"]:
            if item["task_id"] == task_id:
                raise MatriarchError(f"Delegated work item already exists: {task_id}")
        task = DelegatedWorkItem(
            task_id=task_id,
            lane_id=lane_id,
            title=title,
            status="pending",
            claimed_by=None,
            claim_token=None,
            claimed_at=None,
            released_at=None,
            completed_at=None,
            result_ref=None,
            error_ref=None,
        )
        payload["tasks"].append(task.to_dict())
        return task

    return _mutate_delegated_work(paths, lane_id, _mutator)


def claim_delegated_work(
    lane_id: str,
    task_id: str,
    *,
    repo_root: Path | str | None = None,
    claimer_id: str,
) -> DelegatedWorkItem:
    paths = MatriarchPaths(_repo_root(repo_root))
    def _mutator(payload: dict[str, Any]) -> DelegatedWorkItem:
        for item in payload["tasks"]:
            if item["task_id"] != task_id:
                continue
            if item["status"] != "pending":
                raise MatriarchError(f"Delegated work item is not pending: {task_id}")
            claimed_at = _now_rfc3339()
            claim_token = f"{lane_id}:{task_id}:{claimer_id}:{secrets.token_hex(8)}"
            item["status"] = "in_progress"
            item["claimed_by"] = claimer_id
            item["claim_token"] = claim_token
            item["claimed_at"] = claimed_at
            item["released_at"] = None
            item["completed_at"] = None
            return DelegatedWorkItem(**item)
        raise MatriarchError(f"Unknown delegated work item: {task_id}")

    return _mutate_delegated_work(paths, lane_id, _mutator)


def complete_delegated_work(
    lane_id: str,
    task_id: str,
    *,
    repo_root: Path | str | None = None,
    claim_token: str,
    result_ref: str | None = None,
    failed: bool = False,
    error_ref: str | None = None,
) -> DelegatedWorkItem:
    paths = MatriarchPaths(_repo_root(repo_root))
    def _mutator(payload: dict[str, Any]) -> DelegatedWorkItem:
        for item in payload["tasks"]:
            if item["task_id"] != task_id:
                continue
            if item.get("status") != "in_progress":
                raise MatriarchError(
                    f"Delegated work item {task_id!r} is not in_progress (status={item.get('status')!r})"
                )
            if item.get("claim_token") != claim_token:
                raise MatriarchError(f"Stale delegated-work completion rejected for {task_id}")
            item["status"] = "failed" if failed else "completed"
            item["completed_at"] = _now_rfc3339()
            item["result_ref"] = result_ref
            item["error_ref"] = error_ref
            item["claimed_by"] = None
            item["claim_token"] = None
            return DelegatedWorkItem(**item)
        raise MatriarchError(f"Unknown delegated work item: {task_id}")

    return _mutate_delegated_work(paths, lane_id, _mutator)


def release_delegated_work(
    lane_id: str,
    task_id: str,
    *,
    repo_root: Path | str | None = None,
    claim_token: str,
) -> DelegatedWorkItem:
    paths = MatriarchPaths(_repo_root(repo_root))
    def _mutator(payload: dict[str, Any]) -> DelegatedWorkItem:
        for item in payload["tasks"]:
            if item["task_id"] != task_id:
                continue
            if item.get("claim_token") != claim_token:
                raise MatriarchError(f"Stale delegated-work release rejected for {task_id}")
            item["status"] = "pending"
            item["released_at"] = _now_rfc3339()
            item["claimed_by"] = None
            item["claim_token"] = None
            item["claimed_at"] = None
            item["result_ref"] = None
            item["error_ref"] = None
            item["completed_at"] = None
            return DelegatedWorkItem(**item)
        raise MatriarchError(f"Unknown delegated work item: {task_id}")

    return _mutate_delegated_work(paths, lane_id, _mutator)


def summarize_lane(
    lane_id: str,
    *,
    repo_root: Path | str | None = None,
) -> dict[str, Any]:
    paths = MatriarchPaths(_repo_root(repo_root))
    record = _load_lane(paths, lane_id)
    flow_summary = _flow_summary(paths, record.spec_id)
    _refresh_dependencies(paths, record)
    effective_state, reason = _derive_effective_state(record, flow_summary)
    mailbox = list_mailbox_events(lane_id, repo_root=paths.repo_root)
    reports = _read_jsonl(paths.reports_path(lane_id))
    delegated = _load_delegated_payload(paths, lane_id).get("tasks", [])
    deployment = dict(record.deployment) if isinstance(record.deployment, dict) else None
    if deployment:
        launcher = deployment.get("launched_by")
        deployment["owner_matches_lane"] = bool(
            not launcher or not record.owner_id or launcher == record.owner_id
        )
    return {
        "lane_id": record.lane_id,
        "spec_id": record.spec_id,
        "title": record.title,
        "branch": record.branch,
        "worktree_path": record.worktree_path,
        "effective_state": effective_state,
        "status_reason": reason,
        "owner_type": record.owner_type,
        "owner_id": record.owner_id,
        "deployment": deployment,
        "flow_state": flow_summary,
        "dependencies": record.dependencies,
        "mailbox_counts": {
            "inbound": len(mailbox["inbound"]),
            "outbound": len(mailbox["outbound"]),
            "reports": len(reports),
        },
        "delegated_work": delegated,
        "assignment_history": record.assignment_history,
        "mailbox_path": record.mailbox_path,
        "registry_revision": record.registry_revision,
    }


def list_lanes(*, repo_root: Path | str | None = None) -> list[dict[str, Any]]:
    paths = MatriarchPaths(_repo_root(repo_root))
    registry = _load_registry(paths)
    lanes: list[dict[str, Any]] = []
    for lane_id in registry.get("lanes", []):
        try:
            lanes.append(summarize_lane(lane_id, repo_root=paths.repo_root))
        except MatriarchError:
            lanes.append({"lane_id": lane_id, "error": "missing or invalid lane record"})
    return lanes


def overall_status(*, repo_root: Path | str | None = None) -> dict[str, Any]:
    paths = MatriarchPaths(_repo_root(repo_root))
    lanes = list_lanes(repo_root=paths.repo_root)
    counts = {
        "registered": 0,
        "active": 0,
        "blocked": 0,
        "review_ready": 0,
        "pr_ready": 0,
        "archived": 0,
    }
    for lane in lanes:
        state = lane.get("effective_state")
        if state in counts:
            counts[state] += 1
    return {
        "repo_root": str(paths.repo_root),
        "lane_count": len(lanes),
        "counts": counts,
        "lanes": lanes,
    }


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Orca Matriarch supervisor runtime.")
    parser.add_argument("--repo-root", help="Optional repo root override.")
    parser.add_argument("--format", choices=("json", "text"), default="json", help="Output format.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Show overall Matriarch status.")

    lane_parser = subparsers.add_parser("lane", help="Lane-focused Matriarch actions.")
    lane_subparsers = lane_parser.add_subparsers(dest="lane_command", required=True)

    lane_subparsers.add_parser("list", help="List lanes.")

    show_parser = lane_subparsers.add_parser("show", help="Show lane details.")
    show_parser.add_argument("lane_id")

    archive_parser = lane_subparsers.add_parser("archive", help="Archive a lane explicitly.")
    archive_parser.add_argument("lane_id")
    archive_parser.add_argument("--reason", default="")

    register_parser = lane_subparsers.add_parser("register", help="Register a lane from a spec id.")
    register_parser.add_argument("spec_id")
    register_parser.add_argument("--branch")
    register_parser.add_argument("--worktree-path")
    register_parser.add_argument("--owner-type", default="unassigned")
    register_parser.add_argument("--owner-id")
    register_parser.add_argument("--title")
    register_parser.add_argument("--notes", default="")

    assign_parser = lane_subparsers.add_parser("assign", help="Assign or reassign a lane owner.")
    assign_parser.add_argument("lane_id")
    assign_parser.add_argument("--owner-type", required=True)
    assign_parser.add_argument("--owner-id")
    assign_parser.add_argument("--notes", default="")

    depend_parser = lane_subparsers.add_parser("depend", help="Add a dependency to a lane.")
    depend_parser.add_argument("lane_id")
    depend_parser.add_argument("--on", required=True, dest="depends_on_lane_id")
    depend_parser.add_argument("--strength", default="hard")
    depend_parser.add_argument("--target-kind", default="lane_exists")
    depend_parser.add_argument("--target-value")
    depend_parser.add_argument("--rationale", default="")

    deploy_parser = lane_subparsers.add_parser("deploy", help="Attach deployment metadata to a lane.")
    deploy_parser.add_argument("lane_id")
    deploy_parser.add_argument("--kind", required=True, dest="deployment_kind")
    deploy_parser.add_argument("--session-name", required=True)
    deploy_parser.add_argument("--state", default="running")
    deploy_parser.add_argument("--worker-cli")
    deploy_parser.add_argument("--launched-by")
    deploy_parser.add_argument("--notes", default="")

    mailbox_parser = lane_subparsers.add_parser("mailbox", help="Send or inspect lane mailbox events.")
    mailbox_subparsers = mailbox_parser.add_subparsers(dest="mailbox_command", required=True)
    mailbox_list = mailbox_subparsers.add_parser("list", help="List lane mailbox events.")
    mailbox_list.add_argument("lane_id")
    mailbox_send = mailbox_subparsers.add_parser("send", help="Send a lane mailbox event.")
    mailbox_send.add_argument("lane_id")
    mailbox_send.add_argument("--direction", choices=("to_lane", "to_matriarch"), required=True)
    mailbox_send.add_argument("--sender", required=True)
    mailbox_send.add_argument("--recipient", required=True)
    mailbox_send.add_argument("--type", required=True, dest="event_type")
    mailbox_send.add_argument("--payload", required=True)
    mailbox_ack = mailbox_subparsers.add_parser("ack", help="Acknowledge a previously emitted event.")
    mailbox_ack.add_argument("lane_id")
    mailbox_ack.add_argument("--sender", required=True)
    mailbox_ack.add_argument("--recipient", default="matriarch")
    mailbox_ack.add_argument("--event-id", required=True, dest="event_id")
    mailbox_ack.add_argument("--state", choices=("acknowledged", "resolved"), default="acknowledged")

    report_parser = lane_subparsers.add_parser("report", help="Append a lane report event.")
    report_parser.add_argument("lane_id")
    report_parser.add_argument("--sender", required=True)
    report_parser.add_argument("--recipient", default="matriarch")
    report_parser.add_argument("--type", required=True, dest="event_type")
    report_parser.add_argument("--payload", required=True)
    startup_parser = lane_subparsers.add_parser("startup-ack", help="Emit a deterministic startup ACK report.")
    startup_parser.add_argument("lane_id")
    startup_parser.add_argument("--sender", required=True)
    startup_parser.add_argument("--deployment-id")
    startup_parser.add_argument("--context-ref", action="append", default=[], dest="context_refs")

    work_parser = lane_subparsers.add_parser("work", help="Manage delegated work items.")
    work_subparsers = work_parser.add_subparsers(dest="work_command", required=True)
    work_create = work_subparsers.add_parser("create")
    work_create.add_argument("lane_id")
    work_create.add_argument("task_id")
    work_create.add_argument("--title", required=True)
    work_claim = work_subparsers.add_parser("claim")
    work_claim.add_argument("lane_id")
    work_claim.add_argument("task_id")
    work_claim.add_argument("--claimer-id", required=True)
    work_complete = work_subparsers.add_parser("complete")
    work_complete.add_argument("lane_id")
    work_complete.add_argument("task_id")
    work_complete.add_argument("--claim-token", required=True)
    work_complete.add_argument("--result-ref")
    work_complete.add_argument("--failed", action="store_true")
    work_complete.add_argument("--error-ref")
    work_release = work_subparsers.add_parser("release")
    work_release.add_argument("lane_id")
    work_release.add_argument("task_id")
    work_release.add_argument("--claim-token", required=True)

    return parser


def _render_text(payload: Any) -> None:
    if isinstance(payload, dict):
        print(json.dumps(payload, indent=2))
    else:
        print(payload)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    repo_root = args.repo_root

    try:
        if args.command == "status":
            payload = overall_status(repo_root=repo_root)
        elif args.command == "lane" and args.lane_command == "list":
            payload = list_lanes(repo_root=repo_root)
        elif args.command == "lane" and args.lane_command == "show":
            payload = summarize_lane(args.lane_id, repo_root=repo_root)
        elif args.command == "lane" and args.lane_command == "archive":
            payload = archive_lane(args.lane_id, repo_root=repo_root, reason=args.reason).to_dict()
        elif args.command == "lane" and args.lane_command == "register":
            payload = register_lane(
                args.spec_id,
                repo_root=repo_root,
                branch=args.branch,
                worktree_path=args.worktree_path,
                owner_type=args.owner_type,
                owner_id=args.owner_id,
                title=args.title,
                notes=args.notes,
            ).to_dict()
        elif args.command == "lane" and args.lane_command == "assign":
            payload = assign_lane(
                args.lane_id,
                repo_root=repo_root,
                owner_type=args.owner_type,
                owner_id=args.owner_id,
                notes=args.notes,
            ).to_dict()
        elif args.command == "lane" and args.lane_command == "depend":
            payload = add_dependency(
                args.lane_id,
                args.depends_on_lane_id,
                repo_root=repo_root,
                strength=args.strength,
                target_kind=args.target_kind,
                target_value=args.target_value,
                rationale=args.rationale,
            ).to_dict()
        elif args.command == "lane" and args.lane_command == "deploy":
            payload = attach_deployment(
                args.lane_id,
                repo_root=repo_root,
                deployment_kind=args.deployment_kind,
                session_name=args.session_name,
                state=args.state,
                worker_cli=args.worker_cli,
                launched_by=args.launched_by,
                notes=args.notes,
            ).to_dict()
        elif args.command == "lane" and args.lane_command == "mailbox" and args.mailbox_command == "list":
            payload = list_mailbox_events(args.lane_id, repo_root=repo_root)
        elif args.command == "lane" and args.lane_command == "mailbox" and args.mailbox_command == "send":
            payload = send_mailbox_event(
                args.lane_id,
                repo_root=repo_root,
                direction=args.direction,
                sender=args.sender,
                recipient=args.recipient,
                event_type=args.event_type,
                payload=_parse_payload(args.payload),
            ).to_dict()
        elif args.command == "lane" and args.lane_command == "mailbox" and args.mailbox_command == "ack":
            payload = acknowledge_event(
                args.lane_id,
                repo_root=repo_root,
                sender=args.sender,
                recipient=args.recipient,
                acked_event_id=args.event_id,
                resolution=args.state,
            ).to_dict()
        elif args.command == "lane" and args.lane_command == "report":
            payload = append_report_event(
                args.lane_id,
                repo_root=repo_root,
                sender=args.sender,
                recipient=args.recipient,
                event_type=args.event_type,
                payload=_parse_payload(args.payload),
            ).to_dict()
        elif args.command == "lane" and args.lane_command == "startup-ack":
            payload = emit_startup_ack(
                args.lane_id,
                repo_root=repo_root,
                sender=args.sender,
                deployment_id=args.deployment_id,
                context_refs=args.context_refs,
            ).to_dict()
        elif args.command == "lane" and args.lane_command == "work" and args.work_command == "create":
            payload = create_delegated_work(
                args.lane_id,
                args.task_id,
                args.title,
                repo_root=repo_root,
            ).to_dict()
        elif args.command == "lane" and args.lane_command == "work" and args.work_command == "claim":
            payload = claim_delegated_work(
                args.lane_id,
                args.task_id,
                repo_root=repo_root,
                claimer_id=args.claimer_id,
            ).to_dict()
        elif args.command == "lane" and args.lane_command == "work" and args.work_command == "complete":
            payload = complete_delegated_work(
                args.lane_id,
                args.task_id,
                repo_root=repo_root,
                claim_token=args.claim_token,
                result_ref=args.result_ref,
                failed=args.failed,
                error_ref=args.error_ref,
            ).to_dict()
        elif args.command == "lane" and args.lane_command == "work" and args.work_command == "release":
            payload = release_delegated_work(
                args.lane_id,
                args.task_id,
                repo_root=repo_root,
                claim_token=args.claim_token,
            ).to_dict()
        else:
            raise MatriarchError("Unsupported command.")
    except MatriarchError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        _print_json(payload)
    else:
        _render_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
