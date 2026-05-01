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

    # Use NUL byte (%x00) as the record separator. NUL cannot appear in a
    # commit message so multi-line bodies don't fragment the parse the way
    # newline-separated %b would.
    while IFS= read -r -d '' commit_record; do
        # commit_record format: <sha>\t<subject>\n<body>
        local sha subj body
        sha="${commit_record%%$'\t'*}"
        local rest="${commit_record#*$'\t'}"
        subj="${rest%%$'\n'*}"
        if [[ "$rest" == *$'\n'* ]]; then
            body="${rest#*$'\n'}"
        else
            body=""
        fi

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
    done < <(git log --reverse --pretty=$'%h\t%s%n%b%x00' "$range")

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

# ===== Detect breaking changes since last tag =====
has_breaking_changes() {
    local prev_tag
    prev_tag="$(git tag --list 'v[0-9]*' --sort=-v:refname | head -1)"
    local range
    if [ -z "$prev_tag" ]; then range="HEAD"; else range="$prev_tag..HEAD"; fi

    while IFS= read -r -d '' commit_record; do
        local sha subj body
        sha="${commit_record%%$'\t'*}"
        local rest="${commit_record#*$'\t'}"
        subj="${rest%%$'\n'*}"
        if [[ "$rest" == *$'\n'* ]]; then
            body="${rest#*$'\n'}"
        else
            body=""
        fi
        if [[ "$subj" =~ ^[a-z]+(\([a-z0-9-]+\))?!: ]]; then return 0; fi
        if [[ -n "$body" && "$body" == *"BREAKING CHANGE:"* ]]; then return 0; fi
    done < <(git log --pretty=$'%h\t%s%n%b%x00' "$range")
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

# ===== Main =====
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

main
