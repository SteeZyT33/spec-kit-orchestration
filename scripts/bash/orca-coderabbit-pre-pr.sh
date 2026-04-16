#!/usr/bin/env bash
# Pre-PR CodeRabbit review hook.
# Runs `coderabbit review` against the current branch's diff from main (or
# the branch's first commit on this feature) to produce line-level findings
# before a PR is opened.
#
# This is complementary to /speckit.orca.review-code — review-code owns
# architecture + spec-fidelity review, CodeRabbit owns line-level signal.
#
# Requires: coderabbit CLI authenticated. See `coderabbit auth status`.

set -euo pipefail

if ! command -v coderabbit >/dev/null 2>&1; then
  echo "coderabbit CLI not installed — skipping pre-PR review."
  echo "Install: https://www.coderabbit.ai/cli"
  exit 0
fi

if ! coderabbit auth status 2>&1 | grep -q "Logged in"; then
  echo "coderabbit CLI not authenticated — skipping pre-PR review."
  echo "Run: coderabbit auth login"
  exit 0
fi

BASE_BRANCH="${ORCA_BASE_BRANCH:-main}"
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

if [[ "$CURRENT_BRANCH" == "$BASE_BRANCH" ]]; then
  echo "On base branch ($BASE_BRANCH) — nothing to review."
  exit 0
fi

# Find the merge base so we review only this branch's commits
MERGE_BASE=$(git merge-base "$BASE_BRANCH" HEAD 2>/dev/null || true)

if [[ -z "$MERGE_BASE" ]]; then
  echo "Could not determine merge base with $BASE_BRANCH — falling back to full review."
  coderabbit review --plain
else
  echo "Running CodeRabbit review against base commit $MERGE_BASE..."
  coderabbit review --plain --type committed --base-commit "$MERGE_BASE"
fi
