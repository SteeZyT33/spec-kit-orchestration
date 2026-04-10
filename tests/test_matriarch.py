from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from speckit_orca.matriarch import (
    MatriarchError,
    acknowledge_event,
    add_dependency,
    append_report_event,
    archive_lane,
    attach_deployment,
    claim_delegated_work,
    complete_delegated_work,
    create_delegated_work,
    emit_startup_ack,
    list_mailbox_events,
    overall_status,
    register_lane,
    release_delegated_work,
    send_mailbox_event,
    summarize_lane,
)


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / ".specify").mkdir(parents=True)
    (root / "specs").mkdir()
    return root


def _spec(root: Path, spec_id: str, *, files: dict[str, str] | None = None) -> Path:
    feature_dir = root / "specs" / spec_id
    feature_dir.mkdir(parents=True)
    for name, content in (files or {"spec.md": "# Spec\n"}).items():
        (feature_dir / name).write_text(content, encoding="utf-8")
    return feature_dir


def test_register_lane_creates_registry_and_mailbox_paths(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _spec(repo, "010-orca-matriarch")

    record = register_lane("010-orca-matriarch", repo_root=repo)

    assert record.lane_id == "010-orca-matriarch"
    assert record.spec_id == "010-orca-matriarch"
    assert record.registry_revision == 1
    assert record.mailbox_path == ".specify/orca/matriarch/mailbox/010-orca-matriarch"
    assert record.assignment_history == []
    assert (repo / ".specify" / "orca" / "matriarch" / "registry.json").exists()
    assert (repo / ".specify" / "orca" / "matriarch" / "mailbox" / "010-orca-matriarch").exists()


def test_dependency_on_missing_upstream_blocks_lane_until_upstream_exists(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _spec(repo, "010-orca-matriarch")
    _spec(repo, "011-orca-evolve")

    register_lane("010-orca-matriarch", repo_root=repo, owner_type="human", owner_id="taylor")
    add_dependency(
        "010-orca-matriarch",
        "011-orca-evolve",
        repo_root=repo,
        target_kind="lane_exists",
        rationale="Wait for upstream setup.",
    )

    blocked = summarize_lane("010-orca-matriarch", repo_root=repo)
    assert blocked["effective_state"] == "blocked"
    assert blocked["dependencies"][0]["state"] == "active"

    register_lane("011-orca-evolve", repo_root=repo)

    unblocked = summarize_lane("010-orca-matriarch", repo_root=repo)
    assert unblocked["effective_state"] == "active"
    assert unblocked["dependencies"][0]["state"] == "satisfied"
    assert unblocked["assignment_history"][0]["owner_id"] == "taylor"


def test_lane_mutations_advance_registry_revision(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _spec(repo, "010-orca-matriarch")

    registered = register_lane("010-orca-matriarch", repo_root=repo)
    assert registered.registry_revision == 1

    reassigned = add_dependency(
        "010-orca-matriarch",
        "missing-lane",
        repo_root=repo,
        target_kind="lane_exists",
    )
    assert reassigned.registry_revision == 2

    archived = archive_lane("010-orca-matriarch", repo_root=repo, reason="Done.")
    assert archived.registry_revision == 3

    status = overall_status(repo_root=repo)
    assert status["counts"]["archived"] == 1


def test_mailbox_and_report_events_use_shared_envelope(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _spec(repo, "010-orca-matriarch")
    register_lane("010-orca-matriarch", repo_root=repo)

    outbound = send_mailbox_event(
        "010-orca-matriarch",
        repo_root=repo,
        direction="to_lane",
        sender="matriarch",
        recipient="worker-1",
        event_type="instruction",
        payload={"step": "inspect"},
    )
    ack = acknowledge_event(
        "010-orca-matriarch",
        repo_root=repo,
        sender="worker-1",
        recipient="matriarch",
        acked_event_id=outbound.id,
    )
    startup = emit_startup_ack(
        "010-orca-matriarch",
        repo_root=repo,
        sender="worker-1",
        deployment_id="010-orca-matriarch-direct-session",
        context_refs=["specs/010-orca-matriarch/spec.md"],
    )
    append_report_event(
        "010-orca-matriarch",
        repo_root=repo,
        sender="worker-1",
        event_type="status",
        payload={"message": "running"},
    )

    mailbox = list_mailbox_events("010-orca-matriarch", repo_root=repo)
    reports_path = repo / ".specify" / "orca" / "matriarch" / "reports" / "010-orca-matriarch" / "events.jsonl"
    reports = [json.loads(line) for line in reports_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert mailbox["outbound"][0]["type"] == "instruction"
    assert mailbox["inbound"][0]["type"] == "ack"
    assert mailbox["inbound"][0]["ack_status"] == "acknowledged"
    assert mailbox["inbound"][0]["payload"]["acked_event_id"] == outbound.id
    assert startup.type == "ack"
    assert startup.ack_status == "acknowledged"
    assert reports[0]["payload"]["deployment_id"] == "010-orca-matriarch-direct-session"
    assert reports[1]["type"] == "status"


def test_delegated_work_rejects_stale_completion_and_can_be_released(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _spec(repo, "010-orca-matriarch")
    register_lane("010-orca-matriarch", repo_root=repo)

    create_delegated_work("010-orca-matriarch", "T001", "Implement runtime", repo_root=repo)
    claimed = claim_delegated_work(
        "010-orca-matriarch",
        "T001",
        repo_root=repo,
        claimer_id="worker-1",
    )

    with pytest.raises(MatriarchError, match="Stale delegated-work completion rejected"):
        complete_delegated_work(
            "010-orca-matriarch",
            "T001",
            repo_root=repo,
            claim_token="bad-token",
            result_ref="notes.md",
        )

    released = release_delegated_work(
        "010-orca-matriarch",
        "T001",
        repo_root=repo,
        claim_token=claimed.claim_token or "",
    )
    assert released.status == "pending"

    reclaimed = claim_delegated_work(
        "010-orca-matriarch",
        "T001",
        repo_root=repo,
        claimer_id="worker-2",
    )
    completed = complete_delegated_work(
        "010-orca-matriarch",
        "T001",
        repo_root=repo,
        claim_token=reclaimed.claim_token or "",
        result_ref="specs/010-orca-matriarch/review.md",
    )
    assert completed.status == "completed"
    assert completed.result_ref == "specs/010-orca-matriarch/review.md"
    assert completed.claimed_by is None
    assert completed.claim_token is None


def test_archived_upstream_does_not_satisfy_review_or_pr_dependencies(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _spec(repo, "010-orca-matriarch")
    _spec(repo, "011-orca-evolve")
    register_lane("010-orca-matriarch", repo_root=repo)
    register_lane("011-orca-evolve", repo_root=repo)
    archive_lane("011-orca-evolve", repo_root=repo, reason="Stopped.")

    review_record = add_dependency(
        "010-orca-matriarch",
        "011-orca-evolve",
        repo_root=repo,
        target_kind="review_ready",
    )
    assert review_record.dependencies[0]["state"] == "active"

    pr_record = add_dependency(
        "010-orca-matriarch",
        "011-orca-evolve",
        repo_root=repo,
        target_kind="pr_ready",
    )
    assert pr_record.dependencies[1]["state"] == "active"


def test_deploy_accepts_explicit_state(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _spec(repo, "010-orca-matriarch")
    register_lane("010-orca-matriarch", repo_root=repo)

    record = attach_deployment(
        "010-orca-matriarch",
        repo_root=repo,
        deployment_kind="direct-session",
        session_name="claude-code-session",
        state="detached",
        worker_cli="claude",
    )

    assert record.deployment is not None
    assert record.deployment["state"] == "detached"


# ---------------------------------------------------------------------------
# Tests for the six targeted fixes
# ---------------------------------------------------------------------------


def test_acknowledge_event_resolved_sets_envelope_ack_status(tmp_path: Path) -> None:
    """acknowledge_event(resolution="resolved") must persist ack_status=resolved on the envelope."""
    repo = _repo(tmp_path)
    _spec(repo, "010-orca-matriarch")
    register_lane("010-orca-matriarch", repo_root=repo)

    outbound = send_mailbox_event(
        "010-orca-matriarch",
        repo_root=repo,
        direction="to_lane",
        sender="matriarch",
        recipient="worker-1",
        event_type="instruction",
        payload={"step": "build"},
    )
    ack = acknowledge_event(
        "010-orca-matriarch",
        repo_root=repo,
        sender="worker-1",
        recipient="matriarch",
        acked_event_id=outbound.id,
        resolution="resolved",
    )
    assert ack.ack_status == "resolved"

    mailbox = list_mailbox_events("010-orca-matriarch", repo_root=repo)
    stored = mailbox["inbound"][0]
    assert stored["ack_status"] == "resolved", (
        "Stored envelope ack_status must reflect the resolution value, not the default 'acknowledged'"
    )


def test_complete_delegated_work_rejects_non_in_progress_task(tmp_path: Path) -> None:
    """complete_delegated_work must raise MatriarchError if the task is not in_progress."""
    repo = _repo(tmp_path)
    _spec(repo, "010-orca-matriarch")
    register_lane("010-orca-matriarch", repo_root=repo)
    create_delegated_work("010-orca-matriarch", "T002", "Pending task", repo_root=repo)
    claimed = claim_delegated_work(
        "010-orca-matriarch", "T002", repo_root=repo, claimer_id="worker-1"
    )

    # Release the task back to pending.
    release_delegated_work(
        "010-orca-matriarch", "T002", repo_root=repo, claim_token=claimed.claim_token or ""
    )

    # Attempting to complete a pending task with the old token must fail with
    # the status check, not the token check.
    with pytest.raises(MatriarchError, match="not in_progress"):
        complete_delegated_work(
            "010-orca-matriarch",
            "T002",
            repo_root=repo,
            claim_token=claimed.claim_token or "",
            result_ref="notes.md",
        )


def test_claim_token_is_unpredictable(tmp_path: Path) -> None:
    """Successive claim tokens for the same task/claimer must differ (random component)."""
    repo = _repo(tmp_path)
    _spec(repo, "010-orca-matriarch")
    register_lane("010-orca-matriarch", repo_root=repo)
    create_delegated_work("010-orca-matriarch", "T000", "Task 0", repo_root=repo)

    tokens: list[str] = []
    for _ in range(3):
        item = claim_delegated_work(
            "010-orca-matriarch", "T000", repo_root=repo, claimer_id="same-worker"
        )
        tokens.append(item.claim_token or "")
        release_delegated_work(
            "010-orca-matriarch", "T000", repo_root=repo, claim_token=item.claim_token or ""
        )

    assert len(set(tokens)) == len(tokens), "Claim tokens must be unique across successive claims"


def test_stage_reached_dependency_with_invalid_target_value_stays_active(tmp_path: Path) -> None:
    """A stage_reached dependency whose target_value is not a known stage must stay active, not crash."""
    repo = _repo(tmp_path)
    _spec(repo, "010-orca-matriarch")
    _spec(repo, "011-orca-evolve")
    register_lane("010-orca-matriarch", repo_root=repo)
    register_lane("011-orca-evolve", repo_root=repo)

    # The public add_dependency() validates target_value at write time, so we
    # must reach into private helpers to simulate what a hand-edited lane file
    # would look like at read time.  This is intentional: the test exercises
    # the read-path resilience of _evaluate_dependency_state, not the write-path.
    from speckit_orca.matriarch import (  # noqa: PLC0415
        LaneDependency,
        MatriarchPaths,
        _commit_lane_record,
        _load_lane,
        _repo_root,
    )

    paths = MatriarchPaths(_repo_root(repo))
    record = _load_lane(paths, "010-orca-matriarch")
    bad_dep = LaneDependency(
        dependency_id="bad-dep-1",
        lane_id="010-orca-matriarch",
        depends_on_lane_id="011-orca-evolve",
        strength="hard",
        target_kind="stage_reached",
        target_value="not-a-real-stage",
        state="active",
        rationale="injected bad dep",
    )
    record.dependencies.append(bad_dep.to_dict())
    record.dependency_ids.append(bad_dep.dependency_id)
    # Skip OCC check: we're intentionally bypassing normal mutation paths.
    _commit_lane_record(paths, record, expected_revision=None)

    # summarize_lane must not raise; the bad dep stays active.
    summary = summarize_lane("010-orca-matriarch", repo_root=repo)
    dep_states = [d["state"] for d in summary["dependencies"]]
    assert all(s == "active" for s in dep_states), (
        "Unknown target_value must leave the dependency active, not raise ValueError"
    )


def test_concurrent_mailbox_appends_produce_valid_jsonl(tmp_path: Path) -> None:
    """Concurrent send_mailbox_event calls must not corrupt the JSONL file."""
    repo = _repo(tmp_path)
    _spec(repo, "010-orca-matriarch")
    register_lane("010-orca-matriarch", repo_root=repo)

    errors: list[Exception] = []

    def _send(_n: int) -> None:
        try:
            send_mailbox_event(
                "010-orca-matriarch",
                repo_root=repo,
                direction="to_lane",
                sender="matriarch",
                recipient=f"worker-{_n}",
                event_type="instruction",
                payload={"n": _n},
            )
        except (OSError, MatriarchError) as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_send, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Concurrent appends raised: {errors}"

    mailbox = list_mailbox_events("010-orca-matriarch", repo_root=repo)
    assert len(mailbox["outbound"]) == 20, "All 20 events must be persisted"
    # Every stored line must be valid JSON.
    outbound_path = (
        repo / ".specify" / "orca" / "matriarch" / "mailbox" / "010-orca-matriarch" / "outbound.jsonl"
    )
    for raw in outbound_path.read_text(encoding="utf-8").splitlines():
        json.loads(raw)  # must not raise
