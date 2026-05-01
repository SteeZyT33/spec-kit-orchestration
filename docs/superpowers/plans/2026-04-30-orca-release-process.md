# Orca Release Process Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `scripts/release.sh` — a single semi-automated release script with conventional-commit-derived CHANGELOG, idempotent retry, and pre-flight safety checks. Output format matches release-please defaults so a future migration is a tooling swap.

**Architecture:** Pure bash; no new deps beyond `git`/`gh`/`awk`/`sed`/`uv` already in dev env. Modular helpers (preflight, version, changelog, tag, push, release) composed by a top-level `main()`. Test runner uses PATH-shadowed `gh`/`uv` stubs to avoid live calls.

**Tech Stack:** bash 4+, git, gh CLI, awk, sed.

**Spec:** `docs/superpowers/specs/2026-04-30-orca-release-process-design.md` (commit `249f6e2`).

**Worktree:** `/home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats`. Branch: `orca-phase-3-plugin-formats`.

**Test runners:**
- Python tests (regression baseline): `uv run python -m pytest`
- Release-script tests: `bash tests/scripts/test_release.sh`

---

## File map

**Create:**
- `scripts/release.sh` — release script (~120 LOC)
- `tests/scripts/test_release.sh` — bash integration runner (~250 LOC including stubs and assertions)
- `tests/scripts/fixtures/gh-stub.sh` — fake `gh` for tests
- `tests/scripts/fixtures/uv-stub.sh` — fake `uv` for tests
- `docs/release-process.md` — maintainer-facing workflow doc (~50 LOC)

**Modify:**
- `.github/workflows/ci.yml` — add `release-script-tests` job (~15 LOC)

---

## Task 1: Skeleton + pre-flight checks

**Files:**
- Create: `scripts/release.sh`
- Create: `tests/scripts/test_release.sh`
- Create: `tests/scripts/fixtures/gh-stub.sh`
- Create: `tests/scripts/fixtures/uv-stub.sh`

- [ ] **Step 1: Write failing tests for pre-flight checks**

Create `tests/scripts/fixtures/gh-stub.sh`:

```bash
#!/usr/bin/env bash
# PATH-shadow stub for `gh`. Records args to $TEST_GH_LOG; succeeds.
echo "gh $*" >> "${TEST_GH_LOG:-/dev/null}"
exit 0
```

Create `tests/scripts/fixtures/uv-stub.sh`:

```bash
#!/usr/bin/env bash
# PATH-shadow stub for `uv`. Records args; succeeds.
echo "uv $*" >> "${TEST_UV_LOG:-/dev/null}"
exit 0
```

Create `tests/scripts/test_release.sh`:

```bash
#!/usr/bin/env bash
# Integration test runner for scripts/release.sh.
# Each test sets up a tmp git repo, PATH-shadows gh/uv stubs,
# runs the script, and asserts on output/exit-code/state.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="$REPO_ROOT/scripts/release.sh"
FIXTURES="$REPO_ROOT/tests/scripts/fixtures"

PASS=0
FAIL=0
FAILED_TESTS=()

_log_pass() { echo "  PASS: $1"; PASS=$((PASS+1)); }
_log_fail() { echo "  FAIL: $1"; echo "        $2"; FAIL=$((FAIL+1)); FAILED_TESTS+=("$1"); }

_setup_tmpdir() {
    local tmp
    tmp="$(mktemp -d)"
    cd "$tmp" || exit 1
    git init -q -b main
    git config user.email "test@example.com"
    git config user.name "Test"
    git config commit.gpgsign false
    mkdir -p stubs
    cp "$FIXTURES/gh-stub.sh" stubs/gh
    cp "$FIXTURES/uv-stub.sh" stubs/uv
    chmod +x stubs/gh stubs/uv
    export PATH="$tmp/stubs:$PATH"
    export TEST_GH_LOG="$tmp/gh.log"
    export TEST_UV_LOG="$tmp/uv.log"
    echo 'name = "orca"' > pyproject.toml
    echo 'version = "2.1.0"' >> pyproject.toml
    echo "# Changelog" > CHANGELOG.md
    git add . && git commit -q -m "chore: initial"
    git tag v2.1.0
    echo "$tmp"
}

_teardown() {
    cd /tmp || exit 1
    rm -rf "$1"
}

# ===== Test 1: dirty tree rejected =====
test_dirty_tree_rejected() {
    local tmp; tmp="$(_setup_tmpdir)"
    echo "uncommitted" > new-file.txt
    if "$SCRIPT" v2.2.0 2>&1 | grep -q "working tree"; then
        _log_pass "dirty_tree_rejected"
    else
        _log_fail "dirty_tree_rejected" "expected error mentioning working tree"
    fi
    _teardown "$tmp"
}

# ===== Test 2: wrong branch rejected =====
test_wrong_branch_rejected() {
    local tmp; tmp="$(_setup_tmpdir)"
    git checkout -q -b feature-x
    if "$SCRIPT" v2.2.0 2>&1 | grep -q "branch"; then
        _log_pass "wrong_branch_rejected"
    else
        _log_fail "wrong_branch_rejected" "expected branch-name error"
    fi
    _teardown "$tmp"
}

# Run all
echo "Running release.sh integration tests..."
echo
test_dirty_tree_rejected
test_wrong_branch_rejected
echo
echo "Results: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
    printf 'Failed: %s\n' "${FAILED_TESTS[@]}"
    exit 1
fi
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
chmod +x tests/scripts/test_release.sh tests/scripts/fixtures/*.sh
bash tests/scripts/test_release.sh
```

