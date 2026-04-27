"""completion-gate capability.

Pure-Python SDD R->P->I stage gate evaluator. Composes file-presence checks
and evidence-driven gates per target stage. No LLM, no git invocation.

Stale-artifact detection (revision-aware): v1 trusts the caller to supply
`evidence.stale_artifacts`. The perf-lab integration shim (Phase 4+) will
populate this from prior review bundle hashes vs. current artifact bytes.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from orca.core.errors import Error, ErrorKind
from orca.core.result import Err, Ok, Result

VERSION = "0.1.0"

VALID_STAGES = ("plan-ready", "implement-ready", "pr-ready", "merge-ready")


@dataclass(frozen=True)
class CompletionGateInput:
    feature_dir: str
    target_stage: str
    evidence: dict = field(default_factory=dict)


@dataclass(frozen=True)
class _GateOutcome:
    gate: str
    passed: bool
    reason: str = ""


def completion_gate(inp: CompletionGateInput) -> Result[dict, Error]:
    """Evaluate gates for `target_stage` against the feature directory.

    Returns Ok(dict) with status pass/blocked/stale + per-gate outcomes,
    failed-gate names, and stale artifact list (mirrors evidence input).

    Returns Err(INPUT_INVALID) for unknown target_stage or non-existent
    feature_dir.
    """
    if inp.target_stage not in VALID_STAGES:
        return Err(Error(
            kind=ErrorKind.INPUT_INVALID,
            message=f"invalid target_stage: {inp.target_stage}; expected one of {list(VALID_STAGES)}",
        ))

    feat = Path(inp.feature_dir)
    if not feat.exists():
        return Err(Error(
            kind=ErrorKind.INPUT_INVALID,
            message=f"feature_dir does not exist: {feat}",
        ))

    raw_stale = inp.evidence.get("stale_artifacts", [])
    if not isinstance(raw_stale, list):
        return Err(Error(
            kind=ErrorKind.INPUT_INVALID,
            message=f"evidence.stale_artifacts must be a list of strings, got {type(raw_stale).__name__}",
        ))
    if not all(isinstance(s, str) for s in raw_stale):
        return Err(Error(
            kind=ErrorKind.INPUT_INVALID,
            message="evidence.stale_artifacts must contain only strings",
        ))
    stale = list(raw_stale)

    gates = _gates_for_stage(inp.target_stage)
    outcomes = [g(feat, inp.evidence) for g in gates]

    blockers = [o.gate for o in outcomes if not o.passed]

    # Stale takes precedence over blocked: a stale prior review trumps
    # current-state gate failures because the operator needs to re-review
    # before any blocker analysis is meaningful.
    if stale:
        status = "stale"
    elif blockers:
        status = "blocked"
    else:
        status = "pass"

    return Ok({
        "status": status,
        "gates_evaluated": [
            {"gate": o.gate, "passed": o.passed, "reason": o.reason}
            for o in outcomes
        ],
        "blockers": blockers,
        "stale_artifacts": stale,
    })


def _gates_for_stage(stage: str) -> tuple[Callable[[Path, dict], _GateOutcome], ...]:
    plan_ready = (_gate_spec_exists, _gate_no_unclarified)
    implement_ready = plan_ready + (_gate_plan_exists,)
    pr_ready = implement_ready + (_gate_tasks_exists,)
    merge_ready = pr_ready + (_gate_evidence_ci_green,)
    return {
        "plan-ready": plan_ready,
        "implement-ready": implement_ready,
        "pr-ready": pr_ready,
        "merge-ready": merge_ready,
    }[stage]


def _gate_spec_exists(feat: Path, _evidence: dict) -> _GateOutcome:
    p = feat / "spec.md"
    return _GateOutcome(gate="spec_exists", passed=p.exists())


def _gate_no_unclarified(feat: Path, _evidence: dict) -> _GateOutcome:
    p = feat / "spec.md"
    if not p.exists():
        return _GateOutcome(gate="no_unclarified", passed=False, reason="spec.md missing")
    text = p.read_text(encoding="utf-8", errors="replace")
    if "[NEEDS CLARIFICATION]" in text:
        return _GateOutcome(
            gate="no_unclarified",
            passed=False,
            reason="spec contains [NEEDS CLARIFICATION]",
        )
    return _GateOutcome(gate="no_unclarified", passed=True)


def _gate_plan_exists(feat: Path, _evidence: dict) -> _GateOutcome:
    p = feat / "plan.md"
    return _GateOutcome(gate="plan_exists", passed=p.exists())


def _gate_tasks_exists(feat: Path, _evidence: dict) -> _GateOutcome:
    p = feat / "tasks.md"
    return _GateOutcome(gate="tasks_exists", passed=p.exists())


def _gate_evidence_ci_green(_feat: Path, evidence: dict) -> _GateOutcome:
    # Strict True check: a string "true"/"false" or other truthy value
    # should not satisfy the gate; only explicit boolean True passes.
    val = evidence.get("ci_green") is True
    return _GateOutcome(
        gate="ci_green",
        passed=val,
        reason="" if val else "evidence.ci_green=true required",
    )
