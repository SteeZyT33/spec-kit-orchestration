# Orca Release Process — Design

**Date:** 2026-04-30
**Status:** Design (pre-implementation)
**Scope:** Versioning discipline, CHANGELOG generation, tag/release workflow, breaking-change protocol for the orca repo. Single semi-automated bash script with a clear forward path to release-please.
**Out of scope:** PyPI publishing (deferred per prior decision), multi-repo orchestration, full GitHub Actions automation, signed tags, notifications.

## Context

orca currently ships via git tag + GitHub Release, no PyPI. Latest release is v2.0.1 (April 16); PR #70 carries `pyproject.toml version = "2.1.0"` but the v2.1.0 tag has not yet been created. CHANGELOG.md is manually maintained. Conventional commits are enforced via commitlint. There is no release script and no release automation in CI.

This design lands a single script `scripts/release.sh` that captures the full "tag a release" flow with pre-flight safety, conventional-commit-derived CHANGELOG generation, and idempotent retry on failure. The output format matches release-please's defaults so a future swap to that tool is mechanical.

## Goals

1. **One command per release.** `scripts/release.sh v2.2.0` does everything: bump version, generate CHANGELOG, commit, tag, push, create GitHub Release.
2. **Conventional Changelog format** so future migration to release-please is a tooling swap, not a format rewrite.
3. **Pre-flight rejection** of unsafe states (dirty tree, wrong branch, version skip, missing migration doc on major).
4. **Idempotent retry** on partial failure (network drop after tag, before GitHub release).
5. **Zero new dependencies.** Pure bash + `git`, `gh`, `awk`, `sed`, `uv`.

## Non-goals

- Continuous release automation (PR-based release-please flow). The script is the v1; release-please is the post-v1 evolution.
- PyPI / wheel publishing.
- Pre-release tags (`-rc.N`, `-beta.N`). Add only if needed.
- Notifications, webhooks, multi-channel publishing.
- Cross-repo coordination (perf-lab and orca release independently).

## Architecture

**Single script:** `scripts/release.sh` (~120 LOC). One responsibility: take a target version, produce an annotated tag + GitHub Release with auto-generated CHANGELOG entry.

**Tests:** `tests/scripts/test_release.sh` integration runner (~10 cases) using a tmp git repo and faked `gh` (via `PATH` shadowing) to avoid live GitHub calls.

**Inputs:** maintainer runs `scripts/release.sh v2.2.0`. Optional flags: `--allow-empty` (no commits since last tag), `--allow-branch <name>` (skip the main-branch check), `--resume` (continue after partial failure), `--dry-run` (print what would happen, no state changes).

**Outputs:**
1. `pyproject.toml` `version` field updated
2. `uv.lock` refreshed if present
3. `CHANGELOG.md` gets a new block at top
4. Commit `chore(release): v2.2.0`
5. Annotated tag `v2.2.0` (annotation body = CHANGELOG block)
6. Pushed commit + tag
7. Published GitHub Release (body = CHANGELOG block)

**Ordering invariant:** local commit + tag exist before any push. Push commit before push tag. GitHub Release create is the last action. Each step is independently retryable.

## Versioning

**Lineage:** continue v2.x. The rebrand was a name change and a kill list, not a fresh project — capability lineage continues from spec-kit-orca v2.0.1. PR #70 ships v2.1.0; subsequent releases follow strict semver.

**Tag format:** `v<MAJOR>.<MINOR>.<PATCH>`. No pre-release suffixes in v1 of the release process.

**Version source of truth:** `pyproject.toml` `[project] version` field. The script bumps this first; everything else is derived.

**Strict-bump rule:** the script rejects version arguments that aren't a clean increment from the latest `v*` tag:
- `v2.1.0` → `v2.1.1` (patch+1) ✓
- `v2.1.0` → `v2.2.0` (minor+1, patch=0) ✓
- `v2.1.0` → `v3.0.0` (major+1, minor=0, patch=0) ✓
- `v2.1.0` → `v2.3.0` (skip minor) ✗
- `v2.1.0` → `v2.1.0` (already exists) ✗
- `v2.1.0` → `v2.0.0` (downgrade) ✗

