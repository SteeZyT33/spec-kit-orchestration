#!/usr/bin/env bash
set -euo pipefail

# Resolve PR review threads that have been responded to with the
# Comment Response Protocol (ADDRESSED, REJECTED, ISSUED).
# Leaves CLARIFY threads open — those await answers.
#
# Usage:
#   resolve-pr-threads.sh              # auto-detect PR from current branch
#   resolve-pr-threads.sh --pr 42      # explicit PR number
#   resolve-pr-threads.sh --dry-run    # show what would be resolved, don't act

PR_NUMBER=""
DRY_RUN=false
OWNER=""
REPO=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pr) PR_NUMBER="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    *) echo "Unknown option: $1"; echo "Usage: resolve-pr-threads.sh [--pr NUMBER] [--dry-run]"; exit 1 ;;
  esac
done

# Verify gh is available
if ! command -v gh &>/dev/null; then
  echo "ERROR: gh CLI not found. Install it: https://cli.github.com/"
  exit 1
fi

# Get repo owner/name
REPO_INFO=$(gh repo view --json owner,name -q '.owner.login + "/" + .name' 2>/dev/null) || {
  echo "ERROR: Could not determine repository. Are you in a git repo with a GitHub remote?"
  exit 1
}
OWNER="${REPO_INFO%%/*}"
REPO="${REPO_INFO##*/}"

# Get PR number from current branch if not specified
if [[ -z "$PR_NUMBER" ]]; then
  PR_NUMBER=$(gh pr view --json number -q '.number' 2>/dev/null) || {
    echo "ERROR: No PR found for current branch. Use --pr NUMBER to specify."
    exit 1
  }
fi

echo "Resolving threads for ${OWNER}/${REPO}#${PR_NUMBER}..."

# Query all review threads with their comments
THREADS_JSON=$(gh api graphql -f query='
query($owner: String!, $repo: String!, $pr: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          isOutdated
          comments(last: 1) {
            nodes {
              body
              author {
                login
              }
            }
          }
        }
      }
    }
  }
}' -f owner="$OWNER" -f repo="$REPO" -F pr="$PR_NUMBER" 2>/dev/null) || {
  echo "ERROR: GraphQL query failed. Check your gh auth status."
  exit 1
}

# Parse threads
TOTAL=0
ALREADY_RESOLVED=0
RESOLVED=0
CLARIFY=0
SKIPPED=0
FAILED=0

while IFS= read -r thread; do
  TOTAL=$((TOTAL + 1))

  THREAD_ID=$(echo "$thread" | jq -r '.id')
  IS_RESOLVED=$(echo "$thread" | jq -r '.isResolved')
  LAST_BODY=$(echo "$thread" | jq -r '.comments.nodes[0].body // ""')
  LAST_AUTHOR=$(echo "$thread" | jq -r '.comments.nodes[0].author.login // ""')

  # Skip already resolved
  if [[ "$IS_RESOLVED" == "true" ]]; then
    ALREADY_RESOLVED=$((ALREADY_RESOLVED + 1))
    continue
  fi

  # Check if last reply matches Comment Response Protocol
  # Match ADDRESSED, REJECTED, or ISSUED at the start of the comment body
  if echo "$LAST_BODY" | grep -qiE '^(ADDRESSED|REJECTED|ISSUED)\b'; then
    STATUS=$(echo "$LAST_BODY" | grep -oiE '^(ADDRESSED|REJECTED|ISSUED)' | head -1 | tr '[:lower:]' '[:upper:]')

    if [[ "$DRY_RUN" == "true" ]]; then
      echo "  [DRY-RUN] Would resolve: ${THREAD_ID} (${STATUS} by ${LAST_AUTHOR})"
      RESOLVED=$((RESOLVED + 1))
    else
      # Resolve the thread
      RESULT=$(gh api graphql -f query='
        mutation($threadId: ID!) {
          resolveReviewThread(input: { threadId: $threadId }) {
            thread { id isResolved }
          }
        }' -f threadId="$THREAD_ID" 2>&1) && {
        echo "  Resolved: ${STATUS} by ${LAST_AUTHOR}"
        RESOLVED=$((RESOLVED + 1))
      } || {
        echo "  FAILED to resolve ${THREAD_ID}: ${RESULT}"
        FAILED=$((FAILED + 1))
      }
    fi
  elif echo "$LAST_BODY" | grep -qiE '^CLARIFY\b'; then
    CLARIFY=$((CLARIFY + 1))
  else
    SKIPPED=$((SKIPPED + 1))
  fi
done < <(echo "$THREADS_JSON" | jq -c '.data.repository.pullRequest.reviewThreads.nodes[]')

# Summary
UNRESOLVED=$((TOTAL - ALREADY_RESOLVED))
echo ""
echo "=== Thread Resolution Summary ==="
echo "Total threads: ${TOTAL}"
echo "Already resolved: ${ALREADY_RESOLVED}"
if [[ "$DRY_RUN" == "true" ]]; then
  echo "Would resolve: ${RESOLVED}"
else
  echo "Resolved: ${RESOLVED}"
fi
echo "CLARIFY (left open): ${CLARIFY}"
echo "No status (skipped): ${SKIPPED}"
[[ $FAILED -gt 0 ]] && echo "Failed: ${FAILED}"
echo ""

if [[ $CLARIFY -gt 0 ]]; then
  echo "${CLARIFY} CLARIFY thread(s) remain open — answer them, then re-run."
fi

if [[ $SKIPPED -gt 0 ]]; then
  echo "${SKIPPED} thread(s) have no ADDRESSED/REJECTED/ISSUED/CLARIFY response — respond first."
fi
