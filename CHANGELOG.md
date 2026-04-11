## [1.4.1] - 2026-04-11

### Fixed
- `matriarch.py`: crash on `MatriarchError` due to `os.sys.stderr` typo (should have been `sys.stderr`). Would have fired on the first error path raised from the CLI.
- `matriarch.py`: lane_id and spec_id are now validated against the anchored `^[A-Za-z0-9._-]+$` pattern at every path-constructing function (`lane_path`, `mailbox_root`, `reports_path`, `delegated_path`, `delegated_lock_path`, `_feature_dir`) per the lane-mailbox and event-envelope contracts. Previously the contracts enforced the regex on paper but the runtime accepted arbitrary ids, allowing path traversal.
- `matriarch.py`: `_parse_payload` narrowed from `str | dict | list` to `str | dict` so CLI payload parsing matches the event-envelope spec (dict, not list) and no longer triggers a Pyright type error on `send_mailbox_event` / `append_report_event` call sites.
- `brainstorm_memory.py`, `evolve.py`: `sections.setdefault(current_section, ...)` no longer passes a potentially-None key to a `dict[str, ...]` — narrowed via a local variable guard.
- `context_handoffs.py`: `_fallback_artifacts` now declares `candidates` up front and falls through to an empty tuple for unknown source stages, so the downstream loop can never run on an unbound name.
- `pyproject.toml`: moved `templates/capability-packs.example.json` force-include from the pytest `ini_options` section (where it was silently misinterpreted as a config key) into the correct `tool.hatch.build.targets.{sdist,wheel}.force-include` blocks.
- `.github/workflows/ci.yml`: now installs the package and runs `pytest tests/` on every push and PR, instead of only running syntax validation. Previous CI accepted passing runs without ever executing any test.
- `.gitignore`: added `debug-search.log`, `neo4j-apoc-schema.json`, and `repomix-output.xml` so local debris does not risk accidental commits.

### Changed
- Spec `Status:` field flipped from `Draft` to `Implemented` on 001 (worktree runtime), 002 (brainstorm memory), 005 (flow state), 006 (review artifacts), 007 (context handoffs), 008 (capability packs). Those specs had 100% of their tasks completed but the status field was never updated.
- `010-orca-matriarch` status changed to `Implemented (v1; hook-model contract deferred as post-v1 work)` — 41 of 58 tasks are confirmed shipped against `matriarch.py` and `test_matriarch.py`; the Phase 8 hook model is not referenced by any spec FR and is explicitly deferred post-v1; remaining partial items are documented inline with v1.1 refinement notes.
- `specs/010-orca-matriarch/tasks.md`: full reconciliation pass against `matriarch.py` — every DONE task is now `[x]` and every partial/deferred task carries an explicit note explaining what's shipped vs what's follow-up.

## [1.4.0] - 2026-04-11

### Added
- `specs/010-orca-matriarch/contracts/lane-agent.md` — consolidates the Lane Agent normative rules previously scattered across five other 010 contracts. Downstream specs (009 FR-013) can now reference a single source instead of a Key Entity with no contract file.
- `docs/refinement-reviews/` directory with the first entry: `2026-04-11-product-surface.md` (GPT Pro review imported verbatim as both a one-off analysis and the template for a new review class).

### Changed
- `specs/009-orca-yolo/`: tightened with FR-013 through FR-019 aligning to `010-orca-matriarch` supervision. New `Lane Agent Binding` entity, supervision/deployment fields across contracts and data-model, resolved the three open plan questions (pr-ready default, retry bound of 2, minimum run-state shape).
- `specs/010-orca-matriarch/contracts/`: tightened `direct-session-deployment.md` (new), `event-envelope.md` (added `resolved` type, anchored `lane_id` regex, `references` rule for ack/resolved/archived), `lane-mailbox.md` (anchored regex, startup ACK MUST), `tmux-deployment.md` (SHOULD→MUST reporting rules), and portable symlink target resolution in the installer.
- `specs/011-orca-evolve/`: migrated remaining spex harvest into three new Evolve entries (EV-011 drift reconciliation, EV-012 reviewer brief artifact, EV-013 spec-compliance-first code review). Retired `docs/spex-harvest-list.md` and `docs/spex-adoption-notes.md` with pointer stubs. Marked `011` as `Implemented`.
- Installer hardening: `install_self` / `uninstall_self` in `speckit-orca-main.sh` now refuse to clobber unrelated files at `~/.local/bin/speckit-orca`, same-version reinstall is skipped when `$INSTALLED_VER == $VERSION` (unless `--force`), destructive companion refresh is FORCE-gated, and `resolve_symlink_target` uses a portable realpath-then-python3 pattern matching `resolve_self_path`.
- Cross-review backend: review prompts over ~100KB now route to codex via stdin (`codex exec -`); claude/gemini/opencode/cursor-agent retain the documented argv path and raise a clear error when a prompt exceeds the argv safety limit. Configurable `--timeout` flag (default 600s).
- Docs: `README.md` Current Focus and `docs/orca-roadmap.md` Current State / What Is Next updated to reflect that workflow primitives (005-008, 010, 011) have shipped and the remaining runtime gap is 009-orca-yolo.

### Related PRs
- PR #15 (cross-review stdin + Pyright fix)
- PR #16 (009 tightening)
- PR #17 (010 contract tightening + new `direct-session-deployment.md`)
- PR #18 (011 harvest migration + spex doc retirement)
- PR #19 (installer safety + symlink portability)
- PR #20 (011 mark implemented)
- PR #21 (lane-agent contract + README/roadmap post-merge cleanup)
- PR #22 (refinement review doc + template)

## [1.1.0] - 2026-04-05

### Added
- `/speckit.self-review` — process retrospective that evaluates workflow effectiveness across five dimensions (spec fidelity, plan accuracy, task decomposition, review effectiveness, workflow friction), dispatches agents to auto-improve LOW/MEDIUM risk issues in extension commands, and checks community catalog for new relevant extensions
- `bootstrap.sh` — one-command project setup that installs spec-kit + orchestration + companion extensions (superb, verify, reconcile, status)
- Companion extension recommendations in extension.yml (superb, verify, reconcile, status)

### Changed
- Extension version bumped to 1.1.0
- Updated README with full command reference, companion extensions table, and architecture notes

## [1.0.0] - 2026-04-05

### Added
- `/speckit.review` — spec-compliant post-implementation review with tiered fixes and PR lifecycle management
- `/speckit.assign` — agent-to-task assignment with capability matching and confidence scoring
- `/speckit.crossreview` — cross-harness adversarial review using alternate AI models
- Review template for structured phase review reports
- Cross-review JSON schema for structured harness communication
- Merge conflict resolution protocol (4-tier: regenerate, owner-resolve, auto-merge, flag)
- PR comment response protocol (ADDRESSED/REJECTED/ISSUED/CLARIFY)
- Thread resolution script for branch protection compliance
- Configuration template for review and cross-review settings

### Origin
Extracted from SteeZyT33/spec-kit fork (specs 001-005) into standalone extension.