Expected: both tests FAIL because `scripts/release.sh` doesn't exist yet.

- [ ] **Step 3: Implement skeleton with pre-flight checks**

Create `scripts/release.sh`:

```bash
#!/usr/bin/env bash
# Orca release script: bump version, generate CHANGELOG, tag, push, release.
# See docs/release-process.md for usage.

set -euo pipefail

VERSION_ARG="${1:-}"
ALLOW_BRANCH=""
ALLOW_EMPTY=0
RESUME=0
DRY_RUN=0

# Parse flags after the version arg
shift || true
while [ $# -gt 0 ]; do
    case "$1" in
        --allow-branch) ALLOW_BRANCH="$2"; shift 2 ;;
        --allow-empty) ALLOW_EMPTY=1; shift ;;
        --resume) RESUME=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        *) echo "unknown flag: $1" >&2; exit 1 ;;
    esac
done

if [ -z "$VERSION_ARG" ]; then
    echo "usage: release.sh vX.Y.Z [--allow-branch <name>] [--allow-empty] [--resume] [--dry-run]" >&2
    exit 1
fi

# Validate version format
if ! [[ "$VERSION_ARG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "error: version must match vMAJOR.MINOR.PATCH (got: $VERSION_ARG)" >&2
    exit 1
fi

NEW_VERSION="${VERSION_ARG#v}"

# ===== Pre-flight checks =====
preflight() {
    # Working tree clean
    if ! git diff --quiet || ! git diff --cached --quiet; then
        echo "error: working tree has uncommitted changes" >&2
        exit 1
    fi

    # Untracked files
    if [ -n "$(git ls-files --others --exclude-standard)" ]; then
        echo "error: working tree has untracked files" >&2
        exit 1
    fi

    # On main branch (or --allow-branch override)
    local current_branch
    current_branch="$(git rev-parse --abbrev-ref HEAD)"
    local expected_branch="${ALLOW_BRANCH:-main}"
    if [ "$current_branch" != "$expected_branch" ]; then
        echo "error: not on branch $expected_branch (current: $current_branch)" >&2
        exit 1
    fi

    # Tag does not exist locally
    if git rev-parse "$VERSION_ARG" >/dev/null 2>&1; then
        if [ "$RESUME" -eq 0 ]; then
            echo "error: tag $VERSION_ARG already exists locally; use --resume to retry" >&2
            exit 1
        fi
    fi
}

# ===== Main =====
main() {
    preflight
    echo "preflight OK; would release $VERSION_ARG"
}

main
```

Make executable:

```bash
chmod +x scripts/release.sh
```

- [ ] **Step 4: Run tests; both should pass**

```bash
bash tests/scripts/test_release.sh
```

Expected: PASS x2.

- [ ] **Step 5: Run python regression suite**

```bash
uv run python -m pytest -x
```

Expected: 624 passed (no regressions; this task only adds new files).

- [ ] **Step 6: Commit**

```bash
git add scripts/release.sh tests/scripts/test_release.sh tests/scripts/fixtures/
git commit -m "feat(release): release.sh skeleton with pre-flight checks"
```

---

## Task 2: Strict version-bump validation

**Files:**
- Modify: `scripts/release.sh` (add bump validator)
- Modify: `tests/scripts/test_release.sh` (add cases)

- [ ] **Step 1: Append failing tests**

Add to `tests/scripts/test_release.sh` before the "Run all" section:

```bash
# ===== Test 3: version skip rejected =====
test_version_skip_rejected() {
    local tmp; tmp="$(_setup_tmpdir)"
    if "$SCRIPT" v2.3.0 2>&1 | grep -q "strict"; then
        _log_pass "version_skip_rejected"
    else
        _log_fail "version_skip_rejected" "expected strict-bump error"
    fi
    _teardown "$tmp"
}

# ===== Test 4: existing tag rejected =====
test_existing_tag_rejected() {
    local tmp; tmp="$(_setup_tmpdir)"
    if "$SCRIPT" v2.1.0 2>&1 | grep -q "already exists"; then
        _log_pass "existing_tag_rejected"
    else
        _log_fail "existing_tag_rejected" "expected tag-already-exists error"
    fi
    _teardown "$tmp"
}

# ===== Test 5: clean patch bump accepted (preflight only) =====
test_patch_bump_passes_preflight() {
    local tmp; tmp="$(_setup_tmpdir)"
    if "$SCRIPT" v2.1.1 2>&1 | grep -q "preflight OK"; then
        _log_pass "patch_bump_passes_preflight"
    else
        _log_fail "patch_bump_passes_preflight" "expected preflight OK"
    fi
    _teardown "$tmp"
}
```

And add to "Run all":

```bash
test_version_skip_rejected
test_existing_tag_rejected
test_patch_bump_passes_preflight
```

- [ ] **Step 2: Run tests to verify failures**

