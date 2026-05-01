#!/usr/bin/env bash
# Integration test runner for scripts/release.sh.
# Each test sets up a tmp git repo, PATH-shadows gh/uv stubs,
# runs the script, and asserts on output/exit-code/state.

set -u
# pipefail intentionally omitted: the release script exits nonzero on expected
# failures; if pipefail were set, `"$SCRIPT" ... 2>&1 | grep -q "pattern"`
# would return the script's exit code (1) even when grep finds the pattern,
# causing all error-detection tests to fail.

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="$REPO_ROOT/scripts/release.sh"
FIXTURES="$REPO_ROOT/tests/scripts/fixtures"

PASS=0
FAIL=0
FAILED_TESTS=()

_log_pass() { echo "  PASS: $1"; PASS=$((PASS+1)); }
_log_fail() { echo "  FAIL: $1"; echo "        $2"; FAIL=$((FAIL+1)); FAILED_TESTS+=("$1"); }

# Sets global _TMP, _GH_LOG, _UV_LOG and updates PATH + TEST_* exports.
# Call without $() so env changes propagate to the calling shell.
_setup_tmpdir() {
    _TMP="$(mktemp -d)"
    cd "$_TMP" || exit 1
    git init -q -b main
    git config user.email "test@example.com"
    git config user.name "Test"
    git config commit.gpgsign false
    git config core.hooksPath /dev/null
    mkdir -p stubs
    cp "$FIXTURES/gh-stub.sh" stubs/gh
    cp "$FIXTURES/uv-stub.sh" stubs/uv
    chmod +x stubs/gh stubs/uv
    export PATH="$_TMP/stubs:$PATH"
    export TEST_GH_LOG="$_TMP/gh.log"
    export TEST_UV_LOG="$_TMP/uv.log"
    _GH_LOG="$_TMP/gh.log"
    echo 'name = "orca"' > pyproject.toml
    echo 'version = "2.1.0"' >> pyproject.toml
    echo "# Changelog" > CHANGELOG.md
    git add . && git commit -q -m "chore: initial"
    git tag v2.1.0
}

_teardown() {
    cd /tmp || exit 1
    rm -rf "$1"
}

# ===== Test 1: dirty tree rejected =====
test_dirty_tree_rejected() {
    _setup_tmpdir
    local tmp="$_TMP"
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
    _setup_tmpdir
    local tmp="$_TMP"
    git checkout -q -b feature-x
    if "$SCRIPT" v2.2.0 2>&1 | grep -q "branch"; then
        _log_pass "wrong_branch_rejected"
    else
        _log_fail "wrong_branch_rejected" "expected branch-name error"
    fi
    _teardown "$tmp"
}

# ===== Test 3: version skip rejected =====
test_version_skip_rejected() {
    _setup_tmpdir
    local tmp="$_TMP"
    if "$SCRIPT" v2.3.0 2>&1 | grep -q "strict"; then
        _log_pass "version_skip_rejected"
    else
        _log_fail "version_skip_rejected" "expected strict-bump error"
    fi
    _teardown "$tmp"
}

# ===== Test 4: existing tag rejected =====
test_existing_tag_rejected() {
    _setup_tmpdir
    local tmp="$_TMP"
    if "$SCRIPT" v2.1.0 2>&1 | grep -q "already exists"; then
        _log_pass "existing_tag_rejected"
    else
        _log_fail "existing_tag_rejected" "expected tag-already-exists error"
    fi
    _teardown "$tmp"
}

# ===== Test 5: clean patch bump accepted (preflight only) =====
test_patch_bump_passes_preflight() {
    _setup_tmpdir
    local tmp="$_TMP"
    if "$SCRIPT" v2.1.1 --allow-empty 2>&1 | grep -q "released"; then
        _log_pass "patch_bump_passes_preflight"
    else
        _log_fail "patch_bump_passes_preflight" "expected released v2.1.1"
    fi
    _teardown "$tmp"
}