Pre-1.0 versions and v0.x tags from the rebrand alpha (`orca-v0.2.0`, `orca-v0.3.0`) are treated as not-in-the-lineage and ignored by the tag scanner.

## CHANGELOG generation

**Format per release block** (matches release-please output verbatim):

```markdown
## v2.2.0 (2026-05-15)

### ⚠ BREAKING CHANGES

- **cli:** rename `--feature` flag to `--feature-id` for consistency

### Features

- **adoption:** flat-namespace slash command conflict detection
- **path-safety:** consolidated validators for Class A/C/D inputs

### Bug Fixes

- **adoption:** track ORCA.md as snapshotted surface

### Documentation

- **contracts:** path-safety status enumerates all migrated flags
```

**Generation algorithm:**

1. Find the previous tag: `git describe --tags --abbrev=0 --match 'v[0-9]*'`. If no prior tag exists, walk all commits.
2. Walk commits in `<prev-tag>..HEAD` via `git log --pretty='%h%x09%s%x09%b%x1e'` (record separator handles multiline bodies).
3. Parse each subject as `<type>(<scope>)?<!>?: <description>`. Skip non-conventional commits with a warning to stderr (do not drop silently).
4. Group by type → heading:
   | Type | Heading |
   |------|---------|
   | `feat` | Features |
   | `fix` | Bug Fixes |
   | `refactor` | Refactors |
   | `docs` | Documentation |
   | `perf` | Performance |
   | `test` | Tests |
   | `build`, `chore`, `ci`, `style` | omitted (noise; release-please omits these too) |
5. Detect BREAKING CHANGES: either `!` in subject (`feat!:`) or `BREAKING CHANGE:` footer line in body. These commits ALSO get listed under `### ⚠ BREAKING CHANGES` with the footer body if present, else the subject description.
6. Sort within each group by commit date ascending.
7. Render. Insert at top of `CHANGELOG.md` immediately after the first H1 (`# Changelog`); preserve everything below.

**Empty-release handling:** if no conventional commits since last tag, refuse with "no release-worthy commits since v2.1.0; use `--allow-empty` to override."

**Optional issue/PR number injection:** if a commit body contains `Refs: #N` or `Closes: #N`, append ` (#N)` to the rendered entry. No GitHub API calls.

## Release flow

`scripts/release.sh v2.2.0` runs in this exact order; any failure exits non-zero with state intact for retry:

1. **Pre-flight:**
   - Working tree clean
   - On `main` branch (override: `--allow-branch <name>`)
   - HEAD matches `origin/main` (no unpushed commits, no behind)
   - Tag does not already exist locally or remotely
   - Strict semver bump from latest `v*` tag
   - On a major bump: `docs/migrations/v<N>.0.0.md` exists (empty file OK)

2. **Update `pyproject.toml`:** awk substitution; re-parse to validate. `uv lock` if `uv.lock` present.

3. **Generate CHANGELOG entry.** If empty and `--allow-empty` not passed → abort.

4. **Commit:** `git add pyproject.toml uv.lock CHANGELOG.md && git commit -m "chore(release): v2.2.0"`

5. **Tag:** annotated, body = CHANGELOG block:
   ```
   git tag -a v2.2.0 -m "Release v2.2.0" -m "$(awk '/^## v2.2.0/,/^## v[0-9]/' CHANGELOG.md | sed '$d')"
   ```

6. **Push commit, then tag:**
   ```
   git push origin main
   git push origin v2.2.0
   ```

7. **Create GitHub Release:** `gh release create v2.2.0 --title "v2.2.0" --notes "<changelog block>"`. On a major release, append `**Migration guide:** [docs/migrations/v3.0.0.md](...)` to notes.

**Idempotent retry (`--resume`):**
- Skips pre-flight checks that would fail because the script has already partially run
- Skips bumping if `pyproject.toml` already matches target version
- Skips CHANGELOG generation if the block is already present
- Skips commit if HEAD message is already `chore(release): vX.Y.Z`
- Skips tag creation if tag exists locally
- Skips push if remote tag exists
- Always retries `gh release create` (its own idempotency: existing release returns exit 1 with a parseable error; script catches and reports URL of existing release)