```bash
bash tests/scripts/test_release.sh
```

Expected: 3 new tests fail (only the existing tag check is implemented; the strict-bump rejection isn't there yet, and the preflight-OK message exists but the strict-bump validator doesn't run yet).

- [ ] **Step 3: Add strict-bump validation**

Add this function to `scripts/release.sh` between `preflight()` and `main()`:

```bash
# ===== Strict semver bump check =====
check_strict_bump() {
    # Find latest v* tag (excluding orca-v* alpha tags)
    local latest_tag
    latest_tag="$(git tag --list 'v[0-9]*' --sort=-v:refname | head -1)"
    if [ -z "$latest_tag" ]; then
        # No prior tag; any vX.Y.Z is acceptable
        return 0
    fi

    local prev="${latest_tag#v}"
    local prev_major prev_minor prev_patch
    IFS=. read -r prev_major prev_minor prev_patch <<<"$prev"

    local new_major new_minor new_patch
    IFS=. read -r new_major new_minor new_patch <<<"$NEW_VERSION"

    # Patch bump: same major.minor, patch+1
    if [ "$new_major" = "$prev_major" ] && [ "$new_minor" = "$prev_minor" ] && [ "$new_patch" = "$((prev_patch + 1))" ]; then
        return 0
    fi
    # Minor bump: same major, minor+1, patch=0
    if [ "$new_major" = "$prev_major" ] && [ "$new_minor" = "$((prev_minor + 1))" ] && [ "$new_patch" = "0" ]; then
        return 0
    fi
    # Major bump: major+1, minor=0, patch=0
    if [ "$new_major" = "$((prev_major + 1))" ] && [ "$new_minor" = "0" ] && [ "$new_patch" = "0" ]; then
        return 0
    fi

    echo "error: $VERSION_ARG is not a strict semver bump from $latest_tag" >&2
    exit 1
}
```

Update `main()`:

```bash
main() {
    preflight
    check_strict_bump
    echo "preflight OK; would release $VERSION_ARG"
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
bash tests/scripts/test_release.sh
```

Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/release.sh tests/scripts/test_release.sh
git commit -m "feat(release): strict semver bump validation"
```

---

## Task 3: Version bump + pyproject.toml update

**Files:**
- Modify: `scripts/release.sh`
- Modify: `tests/scripts/test_release.sh`

- [ ] **Step 1: Append test for version bump**

Add to `tests/scripts/test_release.sh`:

```bash
# ===== Test 6: pyproject.toml version updated =====
test_pyproject_version_bumped() {
    local tmp; tmp="$(_setup_tmpdir)"
    "$SCRIPT" v2.1.1 --dry-run 2>&1 >/dev/null || true
    # dry-run shouldn't change file
    if ! grep -q '^version = "2.1.0"$' pyproject.toml; then
        _log_fail "pyproject_version_bumped" "dry-run modified pyproject.toml"
        _teardown "$tmp"
        return
    fi
    # actual run should bump
    "$SCRIPT" v2.1.1 2>&1 >/dev/null || true
    if grep -q '^version = "2.1.1"$' pyproject.toml; then
        _log_pass "pyproject_version_bumped"
    else
        _log_fail "pyproject_version_bumped" "version not updated in pyproject.toml"
    fi
    _teardown "$tmp"
}
```

And add `test_pyproject_version_bumped` to "Run all".

- [ ] **Step 2: Run tests to verify failure**

```bash
bash tests/scripts/test_release.sh
```

Expected: 5 PASS, 1 FAIL.

- [ ] **Step 3: Add bump function**

Add to `scripts/release.sh`:

```bash
# ===== Update pyproject.toml version =====
bump_version() {
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "[dry-run] would bump pyproject.toml version to $NEW_VERSION"
        return 0
    fi

    local tmp_file
    tmp_file="$(mktemp)"
    awk -v new="$NEW_VERSION" '
        /^version = / && !done { print "version = \"" new "\""; done=1; next }
        { print }
    ' pyproject.toml > "$tmp_file"
    mv "$tmp_file" pyproject.toml

    # Validate the substitution worked
    if ! grep -q "^version = \"$NEW_VERSION\"$" pyproject.toml; then
        echo "error: pyproject.toml version substitution failed" >&2
        exit 1
    fi

    # Refresh uv.lock if present
    if [ -f uv.lock ]; then
        uv lock >/dev/null 2>&1 || true
    fi
}
```

Update `main()`:

```bash
main() {
    preflight
    check_strict_bump
    bump_version
    echo "preflight OK; would release $VERSION_ARG"
}
```

- [ ] **Step 4: Run tests**

```bash
bash tests/scripts/test_release.sh
```

Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/release.sh tests/scripts/test_release.sh
git commit -m "feat(release): bump pyproject.toml version with dry-run support"
```

---

## Task 4: CHANGELOG generation from conventional commits

**Files:**
- Modify: `scripts/release.sh`
- Modify: `tests/scripts/test_release.sh`

- [ ] **Step 1: Append tests**

Add to `tests/scripts/test_release.sh`:

```bash
# Helper for changelog tests: setup + add commits with conventional types
_setup_with_commits() {
    local tmp; tmp="$(_setup_tmpdir)"
    git commit -q --allow-empty -m "feat(adoption): flat-namespace conflict detection"
    git commit -q --allow-empty -m "fix(reviewers): file-backed reviewer delegates to path_safety"
    git commit -q --allow-empty -m "docs(contracts): path-safety status update"
    git commit -q --allow-empty -m "chore: bump deps"
    echo "$tmp"
}

# ===== Test 7: changelog groups commits by conventional type =====
test_changelog_groups_by_type() {
    local tmp; tmp="$(_setup_with_commits)"
    "$SCRIPT" v2.2.0 2>&1 >/dev/null || true
    local content; content="$(cat CHANGELOG.md)"
    if echo "$content" | grep -q "^## v2.2.0" \
        && echo "$content" | grep -q "^### Features" \
        && echo "$content" | grep -q "flat-namespace conflict detection" \
        && echo "$content" | grep -q "^### Bug Fixes" \
        && echo "$content" | grep -q "file-backed reviewer delegates" \
        && echo "$content" | grep -q "^### Documentation"; then
        _log_pass "changelog_groups_by_type"
    else
        _log_fail "changelog_groups_by_type" "expected grouped sections; got: $content"
    fi
    _teardown "$tmp"
}

# ===== Test 8: changelog omits chore/build/ci/style =====
test_changelog_omits_noise() {
    local tmp; tmp="$(_setup_with_commits)"
    "$SCRIPT" v2.2.0 2>&1 >/dev/null || true
    if grep -q "bump deps" CHANGELOG.md; then
        _log_fail "changelog_omits_noise" "chore commit leaked into CHANGELOG"
    else
        _log_pass "changelog_omits_noise"
    fi
    _teardown "$tmp"
}

# ===== Test 9: empty release rejected =====
test_empty_release_rejected() {
    local tmp; tmp="$(_setup_tmpdir)"
    # No new commits since v2.1.0 tag
    if "$SCRIPT" v2.1.1 2>&1 | grep -q "no release-worthy commits"; then
        _log_pass "empty_release_rejected"
    else
        _log_fail "empty_release_rejected" "expected empty-release rejection"
    fi
    _teardown "$tmp"
}

# ===== Test 10: --allow-empty permits empty release =====
test_allow_empty_overrides() {
    local tmp; tmp="$(_setup_tmpdir)"
    if "$SCRIPT" v2.1.1 --allow-empty 2>&1 | grep -q "preflight OK"; then
        _log_pass "allow_empty_overrides"
    else
        _log_fail "allow_empty_overrides" "expected --allow-empty to bypass empty check"
    fi
    _teardown "$tmp"
}
```

Add `test_changelog_groups_by_type test_changelog_omits_noise test_empty_release_rejected test_allow_empty_overrides` to "Run all".

- [ ] **Step 2: Run tests to verify failures**

```bash
bash tests/scripts/test_release.sh
```

Expected: 6 PASS, 4 FAIL.

- [ ] **Step 3: Implement changelog generation**

Add to `scripts/release.sh`:

```bash
# ===== Map conventional type to heading =====
_type_to_heading() {
    case "$1" in
        feat) echo "Features" ;;
        fix) echo "Bug Fixes" ;;
        refactor) echo "Refactors" ;;
        docs) echo "Documentation" ;;
        perf) echo "Performance" ;;
        test) echo "Tests" ;;
        *) echo "" ;;  # noise types omitted
    esac
}

# ===== Generate CHANGELOG block since previous tag =====
generate_changelog_block() {
    local prev_tag
    prev_tag="$(git tag --list 'v[0-9]*' --sort=-v:refname | head -1)"
    local range
    if [ -z "$prev_tag" ]; then
        range="HEAD"
    else
        range="$prev_tag..HEAD"
    fi

    local today
    today="$(date -u +%Y-%m-%d)"
    local block_file
    block_file="$(mktemp)"

    echo "## $VERSION_ARG ($today)" >> "$block_file"
    echo >> "$block_file"

    # Buckets per heading
    declare -A buckets
    local has_breaking=0
    local breaking_lines=""

    while IFS=$'\t' read -r sha subj body; do
        # Skip merge commits
        if [[ "$subj" =~ ^Merge ]]; then continue; fi

        # Detect breaking change
        local is_breaking=0
        if [[ "$subj" =~ ^[a-z]+(\([a-z0-9-]+\))?!: ]]; then
            is_breaking=1
        fi
        if [[ -n "$body" && "$body" == *"BREAKING CHANGE:"* ]]; then
            is_breaking=1
        fi

        # Parse type/scope/description
        local type scope desc
        if [[ "$subj" =~ ^([a-z]+)(\(([a-z0-9/_-]+)\))?!?:[[:space:]](.+)$ ]]; then
            type="${BASH_REMATCH[1]}"
            scope="${BASH_REMATCH[3]}"
            desc="${BASH_REMATCH[4]}"
        else
            echo "warning: skipping non-conventional commit: $sha $subj" >&2
            continue
        fi

        local heading
        heading="$(_type_to_heading "$type")"
        if [ -z "$heading" ] && [ "$is_breaking" -eq 0 ]; then
            continue  # noise type, skip
        fi

        # Format entry
        local entry
        if [ -n "$scope" ]; then
            entry="- **$scope:** $desc"
        else
            entry="- $desc"
        fi

        # Optional Refs/Closes injection
        local refs
        refs="$(echo "$body" | grep -oE '(Refs|Closes): #[0-9]+' | head -1 | grep -oE '#[0-9]+')"
        if [ -n "$refs" ]; then
            entry="$entry ($refs)"
        fi

        if [ "$is_breaking" -eq 1 ]; then
            has_breaking=1
            breaking_lines="$breaking_lines$entry"$'\n'
        fi

        if [ -n "$heading" ]; then
            buckets[$heading]="${buckets[$heading]:-}$entry"$'\n'
        fi
    done < <(git log --reverse --pretty=$'%h\t%s\t%b' "$range")

    # Emit BREAKING CHANGES first if any
    if [ "$has_breaking" -eq 1 ]; then
        echo "### ⚠ BREAKING CHANGES" >> "$block_file"
        echo >> "$block_file"
        printf '%s' "$breaking_lines" >> "$block_file"
        echo >> "$block_file"
    fi

    # Emit each heading bucket in canonical order
    for h in "Features" "Bug Fixes" "Refactors" "Documentation" "Performance" "Tests"; do
        if [ -n "${buckets[$h]:-}" ]; then
            echo "### $h" >> "$block_file"
            echo >> "$block_file"
            printf '%s' "${buckets[$h]}" >> "$block_file"
            echo >> "$block_file"
        fi
    done

    cat "$block_file"
    rm "$block_file"
}

# ===== Insert generated block at top of CHANGELOG.md =====
insert_changelog() {
    local block
    block="$(generate_changelog_block)"

    # Strip trailing blank lines from block, count non-blank lines
    local non_blank_count
    non_blank_count="$(echo "$block" | grep -cE '^### ' || true)"

    if [ "$non_blank_count" -eq 0 ] && [ "$ALLOW_EMPTY" -eq 0 ]; then
        local prev_tag
        prev_tag="$(git tag --list 'v[0-9]*' --sort=-v:refname | head -1)"
        echo "error: no release-worthy commits since $prev_tag; use --allow-empty to override" >&2
        exit 1
    fi

    if [ "$DRY_RUN" -eq 1 ]; then
        echo "[dry-run] would insert CHANGELOG block:"
        echo "$block"
        return 0
    fi

    # Insert block after the first '# ' header in CHANGELOG.md
    local tmp_file
    tmp_file="$(mktemp)"
    awk -v block="$block" '
        BEGIN { inserted = 0 }
        /^# / && !inserted { print; print ""; print block; inserted = 1; next }
        { print }
    ' CHANGELOG.md > "$tmp_file"
    mv "$tmp_file" CHANGELOG.md
}
```

Update `main()`:

```bash
main() {
    preflight
    check_strict_bump
    bump_version
    insert_changelog
    echo "preflight OK; would release $VERSION_ARG"
}
```

- [ ] **Step 4: Run tests**

```bash
bash tests/scripts/test_release.sh
```

Expected: 10 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/release.sh tests/scripts/test_release.sh
git commit -m "feat(release): generate CHANGELOG from conventional commits"
```

---

## Task 5: Breaking-change detection + migration doc enforcement

**Files:**
- Modify: `scripts/release.sh`
- Modify: `tests/scripts/test_release.sh`

- [ ] **Step 1: Append tests**

Add to `tests/scripts/test_release.sh`:

```bash
# ===== Test 11: breaking change forces major bump =====
test_breaking_change_forces_major() {
    local tmp; tmp="$(_setup_tmpdir)"
    git commit -q --allow-empty -m "feat!(cli): rename --feature to --feature-id"
    if "$SCRIPT" v2.2.0 2>&1 | grep -q "breaking changes require a major bump"; then
        _log_pass "breaking_change_forces_major"
    else
        _log_fail "breaking_change_forces_major" "expected breaking-change forced-major-bump error"
    fi
    _teardown "$tmp"
}

# ===== Test 12: major bump requires migration doc =====
test_major_requires_migration_doc() {
    local tmp; tmp="$(_setup_tmpdir)"
    git commit -q --allow-empty -m "feat!(cli): rename --feature to --feature-id"
    if "$SCRIPT" v3.0.0 2>&1 | grep -q "docs/migrations/v3.0.0.md"; then
        _log_pass "major_requires_migration_doc"
    else
        _log_fail "major_requires_migration_doc" "expected migration doc requirement error"
    fi
    _teardown "$tmp"
}