# ===== Test 6: pyproject.toml version updated =====
test_pyproject_version_bumped() {
    _setup_tmpdir
    local tmp="$_TMP"
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

# Helper for changelog tests: setup + add commits with conventional types.
# Call without $() so PATH/TEST_* exports propagate.
_setup_with_commits() {
    _setup_tmpdir
    git commit -q --allow-empty -m "feat(adoption): flat-namespace conflict detection"
    git commit -q --allow-empty -m "fix(reviewers): file-backed reviewer delegates to path_safety"
    git commit -q --allow-empty -m "docs(contracts): path-safety status update"
    git commit -q --allow-empty -m "chore: bump deps"
}

# ===== Test 7: changelog groups commits by conventional type =====
test_changelog_groups_by_type() {
    _setup_with_commits
    local tmp="$_TMP"
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
    _setup_with_commits
    local tmp="$_TMP"
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
    _setup_tmpdir
    local tmp="$_TMP"
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
    _setup_tmpdir
    local tmp="$_TMP"
    if "$SCRIPT" v2.1.1 --allow-empty 2>&1 | grep -q "released"; then
        _log_pass "allow_empty_overrides"
    else
        _log_fail "allow_empty_overrides" "expected --allow-empty to bypass empty check"
    fi
    _teardown "$tmp"
}

# ===== Test 11: breaking change forces major bump =====
test_breaking_change_forces_major() {
    _setup_tmpdir
    local tmp="$_TMP"
    git commit -q --allow-empty -m "feat(cli)!: rename --feature to --feature-id"
    if "$SCRIPT" v2.2.0 2>&1 | grep -q "breaking changes require a major bump"; then
        _log_pass "breaking_change_forces_major"
    else
        _log_fail "breaking_change_forces_major" "expected breaking-change forced-major-bump error"
    fi
    _teardown "$tmp"
}

# ===== Test 12: major bump requires migration doc =====
test_major_requires_migration_doc() {
    _setup_tmpdir
    local tmp="$_TMP"
    git commit -q --allow-empty -m "feat(cli)!: rename --feature to --feature-id"
    if "$SCRIPT" v3.0.0 2>&1 | grep -q "docs/migrations/v3.0.0.md"; then
        _log_pass "major_requires_migration_doc"
    else
        _log_fail "major_requires_migration_doc" "expected migration doc requirement error"
    fi
    _teardown "$tmp"
}

# ===== Test 13: major with migration doc proceeds =====
test_major_with_migration_doc_proceeds() {
    _setup_tmpdir
    local tmp="$_TMP"
    git commit -q --allow-empty -m "feat(cli)!: rename --feature to --feature-id"
    mkdir -p docs/migrations
    echo "# v3.0.0 Migration" > docs/migrations/v3.0.0.md
    git add docs/migrations/v3.0.0.md
    git commit -q -m "docs: v3.0.0 migration guide"
    if "$SCRIPT" v3.0.0 --dry-run 2>&1 | grep -q "released"; then
        _log_pass "major_with_migration_doc_proceeds"
    else
        _log_fail "major_with_migration_doc_proceeds" "expected released v3.0.0"
    fi
    _teardown "$tmp"
}

# ===== Test 14: end-to-end happy path creates commit + tag =====
test_e2e_happy_path() {
    _setup_with_commits
    local tmp="$_TMP"
    local gh_log="$_GH_LOG"
    # Stub origin so push doesn't fail (push to a bare repo outside working tree)
    local bare_tmp; bare_tmp="$(mktemp -d)"
    git init -q --bare "$bare_tmp/origin.git"
    git remote add origin "$bare_tmp/origin.git"
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
    if ! grep -q "release create v2.2.0" "$gh_log"; then
        _log_fail "e2e_happy_path" "gh release create not invoked"
        _teardown "$tmp"; return
    fi

    _log_pass "e2e_happy_path"
    _teardown "$tmp"
}

# ===== Test 15: --resume after commit-exists is idempotent =====
test_resume_skips_existing_commit() {
    _setup_with_commits
    local tmp="$_TMP"
    local bare_tmp; bare_tmp="$(mktemp -d)"
    git init -q --bare "$bare_tmp/origin.git"
    git remote add origin "$bare_tmp/origin.git"
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

# Run all
echo "Running release.sh integration tests..."
echo
test_dirty_tree_rejected
test_wrong_branch_rejected
test_version_skip_rejected
test_existing_tag_rejected
test_patch_bump_passes_preflight
test_pyproject_version_bumped
test_changelog_groups_by_type
test_changelog_omits_noise
test_empty_release_rejected
test_allow_empty_overrides
test_breaking_change_forces_major
test_major_requires_migration_doc
test_major_with_migration_doc_proceeds
test_e2e_happy_path
test_resume_skips_existing_commit
echo
echo "Results: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
    printf 'Failed: %s\n' "${FAILED_TESTS[@]}"
    exit 1
fi
