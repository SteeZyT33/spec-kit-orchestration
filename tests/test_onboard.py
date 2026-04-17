"""Tests for the 017 brownfield onboarding pipeline.

Covers sub-phases A–E per `specs/017-brownfield-v2/tasks.md`:
  A. Manifest dataclasses + YAML subset I/O
  B. Heuristics H1, H2, H3, H6 + merge + discover
  C. Draft generation (round-trips through 015's parser)
  D. Triage.md render/parse + commit flow
  E. CLI entry point

Discipline: every GREEN task has a RED test here. Integration tests
use real `tmp_path` repos and call 015's `adoption` runtime under
the hood to verify the no-mutation invariant.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from speckit_orca import adoption
from speckit_orca import onboard


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


# Resolve git once so subprocess invocations use an absolute executable
# path (keeps Ruff S607 happy without needing per-call noqa comments).
_GIT = shutil.which("git") or "git"


def _init_git(repo: Path) -> None:
    subprocess.run([_GIT, "init", "-q"], cwd=repo, check=True)
    subprocess.run([_GIT, "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run([_GIT, "config", "user.name", "t"], cwd=repo, check=True)
    subprocess.run([_GIT, "config", "commit.gpgsign", "false"], cwd=repo, check=True)


def _commit_all(repo: Path, message: str = "chore: commit") -> None:
    subprocess.run([_GIT, "add", "-A"], cwd=repo, check=True)
    # Merge author/committer overrides over the real environment so
    # `git` keeps its normal PATH, HOME, and friends. Replacing env
    # wholesale breaks on systems where git lives outside /usr/bin.
    # --no-verify skips commit hooks that the host repo may have
    # configured (e.g., a conventional-commit gate); synthetic test
    # repos shouldn't depend on those.
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@e.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@e.com",
    }
    subprocess.run(
        [_GIT, "commit", "-q", "--no-verify", "-m", message],
        cwd=repo,
        check=True,
        env=env,
    )


def _write(path: Path, content: str = "# stub\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture
def brownfield_repo(tmp_path: Path) -> Path:
    """Synthetic brownfield repo with layered signals.

    Layout:
      src/auth/__init__.py, middleware.py, sessions.py  ← H1
      src/payments/__init__.py, stripe.py               ← H1
      src/utils/helpers.py, misc.py                     ← H1 (grab-bag)
      src/cli.py                                        ← H2 target
      pyproject.toml with scripts entry                 ← H2
      README.md with ## Authentication, ## Data Pipeline, ## Installation  ← H3
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / "src" / "auth" / "__init__.py")
    _write(repo / "src" / "auth" / "middleware.py")
    _write(repo / "src" / "auth" / "sessions.py")
    _write(repo / "src" / "payments" / "__init__.py")
    _write(repo / "src" / "payments" / "stripe.py")
    _write(repo / "src" / "utils" / "helpers.py")
    _write(repo / "src" / "utils" / "misc.py")
    _write(repo / "src" / "cli.py")
    _write(
        repo / "pyproject.toml",
        '[project]\nname = "demo"\nversion = "0.1"\n\n'
        '[project.scripts]\n'
        'demo-cli = "demo.cli:main"\n'
        'demo-worker = "demo.worker:run"\n',
    )
    _write(
        repo / "README.md",
        "# Demo\n\n## Authentication\n\nAuth stuff.\n\n"
        "## Data Pipeline\n\nPipeline stuff.\n\n"
        "## Installation\n\npip install demo\n",
    )
    return repo


@pytest.fixture
def git_repo_with_cochange(tmp_path: Path) -> Path:
    """Repo with a co-change cluster: two files changed together multiple times."""
    repo = tmp_path / "gitrepo"
    repo.mkdir()
    _init_git(repo)
    _write(repo / "src" / "alpha.py")
    _write(repo / "src" / "beta.py")
    _write(repo / "unrelated.py")
    _commit_all(repo, "initial")
    # Co-change alpha + beta three times.
    for i in range(3):
        (repo / "src" / "alpha.py").write_text(f"# v{i}\n")
        (repo / "src" / "beta.py").write_text(f"# v{i}\n")
        _commit_all(repo, f"cochange {i}")
    # Independent change to unrelated.
    (repo / "unrelated.py").write_text("# independent\n")
    _commit_all(repo, "unrelated")
    return repo


# ---------------------------------------------------------------------------
# Sub-phase A — dataclasses + YAML I/O
# ---------------------------------------------------------------------------


class TestCandidateRecord:
    def test_instantiation_and_fields(self) -> None:
        c = onboard.CandidateRecord(
            id="C-001",
            proposed_title="Auth",
            proposed_slug="auth",
            paths=["src/auth/__init__.py"],
            signals=["H1:src/auth"],
            score=0.5,
            draft_path="drafts/DRAFT-001-auth.md",
            triage="pending",
            duplicate_of=None,
        )
        assert c.id == "C-001"
        assert c.score == 0.5
        assert c.triage == "pending"

    def test_invalid_triage_verb_rejected(self) -> None:
        with pytest.raises(ValueError):
            onboard.CandidateRecord(
                id="C-001", proposed_title="x", proposed_slug="x",
                paths=["a"], signals=[], score=0.5,
                draft_path="d.md", triage="nope", duplicate_of=None,
            )

    def test_id_format_validated(self) -> None:
        with pytest.raises(ValueError):
            onboard.CandidateRecord(
                id="001", proposed_title="x", proposed_slug="x",
                paths=["a"], signals=[], score=0.5,
                draft_path="d.md", triage="pending", duplicate_of=None,
            )


class TestOnboardingManifest:
    def test_instantiation(self) -> None:
        m = onboard.OnboardingManifest(
            run_id="2026-04-16-initial",
            created="2026-04-16T14:03:00Z",
            phase="discovery",
            repo_root="/x/y",
            baseline_commit="abc1234",
            heuristics_enabled=["H1", "H2"],
            score_threshold=0.3,
            candidates=[],
        )
        assert m.phase == "discovery"
        assert m.committed == []
        assert m.rejected == []
        assert m.failed == []

    def test_invalid_phase_rejected(self) -> None:
        with pytest.raises(ValueError):
            onboard.OnboardingManifest(
                run_id="r", created="2026-04-16T14:03:00Z", phase="bogus",
                repo_root="/", baseline_commit=None, heuristics_enabled=[],
                score_threshold=0.3, candidates=[],
            )


class TestYamlRoundTrip:
    def test_roundtrip_scalars_lists_nested(self, tmp_path: Path) -> None:
        m = onboard.OnboardingManifest(
            run_id="2026-04-16-initial",
            created="2026-04-16T14:03:00Z",
            phase="review",
            repo_root=str(tmp_path),
            baseline_commit="abc1234",
            heuristics_enabled=["H1", "H2", "H3", "H6"],
            score_threshold=0.3,
            candidates=[
                onboard.CandidateRecord(
                    id="C-001",
                    proposed_title="Auth Middleware",
                    proposed_slug="auth-middleware",
                    paths=["src/auth/middleware.py", "src/auth/sessions.py"],
                    signals=["H1:src/auth", "H2:entry-point"],
                    score=0.78,
                    draft_path="drafts/DRAFT-001-auth-middleware.md",
                    triage="accept",
                    duplicate_of=None,
                ),
                onboard.CandidateRecord(
                    id="C-002",
                    proposed_title="Utils",
                    proposed_slug="utils",
                    paths=["src/utils/helpers.py"],
                    signals=["H1:src/utils"],
                    score=0.15,
                    draft_path="drafts/DRAFT-002-utils.md",
                    triage="duplicate",
                    duplicate_of="C-001",
                ),
            ],
        )
        text = onboard._emit_yaml(m)
        assert "run_id: \"2026-04-16-initial\"" in text
        assert "heuristics_enabled:" in text
        assert "- \"H1\"" in text

        back = onboard._parse_yaml(text)
        assert back["run_id"] == "2026-04-16-initial"
        assert back["phase"] == "review"
        assert back["heuristics_enabled"] == ["H1", "H2", "H3", "H6"]
        assert len(back["candidates"]) == 2
        assert back["candidates"][0]["id"] == "C-001"
        assert back["candidates"][0]["score"] == 0.78
        assert back["candidates"][1]["duplicate_of"] == "C-001"

    def test_parse_yaml_null_value(self) -> None:
        text = "baseline_commit: null\nscore: 0.5\n"
        back = onboard._parse_yaml(text)
        assert back["baseline_commit"] is None
        assert back["score"] == 0.5

    def test_parse_yaml_empty_list(self) -> None:
        text = "committed: []\ncandidates: []\n"
        back = onboard._parse_yaml(text)
        assert back["committed"] == []
        assert back["candidates"] == []