## Breaking changes + migration

A commit with `feat!:`, `fix!:`, or a `BREAKING CHANGE:` footer triggers the breaking-change path:

1. Auto-detection forces the major-bump check: if maintainer-supplied version isn't a major bump but commits contain breaking changes, refuse with a clear error.
2. CHANGELOG gets a `### ⚠ BREAKING CHANGES` section listing the breaking change descriptions.
3. On a major release, the script verifies `docs/migrations/v<N>.0.0.md` exists. Empty file is acceptable — existence is the contract that says "the maintainer made a deliberate decision."
4. The GitHub Release body gets a footer: `**Migration guide:** [docs/migrations/v<N>.0.0.md](https://github.com/<owner>/<repo>/blob/v<N>.0.0/docs/migrations/v<N>.0.0.md)`.

Migration docs are prose; no template enforcement. They live at `docs/migrations/v3.0.0.md`, `docs/migrations/v4.0.0.md`, etc. Patch and minor releases skip the migration check entirely.

## Testing

**Test runner:** `tests/scripts/test_release.sh`. Plain bash, no bats dependency. Uses a `mktemp -d` tmp directory with a fresh git repo, fakes `gh` and `uv` via PATH shadowing (stub scripts that record their args and exit successfully).

**Cases:**
1. Pre-flight rejects dirty working tree
2. Pre-flight rejects non-main branch (without `--allow-branch`)
3. Pre-flight rejects version skip (`v2.1.0` → `v2.3.0`)
4. Pre-flight rejects existing tag
5. CHANGELOG generation groups commits correctly by conventional type
6. CHANGELOG omits `chore`, `build`, `ci`, `style`
7. BREAKING CHANGE in body → ⚠ section populated; major bump enforced
8. Major bump without `docs/migrations/vN.0.0.md` → refused
9. `--allow-empty` permits release with no conventional commits
10. `--resume` after simulated push failure completes successfully without duplicating commits/tags
11. `--dry-run` produces no state changes

## Implementation phases

Single PR, sequential within:

1. **Script + helpers:** Build `scripts/release.sh` with pre-flight, version bump, CHANGELOG generation as separate functions.
2. **Tests:** Write `tests/scripts/test_release.sh` runner + 11 cases with PATH-shadowed `gh`/`uv` stubs. Tests run via `bash tests/scripts/test_release.sh` from project root.
3. **CI integration:** Add a `release-script-tests` job to `.github/workflows/ci.yml` that runs the bash tests on PRs that touch the script.
4. **Documentation:** Add `docs/release-process.md` describing the maintainer workflow ("when ready to ship: ensure main is green, run `scripts/release.sh vX.Y.Z`, done"). Link from README.

Total: ~120 LOC script + ~150 LOC test runner + ~30 LOC CI yaml + ~50 LOC docs. Half-day of focused work.

## Migration to release-please (future)

When the maintainer wants PR-based automation:

1. Delete `scripts/release.sh` and `tests/scripts/test_release.sh`
2. Add `.github/workflows/release-please.yml`:
   ```yaml
   on:
     push:
       branches: [main]
   jobs:
     release-please:
       runs-on: ubuntu-latest
       steps:
         - uses: googleapis/release-please-action@v4
           with:
             release-type: python
             package-name: orca
   ```
3. First run opens a release PR; merge to ship.

CHANGELOG.md history continues uninterrupted because the script's output format matches release-please's verbatim. Tag scheme (`vX.Y.Z`) is release-please's default. Version source-of-truth (`pyproject.toml`) is release-please's default for `release-type: python`. No format conversion or backfill required.

## Risk

Low. The script is local-execution-only at the maintainer's discretion. Failures leave reproducible state; `--resume` handles partial failure. The CI job is gated to PRs that touch the script, so the test suite doesn't add CI load to unrelated changes.

The one place to be careful: the awk regex in step 5 of the release flow that extracts the CHANGELOG block for tag annotation. If the format ever drifts (e.g., a heading style changes), the awk will pull the wrong content. Tests case 5 covers this directly.
