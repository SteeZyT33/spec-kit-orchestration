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

    def test_rescan_returns_deferred_message(self, tmp_path: Path, capsys) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        rc = onboard.cli_main([
            "--root", str(repo), "rescan",
        ])
        assert rc != 0
        captured = capsys.readouterr()
        out = captured.out + captured.err
        # rescan is not implemented in MVP — runtime should say so
        assert "v1.1" in out or "deferred" in out.lower()

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