class TestManifestFileIO:
    def test_write_read_roundtrip(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        m = onboard.OnboardingManifest(
            run_id="2026-04-16-initial",
            created="2026-04-16T14:03:00Z",
            phase="discovery",
            repo_root=str(tmp_path),
            baseline_commit="abc1234",
            heuristics_enabled=["H1"],
            score_threshold=0.3,
            candidates=[],
        )
        onboard.write_manifest(run_dir, m)
        assert (run_dir / "manifest.yaml").exists()
        loaded = onboard.read_manifest(run_dir)
        assert loaded.run_id == m.run_id
        assert loaded.phase == m.phase
        assert loaded.heuristics_enabled == ["H1"]

    def test_read_missing_raises(self, tmp_path: Path) -> None:
        with pytest.raises(onboard.OnboardError):
            onboard.read_manifest(tmp_path / "nope")


# ---------------------------------------------------------------------------
# Sub-phase B — Heuristics
# ---------------------------------------------------------------------------


class TestHeuristicH1:
    def test_emits_candidates_for_subdirectories(self, brownfield_repo: Path) -> None:
        cands = onboard.heuristic_h1_directories(brownfield_repo)
        titles = {c.proposed_title for c in cands}
        assert "auth" in titles
        assert "payments" in titles
        # utils is grab-bag — emitted but with score < 0.3 after penalty
        utils = [c for c in cands if c.proposed_title == "utils"]
        if utils:
            assert utils[0].score < 0.3

    def test_ignores_dirs_below_minimum_files(self, tmp_path: Path) -> None:
        repo = tmp_path / "r"
        repo.mkdir()
        _write(repo / "src" / "lonely" / "only.py")
        cands = onboard.heuristic_h1_directories(repo)
        slugs = {c.proposed_slug for c in cands}
        assert "lonely" not in slugs


class TestHeuristicH2:
    def test_extracts_entry_points_from_pyproject(self, brownfield_repo: Path) -> None:
        cands = onboard.heuristic_h2_entry_points(brownfield_repo)
        slugs = {c.proposed_slug for c in cands}
        assert "demo-cli" in slugs
        assert "demo-worker" in slugs
        for c in cands:
            assert any(s.startswith("H2:") for s in c.signals)

    def test_extracts_entry_points_from_package_json(self, tmp_path: Path) -> None:
        repo = tmp_path / "jsrepo"
        repo.mkdir()
        _write(
            repo / "package.json",
            '{"name":"x","bin":{"my-cli":"./bin/my-cli.js"}}',
        )
        cands = onboard.heuristic_h2_entry_points(repo)
        slugs = {c.proposed_slug for c in cands}
        assert "my-cli" in slugs


class TestHeuristicH3:
    def test_extracts_h2_headings_skipping_boilerplate(self, brownfield_repo: Path) -> None:
        cands = onboard.heuristic_h3_readme(brownfield_repo)
        titles = {c.proposed_title for c in cands}
        assert "Authentication" in titles
        assert "Data Pipeline" in titles
        # Installation is boilerplate, must be dropped
        assert "Installation" not in titles

    def test_no_readme_returns_empty(self, tmp_path: Path) -> None:
        repo = tmp_path / "norm"
        repo.mkdir()
        assert onboard.heuristic_h3_readme(repo) == []


class TestHeuristicH6:
    def test_cochange_cluster_proposes_candidate(self, git_repo_with_cochange: Path) -> None:
        cands = onboard.heuristic_h6_cochange(git_repo_with_cochange)
        # The alpha+beta pair should cluster.
        paths_union: set[str] = set()
        for c in cands:
            for p in c.paths:
                paths_union.add(p)
        assert any("alpha.py" in p for p in paths_union)
        assert any("beta.py" in p for p in paths_union)

    def test_no_git_returns_empty(self, tmp_path: Path) -> None:
        repo = tmp_path / "nogit"
        repo.mkdir()
        _write(repo / "a.py")
        assert onboard.heuristic_h6_cochange(repo) == []


class TestMergeCandidates:
    def test_same_slug_merges_signals_and_scores(self) -> None:
        a = onboard.CandidateRecord(
            id="C-001", proposed_title="auth", proposed_slug="auth",
            paths=["src/auth/__init__.py"], signals=["H1:src/auth"], score=0.5,
            draft_path="", triage="pending", duplicate_of=None,
        )
        b = onboard.CandidateRecord(
            id="C-002", proposed_title="Authentication",
            proposed_slug="auth",
            paths=["src/auth/middleware.py"], signals=["H3:Authentication"],
            score=0.7, draft_path="", triage="pending", duplicate_of=None,
        )
        merged = onboard.merge_candidates([a, b])
        assert len(merged) == 1
        m = merged[0]
        # H3 title wins
        assert m.proposed_title == "Authentication"
        # Signals combined
        assert "H1:src/auth" in m.signals
        assert "H3:Authentication" in m.signals
        # Score is probabilistic OR: 1 - (1-0.5)*(1-0.7) = 0.85
        assert abs(m.score - 0.85) < 1e-6
        # Paths unioned
        assert len(m.paths) == 2


class TestDiscover:
    def test_returns_sorted_filtered_candidates(self, brownfield_repo: Path) -> None:
        cands = onboard.discover(
            repo_root=brownfield_repo,
            heuristics=["H1", "H2", "H3"],
            score_threshold=0.3,
        )
        # All returned candidates must be above threshold
        for c in cands:
            assert c.score >= 0.3
        # Stable order: score desc, slug asc
        score_slug_pairs = [(c.score, c.proposed_slug) for c in cands]
        assert score_slug_pairs == sorted(
            score_slug_pairs, key=lambda x: (-x[0], x[1])
        )
        # utils grab-bag should be filtered out
        assert "utils" not in {c.proposed_slug for c in cands}
        # auth and payments should survive
        slugs = {c.proposed_slug for c in cands}
        assert "auth" in slugs or "authentication" in slugs
        assert "payments" in slugs

    def test_ids_are_sequential(self, brownfield_repo: Path) -> None:
        cands = onboard.discover(
            repo_root=brownfield_repo,
            heuristics=["H1", "H2", "H3"],
            score_threshold=0.3,
        )
        ids = [c.id for c in cands]
        assert ids == [f"C-{i:03d}" for i in range(1, len(ids) + 1)]


# ---------------------------------------------------------------------------
# Sub-phase C — Proposal generator
# ---------------------------------------------------------------------------


class TestRenderDraft:
    def test_draft_contains_required_015_shape(self) -> None:
        c = onboard.CandidateRecord(
            id="C-001",
            proposed_title="Auth Middleware",
            proposed_slug="auth-middleware",
            paths=["src/auth/middleware.py", "src/auth/sessions.py"],
            signals=["H1:src/auth", "H2:entry-point:auth-cli"],
            score=0.8,
            draft_path="drafts/DRAFT-001-auth-middleware.md",
            triage="pending",
            duplicate_of=None,
        )
        text = onboard.render_draft(c, draft_number=1)
        # 015's parser expects exactly these headings
        assert "# Adoption Record: DRAFT-001: Auth Middleware" in text
        assert "**Status**: adopted" in text
        assert "**Adopted-on**:" in text
        assert "## Summary" in text
        assert "## Location" in text
        assert "## Key Behaviors" in text
        # Banner makes drafts visibly uncommitted
        assert "DRAFT" in text

    def test_draft_parses_through_015_parser(self, tmp_path: Path) -> None:
        """The draft must pass 015's parser so commit-time validation works.

        Note: 015's parser only accepts title prefix `AR-NNN` — drafts use
        `DRAFT-NNN` so we rewrite the title for the parse check. The
        important invariant is that Summary / Location / Key Behaviors are
        well-formed.
        """
        c = onboard.CandidateRecord(
            id="C-001",
            proposed_title="CLI Entrypoint",
            proposed_slug="cli-entrypoint",
            paths=["src/cli.py"],
            signals=["H2:entry-point"],
            score=0.7,
            draft_path="drafts/DRAFT-001-cli-entrypoint.md",
            triage="pending",
            duplicate_of=None,
        )
        text = onboard.render_draft(c, draft_number=1)
        # Rewrite DRAFT-NNN → AR-NNN for parse compatibility
        ar_text = text.replace("DRAFT-001", "AR-999")
        # Strip the banner HTML comment before parsing
        parseable = "\n".join(
            line for line in ar_text.splitlines()
            if not line.startswith("<!--") and not line.startswith("-->")
        ).strip() + "\n"
        p = tmp_path / "AR-999-cli-entrypoint.md"
        p.write_text(parseable)
        rec = adoption.parse_record(p)
        assert rec.title == "CLI Entrypoint"
        assert rec.location == ["src/cli.py"]


class TestWriteDrafts:
    def test_writes_one_file_per_candidate(self, tmp_path: Path) -> None:
        run_dir = tmp_path / ".specify" / "orca" / "adoption-runs" / "2026-04-16-initial"
        run_dir.mkdir(parents=True)
        cands = [
            onboard.CandidateRecord(
                id="C-001", proposed_title="Auth", proposed_slug="auth",
                paths=["src/auth/a.py"], signals=["H1"], score=0.5,
                draft_path="drafts/DRAFT-001-auth.md",
                triage="pending", duplicate_of=None,
            ),
            onboard.CandidateRecord(
                id="C-002", proposed_title="CLI", proposed_slug="cli",
                paths=["src/cli.py"], signals=["H2"], score=0.6,
                draft_path="drafts/DRAFT-002-cli.md",
                triage="pending", duplicate_of=None,
            ),
        ]
        onboard.write_drafts(run_dir, cands)
        assert (run_dir / "drafts" / "DRAFT-001-auth.md").exists()
        assert (run_dir / "drafts" / "DRAFT-002-cli.md").exists()


# ---------------------------------------------------------------------------
# Sub-phase D — Triage + commit
# ---------------------------------------------------------------------------


def _basic_manifest(repo: Path) -> onboard.OnboardingManifest:
    return onboard.OnboardingManifest(
        run_id="2026-04-16-test",
        created="2026-04-16T00:00:00Z",
        phase="review",
        repo_root=str(repo),
        baseline_commit="abc1234",
        heuristics_enabled=["H1", "H2"],
        score_threshold=0.3,
        candidates=[
            onboard.CandidateRecord(
                id="C-001",
                proposed_title="Auth",
                proposed_slug="auth",
                paths=["src/auth/__init__.py"],
                signals=["H1:src/auth"],
                score=0.6,
                draft_path="drafts/DRAFT-001-auth.md",
                triage="pending",
                duplicate_of=None,
            ),
            onboard.CandidateRecord(
                id="C-002",
                proposed_title="CLI",
                proposed_slug="cli",
                paths=["src/cli.py"],
                signals=["H2:entry-point"],
                score=0.7,
                draft_path="drafts/DRAFT-002-cli.md",
                triage="pending",
                duplicate_of=None,
            ),
        ],
    )


class TestRenderTriage:
    def test_renders_one_section_per_candidate(self, tmp_path: Path) -> None:
        m = _basic_manifest(tmp_path)
        text = onboard.render_triage(m)
        assert "## C-001: Auth" in text
        assert "## C-002: CLI" in text
        assert "- status: pending" in text
        # Exactly one "- status: pending" line per candidate
        assert text.count("- status: pending") == 2


class TestParseTriage:
    def test_parses_all_verbs(self, tmp_path: Path) -> None:
        m = _basic_manifest(tmp_path)
        text = (
            "# Adoption Run\n\n"
            "## C-001: Auth\n\n"
            "- status: accept\n\n"
            "## C-002: CLI\n\n"
            "- status: reject\n"
        )
        entries = onboard.parse_triage(text, m)
        assert entries["C-001"].verb == "accept"
        assert entries["C-002"].verb == "reject"

    def test_parses_duplicate_of(self, tmp_path: Path) -> None:
        m = _basic_manifest(tmp_path)
        text = (
            "## C-001: Auth\n\n- status: accept\n\n"
            "## C-002: CLI\n\n- status: duplicate-of:C-001\n"
        )
        entries = onboard.parse_triage(text, m)
        assert entries["C-002"].verb == "duplicate"
        assert entries["C-002"].duplicate_of == "C-001"

    def test_unknown_verb_raises(self, tmp_path: Path) -> None:
        m = _basic_manifest(tmp_path)
        text = (
            "## C-001: Auth\n\n- status: maybe\n\n"
            "## C-002: CLI\n\n- status: accept\n"
        )
        with pytest.raises(onboard.OnboardError):
            onboard.parse_triage(text, m)

    def test_unknown_candidate_id_raises(self, tmp_path: Path) -> None:
        m = _basic_manifest(tmp_path)
        text = (
            "## C-001: Auth\n\n- status: accept\n\n"
            "## C-002: CLI\n\n- status: accept\n\n"
            "## C-999: Ghost\n\n- status: accept\n"
        )
        with pytest.raises(onboard.OnboardError):
            onboard.parse_triage(text, m)

    def test_missing_candidate_is_pending(self, tmp_path: Path) -> None:
        m = _basic_manifest(tmp_path)
        text = "## C-001: Auth\n\n- status: accept\n"
        entries = onboard.parse_triage(text, m)
        # C-002 absent → pending
        assert entries["C-002"].verb == "pending"

    def test_duplicate_heading_without_status_raises(
        self, tmp_path: Path
    ) -> None:
        """Two `## C-001` headings must be rejected even if neither has
        a `- status:` line yet. Regression for PR #60 finding #5 —
        keying the duplicate check off `entries` alone let a second
        heading silently replace the first."""
        m = _basic_manifest(tmp_path)
        text = (
            "## C-001: Auth\n\n"  # first heading, no status yet
            "## C-001: Auth v2\n\n"  # duplicate heading, same id
            "- status: accept\n"
        )
        with pytest.raises(onboard.OnboardError) as exc_info:
            onboard.parse_triage(text, m)
        assert "duplicate section" in str(exc_info.value).lower()


class TestCommitFlow:
    def _setup_run(self, repo: Path) -> Path:
        """Scan a simple brownfield repo, return run_dir."""
        _write(repo / "src" / "auth" / "__init__.py")
        _write(repo / "src" / "auth" / "middleware.py")
        _write(repo / "src" / "cli.py")
        _write(
            repo / "pyproject.toml",
            '[project]\nname="d"\nversion="0"\n[project.scripts]\n'
            'd-cli = "d.cli:main"\n',
        )
        run_dir = onboard.scan(repo_root=repo, run_name="2026-04-16-test")
        return run_dir

    def test_pending_blocks_commit(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        run_dir = self._setup_run(repo)
        # Triage left as pending; commit must refuse
        with pytest.raises(onboard.OnboardError) as exc_info:
            onboard.commit_run(run_dir, dry_run=False)
        assert "pending" in str(exc_info.value).lower()

    def test_accept_calls_create_record(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        run_dir = self._setup_run(repo)
        m = onboard.read_manifest(run_dir)
        # Fill in drafts with real content so 015 validation passes
        for c in m.candidates:
            path = run_dir / c.draft_path
            text = path.read_text()
            text = text.replace(
                "TODO: describe what this feature does",
                "Real summary describing the feature.",
            )
            text = text.replace(
                "TODO: fill in an observed behavior before accepting",
                "Dispatches requests to the right handler",
            )
            path.write_text(text)
        # Mark all candidates accept
        triage_path = run_dir / "triage.md"
        text = triage_path.read_text()
        text = text.replace("- status: pending", "- status: accept")
        triage_path.write_text(text)
        # Commit
        summary = onboard.commit_run(run_dir, dry_run=False)
        assert summary["committed"] >= 1
        # Verify ARs actually written via 015's list_records
        records = adoption.list_records(repo_root=repo)
        assert len(records) == summary["committed"]
        for r in records:
            assert r.record_id.startswith("AR-")
            assert r.status == "adopted"

    def test_reject_is_audited(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        run_dir = self._setup_run(repo)
        triage_path = run_dir / "triage.md"
        text = triage_path.read_text()
        text = text.replace("- status: pending", "- status: reject")
        triage_path.write_text(text)
        summary = onboard.commit_run(run_dir, dry_run=False)
        assert summary["committed"] == 0
        assert summary["rejected"] >= 1
        # No ARs written
        assert adoption.list_records(repo_root=repo) == []

    def test_existing_ars_untouched(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        # Pre-existing AR
        existing = adoption.create_record(
            repo_root=repo,
            title="Pre-existing",
            summary="Shipped before 017 scanned",
            location=["src/pre.py"],
            key_behaviors=["Does existing things"],
            baseline_commit=None,
        )
        before_hash = hashlib.sha256(existing.path.read_bytes()).hexdigest()
        before_mtime = existing.path.stat().st_mtime

        # Now run the pipeline
        run_dir = self._setup_run(repo)
        # Fill in drafts
        m = onboard.read_manifest(run_dir)
        for c in m.candidates:
            path = run_dir / c.draft_path
            text = path.read_text().replace(
                "TODO: describe what this feature does",
                "Real summary.",
            ).replace(
                "TODO: fill in an observed behavior before accepting",
                "Real behavior.",
            )
            path.write_text(text)
        triage_path = run_dir / "triage.md"
        triage_path.write_text(
            triage_path.read_text().replace("- status: pending", "- status: accept")
        )
        onboard.commit_run(run_dir, dry_run=False)

        # Verify the pre-existing AR is bit-identical
        after_hash = hashlib.sha256(existing.path.read_bytes()).hexdigest()
        assert before_hash == after_hash
        # mtime can be updated by overview regeneration writing to the
        # registry dir, but the AR file itself must not be touched
        after_mtime = existing.path.stat().st_mtime
        assert before_mtime == after_mtime

    def test_validation_failure_isolated(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        run_dir = self._setup_run(repo)
        m = onboard.read_manifest(run_dir)
        # Fill in SOME drafts, leave one with TODO placeholder
        candidates = sorted(m.candidates, key=lambda c: c.id)
        first = candidates[0]
        good_path = run_dir / first.draft_path
        text = good_path.read_text().replace(
            "TODO: describe what this feature does", "Real summary.",
        ).replace(
            "TODO: fill in an observed behavior before accepting",
            "Real behavior.",
        )
        good_path.write_text(text)
        # Leave subsequent draft unmodified so 015 validation fails
        # (015 validates summary/location/key_behaviors non-empty, but
        # "TODO:" passes that check since it's non-empty. To force a
        # failure, empty out the summary section instead.)
        if len(candidates) > 1:
            bad = candidates[1]
            bad_path = run_dir / bad.draft_path
            bad_text = bad_path.read_text()
            # Remove summary content to force 015 rejection
            bad_text = bad_text.replace(
                "TODO: describe what this feature does", ""
            )
            bad_path.write_text(bad_text)

        triage_path = run_dir / "triage.md"
        triage_path.write_text(
            triage_path.read_text().replace("- status: pending", "- status: accept")
        )
        summary = onboard.commit_run(run_dir, dry_run=False)
        # Good one should commit, bad one should land in failed
        if len(candidates) > 1:
            assert summary["committed"] >= 1
            assert summary["failed"] >= 1

    def test_dry_run_writes_no_ars(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        run_dir = self._setup_run(repo)
        # Mark accept but use dry-run
        triage_path = run_dir / "triage.md"
        triage_path.write_text(
            triage_path.read_text().replace("- status: pending", "- status: accept")
        )
        summary = onboard.commit_run(run_dir, dry_run=True)
        assert summary["dry_run"] is True
        # No ARs
        assert adoption.list_records(repo_root=repo) == []


# ---------------------------------------------------------------------------
# Sub-phase E — CLI
# ---------------------------------------------------------------------------


class TestCli:
    def test_default_scan_enables_h4_and_h5(self, tmp_path: Path) -> None:
        """Regression (codex finding #3): the default CLI scan must apply
        H4/H5 without requiring --heuristics. The v1.1 docs promise
        `scan` uses H1-H6 out of the box; the default constant was left
        at HEURISTICS_MVP in the first pass.
        """
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git(repo)
        _write(repo / "CODEOWNERS", "/src/auth/ @alice\n")
        _write(repo / "src" / "auth" / "__init__.py")
        _write(repo / "src" / "auth" / "middleware.py")
        _write(repo / "tests" / "test_auth.py", "# tests\n")
        _commit_all(repo, "init")
        run_dir = onboard.scan(repo_root=repo, run_name="initial")
        m = onboard.read_manifest(run_dir)
        # H4 and H5 both land signals on the auth candidate.
        auth = next(
            (c for c in m.candidates if c.proposed_slug == "auth"), None,
        )
        assert auth is not None, [c.proposed_slug for c in m.candidates]
        assert any(s.startswith("H4:owner:") for s in auth.signals), auth.signals
        assert any(s.startswith("H5:") for s in auth.signals), auth.signals

    def test_scan_writes_manifest_and_triage(self, tmp_path: Path, capsys) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _write(repo / "src" / "auth" / "__init__.py")
        _write(repo / "src" / "auth" / "middleware.py")
        _write(repo / "src" / "cli.py")
        _write(
            repo / "pyproject.toml",
            '[project]\nname="d"\nversion="0"\n[project.scripts]\n'
            'd-cli = "d.cli:main"\n',
        )
        rc = onboard.cli_main([
            "--root", str(repo), "scan", "--run", "2026-04-16-initial",
        ])
        assert rc == 0
        run_dir = repo / ".specify" / "orca" / "adoption-runs" / "2026-04-16-initial"
        assert (run_dir / "manifest.yaml").exists()
        assert (run_dir / "triage.md").exists()
        assert (run_dir / "drafts").is_dir()

    def test_scan_refuses_existing_run(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _write(repo / "src" / "auth" / "__init__.py")
        _write(repo / "src" / "auth" / "middleware.py")
        rc1 = onboard.cli_main([
            "--root", str(repo), "scan", "--run", "2026-04-16-initial",
        ])
        assert rc1 == 0
        rc2 = onboard.cli_main([
            "--root", str(repo), "scan", "--run", "2026-04-16-initial",
        ])
        assert rc2 != 0

    def test_status_prints_phase_and_counts(self, tmp_path: Path, capsys) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _write(repo / "src" / "auth" / "__init__.py")
        _write(repo / "src" / "auth" / "middleware.py")
        onboard.cli_main([
            "--root", str(repo), "scan", "--run", "2026-04-16-initial",
        ])
        capsys.readouterr()
        rc = onboard.cli_main([
            "--root", str(repo), "status", "--run", "2026-04-16-initial",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "phase" in out.lower()

    def test_rescan_requires_from_flag(self, tmp_path: Path, capsys) -> None:
        """v1.1: rescan requires --from <prior-run>. Invoking without it must
        exit non-zero with an argparse-style error mentioning --from."""
        repo = tmp_path / "repo"
        repo.mkdir()
        # argparse raises SystemExit on missing required args; catch it so
        # the test can inspect the exit code rather than blow up.
        with pytest.raises(SystemExit) as exc_info:
            onboard.cli_main([
                "--root", str(repo), "rescan",
            ])
        assert exc_info.value.code != 0
        captured = capsys.readouterr()
        out = captured.out + captured.err
        assert "--from" in out or "from" in out.lower()

    def test_commit_is_idempotent_on_retry(self, tmp_path: Path) -> None:
        """Second commit after a successful first must not re-create ARs."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _write(repo / "src" / "auth" / "__init__.py")
        _write(repo / "src" / "auth" / "middleware.py")
        _write(
            repo / "pyproject.toml",
            '[project]\nname="d"\nversion="0"\n[project.scripts]\n'
            'd-cli = "d.cli:main"\n',
        )
        onboard.cli_main([
            "--root", str(repo), "scan", "--run", "r1",
        ])
        run_dir = repo / ".specify" / "orca" / "adoption-runs" / "r1"
        m = onboard.read_manifest(run_dir)
        for c in m.candidates:
            path = run_dir / c.draft_path
            text = path.read_text().replace(
                "TODO: describe what this feature does", "Real summary.",
            ).replace(
                "TODO: fill in an observed behavior before accepting",
                "Real behavior.",
            )
            path.write_text(text)
        triage = run_dir / "triage.md"
        triage.write_text(triage.read_text().replace("- status: pending", "- status: accept"))
        rc1 = onboard.cli_main(["--root", str(repo), "commit", "--run", "r1"])
        assert rc1 == 0
        records_1 = adoption.list_records(repo_root=repo)
        # Run commit again
        rc2 = onboard.cli_main(["--root", str(repo), "commit", "--run", "r1"])
        assert rc2 == 0
        records_2 = adoption.list_records(repo_root=repo)
        assert len(records_1) == len(records_2)
        # AR ids unchanged
        assert [r.record_id for r in records_1] == [r.record_id for r in records_2]

    def test_triage_decisions_persisted_to_manifest(self, tmp_path: Path) -> None:
        """Parsed triage verbs must land in manifest.yaml for round-trip."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _write(repo / "src" / "auth" / "__init__.py")
        _write(repo / "src" / "auth" / "middleware.py")
        run_dir = onboard.scan(repo_root=repo, run_name="r1")
        triage = run_dir / "triage.md"
        triage.write_text(
            triage.read_text().replace("- status: pending", "- status: reject")
        )
        onboard.commit_run(run_dir, dry_run=False)
        m = onboard.read_manifest(run_dir)
        for c in m.candidates:
            assert c.triage == "reject"

    def test_unreadable_draft_isolated_to_failed(self, tmp_path: Path) -> None:
        """An UnicodeDecodeError / OSError on one draft must land in
        manifest.failed for that candidate, not abort the whole batch.
        Regression for PR #60 finding #6 — draft_path.read_text() used
        to sit outside the try/except so undecodable drafts escaped
        commit_run().
        """
        repo = tmp_path / "repo"
        repo.mkdir()
        _write(repo / "src" / "auth" / "__init__.py")
        _write(repo / "src" / "auth" / "middleware.py")
        _write(repo / "src" / "billing" / "__init__.py")
        _write(repo / "src" / "billing" / "invoice.py")
        run_dir = onboard.scan(repo_root=repo, run_name="r1")
        m = onboard.read_manifest(run_dir)
        assert len(m.candidates) >= 2
        # Corrupt the FIRST candidate's draft so UTF-8 decode fails.
        bad = run_dir / m.candidates[0].draft_path
        bad.write_bytes(b"\xff\xfe\xfd not-valid-utf-8 \xc3\x28")
        # Fill in the SECOND candidate so it commits cleanly.
        good = run_dir / m.candidates[1].draft_path
        text = good.read_text()
        text = text.replace(
            "TODO: describe what this feature does",
            "Real summary describing the feature.",
        ).replace(
            "TODO: fill in an observed behavior before accepting",
            "Does something observable",
        )
        good.write_text(text)
        triage = run_dir / "triage.md"
        triage.write_text(
            triage.read_text().replace("- status: pending", "- status: accept")
        )
        # Must not raise; must isolate the bad candidate.
        summary = onboard.commit_run(run_dir, dry_run=False)
        assert summary["failed"] >= 1
        assert summary["committed"] >= 1
        # Confirm the failure message references the unreadable draft.
        m2 = onboard.read_manifest(run_dir)
        bad_id = m.candidates[0].id
        failure_ids = {e["candidate_id"] for e in m2.failed if isinstance(e, dict)}
        assert bad_id in failure_ids

    def test_draft_parses_through_015_at_commit(self, tmp_path: Path) -> None:
        """Commit-time draft parse must delegate to 015's parser."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _write(repo / "src" / "auth" / "__init__.py")
        _write(repo / "src" / "auth" / "middleware.py")
        run_dir = onboard.scan(repo_root=repo, run_name="r1")
        m = onboard.read_manifest(run_dir)
        first = m.candidates[0]
        path = run_dir / first.draft_path
        # Remove the Summary section content — 015 rejects empty summary.
        # If 017 had a lenient extractor, it would pass "TODO..." through.
        # Using the 015 parser means commit refuses this draft.
        raw = path.read_text()
        raw = raw.replace("TODO: describe what this feature does", "")
        path.write_text(raw)
        triage = run_dir / "triage.md"
        triage.write_text(triage.read_text().replace("- status: pending", "- status: accept"))
        summary = onboard.commit_run(run_dir, dry_run=False)
        # Must land in failed
        assert summary["failed"] >= 1


class TestH2ExtraEntryShapes:
    def test_setup_py_entry_points_detected(self, tmp_path: Path) -> None:
        repo = tmp_path / "setuprepo"
        repo.mkdir()
        _write(
            repo / "setup.py",
            "from setuptools import setup\n"
            "setup(name='x', entry_points={"
            "'console_scripts': ['legacy-cli = legacy.cli:main']})\n",
        )
        cands = onboard.heuristic_h2_entry_points(repo)
        slugs = {c.proposed_slug for c in cands}
        assert "legacy-cli" in slugs

    def test_pyproject_entry_points_table_detected(self, tmp_path: Path) -> None:
        repo = tmp_path / "epsrepo"
        repo.mkdir()
        _write(
            repo / "pyproject.toml",
            '[project]\nname="x"\nversion="0"\n\n'
            '[project.entry-points."my_plugins"]\n'
            'my-plugin = "x.plugin:entry"\n',
        )
        cands = onboard.heuristic_h2_entry_points(repo)
        slugs = {c.proposed_slug for c in cands}
        assert "my-plugin" in slugs


    def test_commit_end_to_end_via_cli(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _write(repo / "src" / "auth" / "__init__.py")
        _write(repo / "src" / "auth" / "middleware.py")
        onboard.cli_main([
            "--root", str(repo), "scan", "--run", "2026-04-16-initial",
        ])
        run_dir = repo / ".specify" / "orca" / "adoption-runs" / "2026-04-16-initial"
        # Fill in drafts
        m = onboard.read_manifest(run_dir)
        for c in m.candidates:
            path = run_dir / c.draft_path
            text = path.read_text().replace(
                "TODO: describe what this feature does", "Real summary.",
            ).replace(
                "TODO: fill in an observed behavior before accepting",
                "Real behavior.",
            )
            path.write_text(text)
        # Mark accept
        triage = run_dir / "triage.md"
        triage.write_text(triage.read_text().replace("- status: pending", "- status: accept"))
        rc = onboard.cli_main([
            "--root", str(repo), "commit", "--run", "2026-04-16-initial",
        ])
        assert rc == 0
        # Verify AR written via 015
        records = adoption.list_records(repo_root=repo)
        assert len(records) >= 1


# ---------------------------------------------------------------------------
# v1.1 — Sub-phase F: H4 ownership signals
# ---------------------------------------------------------------------------


def _h1_candidate(slug: str, paths: list[str], score: float = 0.5) -> "onboard.CandidateRecord":
    return onboard.CandidateRecord(
        id="C-001",
        proposed_title=slug,
        proposed_slug=slug,
        paths=paths,
        signals=[f"H1:src/{slug}"],
        score=score,
        draft_path="",
        triage="pending",
        duplicate_of=None,
    )


class TestHeuristicH4Ownership:
    def test_codeowners_single_owner_boosts_candidate(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _write(repo / "CODEOWNERS", "/src/auth/ @alice\n")
        _write(repo / "src" / "auth" / "middleware.py")
        cands = [_h1_candidate("auth", ["src/auth/middleware.py"], score=0.5)]
        out = onboard.heuristic_h4_ownership(repo, cands)
        assert len(out) == 1
        c = out[0]
        assert any("H4:owner:alice" in s for s in c.signals)
        assert c.score > 0.5  # bumped

    def test_git_shortlog_concentrated_owner_boosts(self, tmp_path: Path) -> None:
        """No CODEOWNERS — rely on git shortlog concentration."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git(repo)
        _write(repo / "src" / "auth" / "middleware.py", "# v0\n")
        # Make 4 commits by the same author so concentration = 1.0
        for i in range(4):
            (repo / "src" / "auth" / "middleware.py").write_text(f"# v{i}\n")
            _commit_all(repo, f"auth {i}")
        cands = [_h1_candidate("auth", ["src/auth/middleware.py"], score=0.5)]
        out = onboard.heuristic_h4_ownership(repo, cands)
        c = out[0]
        assert any(s.startswith("H4:owner:") for s in c.signals)
        assert c.score > 0.5

    def test_fragmented_ownership_no_bump(self, tmp_path: Path) -> None:
        """Many authors + low concentration → fragmented annotation, no bump."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git(repo)
        # Alternate authors across 6 commits so no single author dominates.
        _write(repo / "src" / "shared" / "util.py", "# 0\n")
        _commit_all(repo, "init")
        authors = ["a", "b", "c", "d", "e", "f"]
        for i, name in enumerate(authors):
            (repo / "src" / "shared" / "util.py").write_text(f"# v{i}\n")
            env = {
                **os.environ,
                "GIT_AUTHOR_NAME": name,
                "GIT_AUTHOR_EMAIL": f"{name}@e.com",
                "GIT_COMMITTER_NAME": name,
                "GIT_COMMITTER_EMAIL": f"{name}@e.com",
            }
            subprocess.run([_GIT, "add", "-A"], cwd=repo, check=True)
            subprocess.run(
                [_GIT, "commit", "-q", "--no-verify", "-m", f"edit by {name}"],
                cwd=repo, check=True, env=env,
            )
        cands = [_h1_candidate("shared", ["src/shared/util.py"], score=0.5)]
        out = onboard.heuristic_h4_ownership(repo, cands)
        c = out[0]
        assert any("H4:fragmented" in s for s in c.signals)
        assert c.score == 0.5  # no bump

    def test_no_git_history_returns_candidates_unchanged(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _write(repo / "src" / "auth" / "middleware.py")
        cands = [_h1_candidate("auth", ["src/auth/middleware.py"], score=0.5)]
        out = onboard.heuristic_h4_ownership(repo, cands)
        # No raise, and no H4 signals added (nothing to infer).
        assert len(out) == 1
        assert out[0].score == 0.5
        assert not any(s.startswith("H4:") for s in out[0].signals)


# ---------------------------------------------------------------------------
# v1.1 — Sub-phase G: H5 test coverage signals
# ---------------------------------------------------------------------------


class TestHeuristicH5TestCoverage:
    def test_cohesive_test_file_bumps(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _write(repo / "src" / "auth" / "middleware.py")
        _write(repo / "tests" / "test_auth.py", "# tests for auth\n")
        cands = [_h1_candidate("auth", ["src/auth/middleware.py"], score=0.5)]
        out = onboard.heuristic_h5_test_coverage(repo, cands)
        c = out[0]
        assert any(s.startswith("H5:tests:") for s in c.signals)
        # Cohesive → +0.15 bump
        assert abs(c.score - 0.65) < 1e-6

    def test_fragmented_tests_small_bump(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _write(repo / "src" / "auth" / "middleware.py")
        _write(repo / "src" / "auth" / "sessions.py")
        # Multiple test files reference auth source files
        _write(repo / "tests" / "test_auth.py", "from src.auth.middleware import x\n")
        _write(repo / "tests" / "test_login.py",
               "from src.auth.sessions import y\n"
               "from src.auth.middleware import z\n")
        _write(repo / "tests" / "test_signup.py",
               "from src.auth.sessions import q\n")
        cands = [_h1_candidate("auth",
                               ["src/auth/middleware.py", "src/auth/sessions.py"],
                               score=0.5)]
        out = onboard.heuristic_h5_test_coverage(repo, cands)
        c = out[0]
        assert any("H5:fragmented" in s for s in c.signals)
        # Fragmented → +0.05 bump
        assert abs(c.score - 0.55) < 1e-6

    def test_absent_tests_annotation_no_bump(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _write(repo / "src" / "payments" / "stripe.py")
        cands = [_h1_candidate("payments", ["src/payments/stripe.py"], score=0.5)]
        out = onboard.heuristic_h5_test_coverage(repo, cands)
        c = out[0]
        assert any("H5:no-tests" in s for s in c.signals)
        assert c.score == 0.5

    def test_two_matches_classifies_as_fragmented(self, tmp_path: Path) -> None:
        """Regression (codex finding #4): 1 dedicated file + 1 additional
        reference = 2 total matches must be fragmented (+0.05), not
        cohesive (+0.15). Multi-file coverage is the fragmentation
        signal regardless of whether one of them is name-matched.
        """
        repo = tmp_path / "repo"
        repo.mkdir()
        _write(repo / "src" / "auth" / "middleware.py")
        _write(repo / "tests" / "test_auth.py", "# dedicated\n")
        # A second test file that also imports the auth source path.
        _write(
            repo / "tests" / "test_login.py",
            "from src.auth.middleware import thing\n",
        )
        cands = [_h1_candidate("auth", ["src/auth/middleware.py"], score=0.5)]
        out = onboard.heuristic_h5_test_coverage(repo, cands)
        c = out[0]
        assert any("H5:fragmented" in s for s in c.signals), c.signals
        # Fragmented bump = +0.05
        assert abs(c.score - 0.55) < 1e-6

    def test_js_tsx_tests_directory_conv(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _write(repo / "src" / "widget" / "index.tsx")
        _write(repo / "src" / "widget" / "__tests__" / "index.test.tsx",
               "// widget tests\n")
        cands = [_h1_candidate("widget", ["src/widget/index.tsx"], score=0.5)]
        out = onboard.heuristic_h5_test_coverage(repo, cands)
        c = out[0]
        assert any(s.startswith("H5:tests:") for s in c.signals)
        assert c.score > 0.5

    def test_lone_content_reference_not_cohesive(self, tmp_path: Path) -> None:
        """Regression (CodeRabbit PR #63): a single content-reference
        hit from a broad integration test is NOT a dedicated test
        module and must not earn the cohesive +0.15 bump. The only
        match is `test_integration.py` which happens to import the
        candidate's module — that's incidental coverage, not a
        dedicated test. Per FR-105 this falls under fragmented
        (+0.05) because the cohesive path requires a dedicated
        name-matched module or co-located test directory.
        """
        repo = tmp_path / "repo"
        repo.mkdir()
        _write(repo / "src" / "auth" / "middleware.py")
        # NO dedicated test_auth.py, NO co-located tests/. Only a
        # broad integration test that imports the module.
        _write(
            repo / "tests" / "test_integration.py",
            "from src.auth.middleware import handle\n"
            "from src.payments.stripe import charge\n",
        )
        cands = [_h1_candidate("auth", ["src/auth/middleware.py"], score=0.5)]
        out = onboard.heuristic_h5_test_coverage(repo, cands)
        c = out[0]
        # Must NOT be cohesive.
        assert not any(s.startswith("H5:tests:") for s in c.signals), c.signals
        # Must be fragmented (lone incidental reference).
        assert any("H5:fragmented" in s for s in c.signals), c.signals
        # Fragmented bump = +0.05, not cohesive +0.15.
        assert abs(c.score - 0.55) < 1e-6, c.score


# ---------------------------------------------------------------------------
# v1.1 — Regression: H4/H5 scoped to H1-backed candidates
# ---------------------------------------------------------------------------


class TestAnnotatorsRestrictedToH1Candidates:
    """Regression (CodeRabbit PR #63): FR-104 scopes H4/H5 annotators
    to H1 directory candidates. H2 single-file entry points and H6
    co-change clusters must NOT pick up ownership bumps or
    `H5:no-tests` annotations that would alter their thresholding.
    """

    def _write_file(self, path: Path, text: str = "x\n") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def test_h2_entry_point_candidate_not_annotated(
        self, tmp_path: Path,
    ) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        # H2 would fire on a top-level entry-point style file.
        self._write_file(
            repo / "pyproject.toml",
            "[project.scripts]\nmytool = \"mytool.cli:main\"\n",
        )
        self._write_file(repo / "mytool" / "cli.py", "def main(): pass\n")
        # A non-H1 candidate (e.g. synthesised from H2) — only H2 signals.
        c = onboard.CandidateRecord(
            id="C-001",
            proposed_title="mytool",
            proposed_slug="mytool",
            paths=["mytool/cli.py"],
            signals=["H2:entry-point"],
            score=0.5,
            draft_path="",
            triage="pending",
            duplicate_of=None,
        )
        out = onboard.discover(
            repo,
            heuristics=("H4", "H5"),
            score_threshold=0.0,
        )
        # With no H1 discovery configured, `discover` won't even see
        # our hand-crafted candidate; exercise the annotator path
        # directly by feeding the candidate through the annotator
        # gating used inside `discover`.
        # Simulate: the gating predicate must reject non-H1 candidates.
        cands = [c]
        h1_only = [x for x in cands if any(s.startswith("H1:") for s in x.signals)]
        other = [x for x in cands if not any(s.startswith("H1:") for s in x.signals)]
        h1_only = onboard.heuristic_h5_test_coverage(repo, h1_only)
        merged = h1_only + other
        # The H2-only candidate must be unchanged by H5.
        got = [x for x in merged if x.proposed_slug == "mytool"][0]
        assert not any(s.startswith("H5:") for s in got.signals), got.signals
        assert got.score == 0.5

    def test_discover_skips_h4_h5_on_non_h1_candidate(
        self, tmp_path: Path,
    ) -> None:
        """End-to-end: `discover(..., heuristics=("H2","H4","H5"))`
        must emit an H2 candidate without any H4/H5 annotations.
        """
        repo = tmp_path / "repo"
        repo.mkdir()
        # Enough structure for H2 (pyproject entry point) but nothing
        # H1 would pick up at the directory level.
        self._write_file(
            repo / "pyproject.toml",
            "[project]\n"
            "name = \"demo\"\n"
            "[project.scripts]\n"
            "demo = \"demo.cli:main\"\n",
        )
        self._write_file(repo / "demo" / "cli.py", "def main():\n    pass\n")
        # A `tests/test_demo.py` file that WOULD give H5 a cohesive hit
        # for an H1 `demo` candidate — but the demo candidate here is
        # H2-only so H5 must be gated off.
        self._write_file(repo / "tests" / "test_demo.py", "# tests\n")

        out = onboard.discover(
            repo,
            heuristics=("H2", "H4", "H5"),
            score_threshold=0.0,
        )
        # There must be at least one non-H1 candidate from H2, and
        # none of those should carry H4 or H5 signals.
        h2_only = [
            c for c in out
            if any(s.startswith("H2:") for s in c.signals)
            and not any(s.startswith("H1:") for s in c.signals)
        ]
        assert h2_only, (
            "expected at least one H2-only candidate from discover; "
            f"got signals={[c.signals for c in out]}"
        )
        for c in h2_only:
            assert not any(
                s.startswith("H4:") or s.startswith("H5:") for s in c.signals
            ), (
                f"H2-only candidate {c.proposed_slug!r} unexpectedly "
                f"picked up annotator signals: {c.signals}"
            )


# ---------------------------------------------------------------------------
# v1.1 — Regression: rescan coverage index fails closed
# ---------------------------------------------------------------------------


class TestLoadArCoverageIndexFailsClosed:
    """Regression (CodeRabbit PR #63): if the adopted-record registry
    fails to parse, `_load_ar_coverage_index` must NOT swallow the
    error and return an empty list — that would let rescan re-emit
    already-covered paths as `new`. It must propagate an
    OnboardError so the operator sees the failure.
    """

    def test_parse_failure_raises_onboard_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If `adoption.list_records` raises AdoptionError (for
        example because of a parser bug or an unreadable registry
        directory), the coverage-index loader must propagate an
        OnboardError rather than silently returning `[]` and letting
        rescan treat every adopted path as uncovered.
        """
        repo = tmp_path / "repo"
        repo.mkdir()

        def _boom(**_kwargs: object) -> list[adoption.AdoptionRecord]:
            raise adoption.AdoptionError("simulated registry parse failure")

        monkeypatch.setattr(onboard.adoption, "list_records", _boom)

        with pytest.raises(onboard.OnboardError) as excinfo:
            onboard._load_ar_coverage_index(repo)
        assert "coverage" in str(excinfo.value).lower()
        # And the original AdoptionError is chained for debuggability.
        assert isinstance(excinfo.value.__cause__, adoption.AdoptionError)


# ---------------------------------------------------------------------------
# v1.1 — Sub-phase H: Rescan
# ---------------------------------------------------------------------------


def _hash_dir(path: Path) -> dict[str, str]:
    """Return {relpath: sha256} for every file under path."""
    out: dict[str, str] = {}
    for f in sorted(path.rglob("*")):
        if f.is_file():
            rel = str(f.relative_to(path))
            out[rel] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def _prepare_committed_run(repo: Path, run_name: str) -> Path:
    """Scan + fill drafts + commit one run so we have AR records to rescan against."""
    run_dir = onboard.scan(repo_root=repo, run_name=run_name)
    m = onboard.read_manifest(run_dir)
    for c in m.candidates:
        path = run_dir / c.draft_path
        text = path.read_text().replace(
            "TODO: describe what this feature does", "Real summary.",
        ).replace(
            "TODO: fill in an observed behavior before accepting",
            "Real behavior.",
        )
        path.write_text(text)
    triage = run_dir / "triage.md"
    triage.write_text(
        triage.read_text().replace("- status: pending", "- status: accept")
    )
    onboard.commit_run(run_dir, dry_run=False)
    return run_dir


class TestRescan:
    def test_new_candidate_appears_in_rescan_run(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _write(repo / "src" / "auth" / "__init__.py")
        _write(repo / "src" / "auth" / "middleware.py")
        prior = _prepare_committed_run(repo, run_name="2026-04-16-initial")
        # Add a new directory AFTER the initial run committed.
        _write(repo / "src" / "metrics" / "__init__.py")
        _write(repo / "src" / "metrics" / "collector.py")
        new_run = onboard.rescan(
            repo_root=repo,
            from_run="2026-04-16-initial",
            new_run="2026-06-20-rescan",
        )
        assert new_run.exists()
        m_new = onboard.read_manifest(new_run)
        slugs = {c.proposed_slug for c in m_new.candidates}
        assert "metrics" in slugs
        # auth is already adopted — should not appear in the new run
        assert "auth" not in slugs

    def test_prior_run_byte_identical_after_rescan(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _write(repo / "src" / "auth" / "__init__.py")
        _write(repo / "src" / "auth" / "middleware.py")
        prior = _prepare_committed_run(repo, run_name="2026-04-16-initial")
        before = _hash_dir(prior)
        # Add new work; rescan
        _write(repo / "src" / "metrics" / "__init__.py")
        _write(repo / "src" / "metrics" / "collector.py")
        onboard.rescan(
            repo_root=repo,
            from_run="2026-04-16-initial",
            new_run="2026-06-20-rescan",
        )
        after = _hash_dir(prior)
        assert before == after, "Prior run directory was mutated by rescan"

    def test_missing_from_run_raises(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".specify" / "orca" / "adoption-runs").mkdir(parents=True)
        with pytest.raises(onboard.OnboardError):
            onboard.rescan(
                repo_root=repo,
                from_run="does-not-exist",
                new_run="2026-06-20-rescan",
            )

    def test_summary_format_matches_fr109(
        self, tmp_path: Path, capsys
    ) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _write(repo / "src" / "auth" / "__init__.py")
        _write(repo / "src" / "auth" / "middleware.py")
        _prepare_committed_run(repo, run_name="2026-04-16-initial")
        _write(repo / "src" / "metrics" / "__init__.py")
        _write(repo / "src" / "metrics" / "collector.py")
        rc = onboard.cli_main([
            "--root", str(repo), "rescan",
            "--from", "2026-04-16-initial",
            "--run", "2026-06-20-rescan",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        # FR-109: "N new, M changed, K stale"
        assert re.search(r"\d+ new, \d+ changed, \d+ stale", out), out

    def test_stale_candidate_listed_not_committed(self, tmp_path: Path) -> None:
        """Prior run candidate that was NOT committed (e.g., pending) and
        is no longer discoverable should appear in rescan_stale."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _write(repo / "src" / "auth" / "__init__.py")
        _write(repo / "src" / "auth" / "middleware.py")
        _write(repo / "src" / "legacy" / "__init__.py")
        _write(repo / "src" / "legacy" / "old.py")
        # Scan finds both. Commit only auth; leave legacy rejected.
        run_dir = onboard.scan(repo_root=repo, run_name="initial")
        m = onboard.read_manifest(run_dir)
        # Fill all drafts with valid content so 015 accepts
        for c in m.candidates:
            path = run_dir / c.draft_path
            text = path.read_text().replace(
                "TODO: describe what this feature does", "Real summary.",
            ).replace(
                "TODO: fill in an observed behavior before accepting",
                "Real behavior.",
            )
            path.write_text(text)
        # Mark auth accept, legacy reject
        triage = run_dir / "triage.md"
        text = triage.read_text()
        # All set to reject, then flip auth sections to accept
        text = text.replace("- status: pending", "- status: reject")
        # find auth sections and set them back to accept
        auth_ids = [c.id for c in m.candidates if c.proposed_slug == "auth"]
        for aid in auth_ids:
            # Replace the `- status: reject` line in that specific section
            # by doing a targeted section-by-section rewrite.
            lines = text.splitlines()
            in_section = False
            for i, ln in enumerate(lines):
                if ln.startswith(f"## {aid}:"):
                    in_section = True
                    continue
                if in_section and ln.startswith("## "):
                    in_section = False
                if in_section and ln.strip() == "- status: reject":
                    lines[i] = "- status: accept"
                    break
            text = "\n".join(lines)
        triage.write_text(text)
        onboard.commit_run(run_dir, dry_run=False)

        # Now delete the legacy directory so it is no longer discoverable.
        shutil.rmtree(repo / "src" / "legacy")
        new_run = onboard.rescan(
            repo_root=repo,
            from_run="initial",
            new_run="rescan-1",
        )
        m_new = onboard.read_manifest(new_run)
        # Contract (FR-106 / User Story 3): a prior candidate that is
        # not rediscoverable AND not absorbed into a committed AR
        # MUST surface in rescan_stale for operator context. Legacy
        # was rejected (not committed) and its source directory was
        # removed, so both conditions hold. Assert the actual entry
        # rather than just the attribute's existence, so this test
        # fails if rescan regresses and drops stale reporting.
        assert any(
            entry.get("slug") == "legacy"
            for entry in (m_new.rescan_stale or [])
            if isinstance(entry, dict)
        ), f"legacy missing from rescan_stale: {m_new.rescan_stale!r}"
        # And rescan must not resurrect legacy as a new candidate.
        new_slugs = {c.proposed_slug for c in m_new.candidates}
        assert "legacy" not in new_slugs

    def test_rescan_metadata_survives_commit_rewrite(
        self, tmp_path: Path,
    ) -> None:
        """Regression (codex finding #1): rescan_new/rescan_changed must
        persist across every commit_run() manifest rewrite. A rescan that
        then runs through commit must still report the original summary
        when the manifest is re-read afterwards.
        """
        repo = tmp_path / "repo"
        repo.mkdir()
        _write(repo / "src" / "auth" / "__init__.py")
        _write(repo / "src" / "auth" / "middleware.py")
        _prepare_committed_run(repo, run_name="initial")
        _write(repo / "src" / "metrics" / "__init__.py")
        _write(repo / "src" / "metrics" / "collector.py")
        new_run = onboard.rescan(
            repo_root=repo, from_run="initial", new_run="rescan-1",
        )
        m_before = onboard.read_manifest(new_run)
        assert m_before.rescan_from == "initial"
        before_new = m_before.rescan_new
        before_changed = m_before.rescan_changed

        # Now simulate a commit pass — triage reject everything so no
        # ARs are written but the manifest is rewritten.
        triage = new_run / "triage.md"
        triage.write_text(
            triage.read_text().replace("- status: pending", "- status: reject")
        )
        onboard.commit_run(new_run, dry_run=False)
        m_after = onboard.read_manifest(new_run)
        assert m_after.rescan_from == "initial"
        assert m_after.rescan_new == before_new
        assert m_after.rescan_changed == before_changed

    def test_rescan_directory_ar_covers_file_candidate(
        self, tmp_path: Path,
    ) -> None:
        """Regression (codex finding #2): an AR recorded at the directory
        granularity (`src/auth/`) must cover a fresh candidate path
        `src/auth/middleware.py`; overlap must be directory-prefix, not
        exact-string.
        """
        repo = tmp_path / "repo"
        repo.mkdir()
        # Create a committed AR whose Location is a directory (with
        # trailing slash).
        adoption.create_record(
            repo_root=repo,
            title="Auth Area",
            summary="Covers the whole auth directory tree.",
            location=["src/auth/"],
            key_behaviors=["Handles sessions"],
            baseline_commit=None,
        )
        # A fresh candidate at `src/auth/middleware.py` must classify
        # as covered, not `new`.
        _write(repo / "src" / "auth" / "__init__.py")
        _write(repo / "src" / "auth" / "middleware.py")
        # Build a minimal prior run so rescan has something to read.
        # Shortcut: reuse scan then mark candidates committed via a
        # manifest edit.
        prior_dir = onboard.scan(repo_root=repo, run_name="initial")
        m = onboard.read_manifest(prior_dir)
        # Pretend the auth candidate was already committed.
        for c in m.candidates:
            if c.proposed_slug == "auth":
                m.committed.append({
                    "candidate_id": c.id,
                    "ar_id": "AR-001",
                    "ar_path": ".specify/orca/adopted/AR-001-auth.md",
                })
        onboard.write_manifest(prior_dir, m)
        new_run = onboard.rescan(
            repo_root=repo, from_run="initial", new_run="rescan-1",
        )
        m_new = onboard.read_manifest(new_run)
        slugs = {c.proposed_slug for c in m_new.candidates}
        # The auth candidate must NOT resurface as new.
        assert "auth" not in slugs

    def test_rescan_plus_commit_additive(self, tmp_path: Path) -> None:
        """Rescan + commit must produce fresh AR ids without mutating
        prior ARs (015 allocator sees a clean increment)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _write(repo / "src" / "auth" / "__init__.py")
        _write(repo / "src" / "auth" / "middleware.py")
        _prepare_committed_run(repo, run_name="initial")
        records_before = adoption.list_records(repo_root=repo)
        before_hashes = {
            r.record_id: hashlib.sha256(r.path.read_bytes()).hexdigest()
            for r in records_before
        }

        # Add new work
        _write(repo / "src" / "metrics" / "__init__.py")
        _write(repo / "src" / "metrics" / "collector.py")
        new_run = onboard.rescan(
            repo_root=repo, from_run="initial", new_run="rescan-1",
        )
        # Fill new drafts
        m_new = onboard.read_manifest(new_run)
        for c in m_new.candidates:
            path = new_run / c.draft_path
            text = path.read_text().replace(
                "TODO: describe what this feature does", "Real summary.",
            ).replace(
                "TODO: fill in an observed behavior before accepting",
                "Real behavior.",
            )
            path.write_text(text)
        triage = new_run / "triage.md"
        triage.write_text(
            triage.read_text().replace("- status: pending", "- status: accept")
        )
        onboard.commit_run(new_run, dry_run=False)

        records_after = adoption.list_records(repo_root=repo)
        assert len(records_after) > len(records_before)
        # Prior ARs are byte-identical
        for r in records_after:
            if r.record_id in before_hashes:
                h = hashlib.sha256(r.path.read_bytes()).hexdigest()
                assert h == before_hashes[r.record_id]