# ===== Test 13: major with migration doc proceeds =====
test_major_with_migration_doc_proceeds() {
    local tmp; tmp="$(_setup_tmpdir)"
    git commit -q --allow-empty -m "feat!(cli): rename --feature to --feature-id"
    mkdir -p docs/migrations
    echo "# v3.0.0 Migration" > docs/migrations/v3.0.0.md
    git add docs/migrations/v3.0.0.md
    git commit -q -m "docs: v3.0.0 migration guide"
    if "$SCRIPT" v3.0.0 --dry-run 2>&1 | grep -q "preflight OK"; then
        _log_pass "major_with_migration_doc_proceeds"
    else
        _log_fail "major_with_migration_doc_proceeds" "expected preflight OK"
    fi
    _teardown "$tmp"
}
```

Add the three test names to "Run all".

- [ ] **Step 2: Run tests to verify failures**

```bash
bash tests/scripts/test_release.sh
```

Expected: 10 PASS, 3 FAIL.

- [ ] **Step 3: Implement breaking-change detection**

Add to `scripts/release.sh`:

```bash
# ===== Detect breaking changes since last tag =====
has_breaking_changes() {
    local prev_tag
    prev_tag="$(git tag --list 'v[0-9]*' --sort=-v:refname | head -1)"
    local range
    if [ -z "$prev_tag" ]; then range="HEAD"; else range="$prev_tag..HEAD"; fi

    while IFS=$'\t' read -r sha subj body; do
        if [[ "$subj" =~ ^[a-z]+(\([a-z0-9-]+\))?!: ]]; then return 0; fi
        if [[ -n "$body" && "$body" == *"BREAKING CHANGE:"* ]]; then return 0; fi
    done < <(git log --pretty=$'%h\t%s\t%b' "$range")
    return 1
}

# ===== Check breaking-change vs version-bump and migration doc =====
check_breaking_changes() {
    if ! has_breaking_changes; then
        return 0
    fi

    # Compare against latest tag
    local latest_tag
    latest_tag="$(git tag --list 'v[0-9]*' --sort=-v:refname | head -1)"
    local prev_major; IFS=. read -r prev_major _ _ <<<"${latest_tag#v}"
    local new_major; IFS=. read -r new_major _ _ <<<"$NEW_VERSION"

    if [ "$new_major" = "$prev_major" ]; then
        echo "error: breaking changes require a major bump (latest tag: $latest_tag, requested: $VERSION_ARG)" >&2
        exit 1
    fi

    # Major bump: require migration doc
    local doc_path="docs/migrations/$VERSION_ARG.md"
    if [ ! -f "$doc_path" ]; then
        echo "error: major release requires $doc_path (empty file is OK; existence is the contract)" >&2
        exit 1
    fi
}
```

Update `main()`:

```bash
main() {
    preflight
    check_strict_bump
    check_breaking_changes
    bump_version
    insert_changelog
    echo "preflight OK; would release $VERSION_ARG"
}
```

- [ ] **Step 4: Run tests**

```bash
bash tests/scripts/test_release.sh
```

Expected: 13 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/release.sh tests/scripts/test_release.sh
git commit -m "feat(release): breaking-change detection forces major bump + migration doc"
```

---

## Task 6: Commit, tag, push, GitHub Release

**Files:**
- Modify: `scripts/release.sh`
- Modify: `tests/scripts/test_release.sh`

- [ ] **Step 1: Append tests**

Add to `tests/scripts/test_release.sh`:

```bash
# ===== Test 14: end-to-end happy path creates commit + tag =====
test_e2e_happy_path() {
    local tmp; tmp="$(_setup_with_commits)"
    # Stub origin so push doesn't fail (push to a bare repo)
    git init -q --bare "$tmp/origin.git"
    git remote add origin "$tmp/origin.git"
    git push -q origin main
    "$SCRIPT" v2.2.0 2>&1 >/dev/null

    # Local commit exists
    if ! git log -1 --pretty=%s | grep -q "chore(release): v2.2.0"; then
        _log_fail "e2e_happy_path" "release commit not found"
        _teardown "$tmp"; return
    fi

    # Tag exists
    if ! git rev-parse v2.2.0 >/dev/null 2>&1; then
        _log_fail "e2e_happy_path" "tag v2.2.0 not created"
        _teardown "$tmp"; return
    fi

    # Tag is annotated (has a tagger)
    if ! git for-each-ref refs/tags/v2.2.0 --format='%(taggername)' | grep -q "Test"; then
        _log_fail "e2e_happy_path" "tag is not annotated"
        _teardown "$tmp"; return
    fi

    # gh release create called
    if ! grep -q "release create v2.2.0" "$TEST_GH_LOG"; then
        _log_fail "e2e_happy_path" "gh release create not invoked"
        _teardown "$tmp"; return
    fi

    _log_pass "e2e_happy_path"
    _teardown "$tmp"
}

# ===== Test 15: --resume after commit-exists is idempotent =====
test_resume_skips_existing_commit() {
    local tmp; tmp="$(_setup_with_commits)"
    git init -q --bare "$tmp/origin.git"
    git remote add origin "$tmp/origin.git"
    git push -q origin main

    # First run: full release
    "$SCRIPT" v2.2.0 2>&1 >/dev/null
    local commit_count_before; commit_count_before="$(git rev-list --count HEAD)"

    # Second run with --resume should not duplicate commit
    "$SCRIPT" v2.2.0 --resume 2>&1 >/dev/null || true
    local commit_count_after; commit_count_after="$(git rev-list --count HEAD)"

    if [ "$commit_count_before" = "$commit_count_after" ]; then
        _log_pass "resume_skips_existing_commit"
    else
        _log_fail "resume_skips_existing_commit" "resume duplicated the commit (before=$commit_count_before, after=$commit_count_after)"
    fi
    _teardown "$tmp"
}
```

Add `test_e2e_happy_path test_resume_skips_existing_commit` to "Run all".

- [ ] **Step 2: Run tests to verify failures**

```bash
bash tests/scripts/test_release.sh
```

Expected: 13 PASS, 2 FAIL.

- [ ] **Step 3: Implement commit/tag/push/release**

Add to `scripts/release.sh`:

```bash
# ===== Extract the just-inserted CHANGELOG block for the tag annotation =====
_extract_changelog_block() {
    awk -v ver="$VERSION_ARG" '
        $0 ~ "^## " ver { found=1; print; next }
        found && /^## v[0-9]/ { exit }
        found { print }
    ' CHANGELOG.md
}

# ===== Commit the release =====
commit_release() {
    local commit_subject="chore(release): $VERSION_ARG"

    # Idempotency: if HEAD already has this subject, skip
    if [ "$RESUME" -eq 1 ]; then
        if git log -1 --pretty=%s | grep -qF "$commit_subject"; then
            echo "[resume] release commit already present, skipping"
            return 0
        fi
    fi

    if [ "$DRY_RUN" -eq 1 ]; then
        echo "[dry-run] would commit: $commit_subject"
        return 0
    fi

    git add pyproject.toml CHANGELOG.md
    [ -f uv.lock ] && git add uv.lock
    git commit -m "$commit_subject"
}

# ===== Create annotated tag =====
create_tag() {
    if git rev-parse "$VERSION_ARG" >/dev/null 2>&1; then
        if [ "$RESUME" -eq 1 ]; then
            echo "[resume] tag $VERSION_ARG already present, skipping"
            return 0
        fi
        # Pre-flight should have caught this; defense in depth
        echo "error: tag $VERSION_ARG already exists" >&2
        exit 1
    fi

    if [ "$DRY_RUN" -eq 1 ]; then
        echo "[dry-run] would tag $VERSION_ARG"
        return 0
    fi

    local block
    block="$(_extract_changelog_block)"
    git tag -a "$VERSION_ARG" -m "Release $VERSION_ARG" -m "$block"
}

# ===== Push commit + tag =====
push_release() {
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "[dry-run] would push commit + tag"
        return 0
    fi

    # Skip if no remote configured (test environments)
    if ! git remote get-url origin >/dev/null 2>&1; then
        echo "warning: no 'origin' remote configured; skipping push" >&2
        return 0
    fi

    git push origin "$(git rev-parse --abbrev-ref HEAD)" || {
        echo "error: failed to push branch" >&2
        exit 1
    }
    git push origin "$VERSION_ARG" || {
        echo "error: failed to push tag" >&2
        exit 1
    }
}

# ===== Create GitHub Release =====
create_github_release() {
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "[dry-run] would create GitHub Release for $VERSION_ARG"
        return 0
    fi

    local block
    block="$(_extract_changelog_block)"

    # Append migration link on major bump
    local new_major; IFS=. read -r new_major _ _ <<<"$NEW_VERSION"
    if [ "${new_major}" -gt 0 ] 2>/dev/null && [ -f "docs/migrations/$VERSION_ARG.md" ]; then
        block="$block

**Migration guide:** [docs/migrations/$VERSION_ARG.md](docs/migrations/$VERSION_ARG.md)"
    fi

    if ! command -v gh >/dev/null 2>&1; then
        echo "warning: gh not available; skipping GitHub Release creation" >&2
        return 0
    fi

    gh release create "$VERSION_ARG" --title "$VERSION_ARG" --notes "$block" || {
        echo "warning: gh release create failed (release may already exist)" >&2
    }
}
```

Update `main()`:

```bash
main() {
    preflight
    check_strict_bump
    check_breaking_changes
    bump_version
    insert_changelog
    commit_release
    create_tag
    push_release
    create_github_release
    echo "released $VERSION_ARG"
}
```

- [ ] **Step 4: Run tests**

```bash
bash tests/scripts/test_release.sh
```

Expected: 15 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/release.sh tests/scripts/test_release.sh
git commit -m "feat(release): commit, tag, push, GitHub Release with --resume idempotency"
```

---

## Task 7: Maintainer documentation

**Files:**
- Create: `docs/release-process.md`

- [ ] **Step 1: Write documentation**

Create `docs/release-process.md`:

```markdown
# Release Process

Orca releases ship via git tag + GitHub Release. There is no PyPI distribution.

## When to release

After landing a meaningful set of changes on `main`. There is no fixed cadence; release when there's something worth shipping.

## How to release

From a clean checkout of `main`:

```bash
git pull origin main
scripts/release.sh vX.Y.Z
```

The script will:

1. Verify the working tree is clean and you're on `main`
2. Verify `vX.Y.Z` is a strict semver bump from the latest tag
3. Bump `pyproject.toml` and refresh `uv.lock`
4. Generate a `CHANGELOG.md` entry from conventional commits since the last tag
5. Create the release commit `chore(release): vX.Y.Z`
6. Create an annotated tag with the CHANGELOG block as the body
7. Push the commit and tag to `origin`
8. Create a GitHub Release with the CHANGELOG as the body

## Choosing the version

Strict semver:
- `v2.1.0` → `v2.1.1` for patch (bug fixes only)
- `v2.1.0` → `v2.2.0` for minor (backwards-compatible features)
- `v2.1.0` → `v3.0.0` for major (breaking changes)

The script enforces this. `v2.1.0` → `v2.3.0` (skip) is rejected.

## Breaking changes

If any commit since the last tag uses `feat!:` / `fix!:` syntax or contains a `BREAKING CHANGE:` footer, the script:

1. Refuses any version that isn't a major bump
2. Requires `docs/migrations/vN.0.0.md` to exist (empty file is fine)
3. Appends a `### ⚠ BREAKING CHANGES` section to the CHANGELOG
4. Adds a `**Migration guide:**` link to the GitHub Release body

Write the migration doc as prose. There's no template — describe what consumers need to change. The file's existence is the contract.

## Flags

- `--dry-run` — print what would happen, change nothing
- `--allow-empty` — proceed even if no conventional commits since last tag
- `--allow-branch <name>` — release from a non-`main` branch
- `--resume` — retry after a partial failure (skips already-completed steps)

## Recovery

If the script fails partway:

- **Pre-flight failure:** no state changes; fix the cause and re-run
- **After commit, before push:** `scripts/release.sh vX.Y.Z --resume` retries push + release create
- **After push, before GitHub Release:** `gh release create vX.Y.Z --title "vX.Y.Z" --notes-file <(awk '/^## vX.Y.Z/,/^## v[0-9]/' CHANGELOG.md | sed '$d')`

## Migration to release-please (future)

When PR-based release automation is desired:

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

CHANGELOG history continues uninterrupted because the script's output format matches release-please's verbatim.
```

- [ ] **Step 2: Commit**

```bash
git add docs/release-process.md
git commit -m "docs: maintainer release-process workflow"
```

---

## Task 8: CI integration

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Read existing CI**

Run `cat .github/workflows/ci.yml` to confirm the current jobs structure.

- [ ] **Step 2: Add release-script-tests job**

Append to `.github/workflows/ci.yml` (after the existing `validate` job):

```yaml
  release-script-tests:
    runs-on: ubuntu-latest
    if: |
      contains(github.event.pull_request.changed_files, 'scripts/release.sh') ||
      contains(github.event.pull_request.changed_files, 'tests/scripts/') ||
      github.event_name == 'push'
    steps:
      - name: Check out repository
        uses: actions/checkout@v6
        with:
          fetch-depth: 0  # full history for tag scanning

      - name: Run release-script integration tests
        run: |
          chmod +x scripts/release.sh
          chmod +x tests/scripts/fixtures/*.sh
          bash tests/scripts/test_release.sh
```

(The `if:` filter is a hint; GitHub Actions doesn't support per-file gating on push events, so the job runs on push to main + on PRs that touch the script. This is fine — the test takes <5s.)

- [ ] **Step 3: Verify YAML syntax**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```

Expected: no output (valid YAML).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: run release-script tests on PR + push to main"
```

---

## Task 9: Final regression sweep

- [ ] **Step 1: Run full Python suite**

```bash
uv run python -m pytest
```

Expected: 624 passed (no regressions).

- [ ] **Step 2: Run release-script tests**

```bash
bash tests/scripts/test_release.sh
```

Expected: 15 PASS, 0 FAIL.

- [ ] **Step 3: Smoke-test --dry-run on the actual repo**

```bash
scripts/release.sh v2.1.1 --dry-run
```

Expected: prints what would happen, makes no changes. Verify with `git status` (clean).

(Note: this will *fail* because v2.1.0 doesn't exist as a tag in this repo yet — pyproject says 2.1.0 but no tag was created. That's the expected state of PR #70's branch. Use `--allow-empty` if needed to test the full flow without commits since v2.0.1; or skip the smoke test entirely. The integration tests have already exercised the full flow.)

- [ ] **Step 4: No commit needed for this task**

This task is verification only.

---

## Self-review checklist

After all tasks ship, verify:

1. **Spec coverage:**
   - Pre-flight checks (Tasks 1-2): ✓
   - Strict semver bump validation (Task 2): ✓
   - pyproject.toml version bump + uv.lock refresh (Task 3): ✓
   - Conventional Changelog generation (Task 4): ✓
   - BREAKING CHANGE detection + migration doc (Task 5): ✓
   - Commit/tag/push/release flow (Task 6): ✓
   - --resume idempotency (Task 6): ✓
   - --dry-run / --allow-empty / --allow-branch (Tasks 1, 3, 4): ✓
   - CI integration (Task 8): ✓
   - Maintainer docs (Task 7): ✓
   - Migration to release-please (Task 7 docs): ✓

2. **Function-name consistency:**
   - `preflight()` consistent across Tasks 1, 2, 5, 6
   - `check_strict_bump()` consistent across Tasks 2, 5
   - `bump_version()` consistent across Tasks 3, 6
   - `insert_changelog()` / `generate_changelog_block()` consistent across Tasks 4, 6
   - `check_breaking_changes()` consistent across Tasks 5, 6
   - `commit_release()` / `create_tag()` / `push_release()` / `create_github_release()` consistent in Task 6
   - All called from `main()` in correct order

3. **No placeholders:** all code blocks complete; no TBD/TODO/"similar to" references.
