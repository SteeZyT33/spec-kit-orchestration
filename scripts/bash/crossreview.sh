#!/usr/bin/env bash
set -euo pipefail

# Cross-harness review launcher.
# Detects tmux and splits pane if available. Otherwise runs in foreground.
# Delegates to crossreview-backend.py for actual CLI invocation.

usage() {
  echo "Usage: crossreview.sh --harness <codex|claude|gemini> --output <path> --prompt-file <path> --patch-file <path> --schema-file <path> [--model <model>] [--effort <effort>]"
  exit 1
}

HARNESS=""
MODEL=""
EFFORT="high"
OUTPUT=""
PROMPT_FILE=""
PATCH_FILE=""
SCHEMA_FILE=""
TIMEOUT="${CROSSREVIEW_TIMEOUT:-300}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --harness) HARNESS="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --effort) EFFORT="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --prompt-file) PROMPT_FILE="$2"; shift 2 ;;
    --patch-file) PATCH_FILE="$2"; shift 2 ;;
    --schema-file) SCHEMA_FILE="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

[[ -z "$HARNESS" || -z "$OUTPUT" || -z "$PROMPT_FILE" || -z "$PATCH_FILE" || -z "$SCHEMA_FILE" ]] && usage

# Skip PATH-only harness check — the backend resolves CLI locations
# (e.g., Claude under ~/.claude/local/). Let the backend own discovery.

# Locate the backend script (relative to this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$SCRIPT_DIR/crossreview-backend.py"

if [[ ! -f "$BACKEND" ]]; then
  echo "ERROR: crossreview-backend.py not found at $BACKEND"
  exit 1
fi

# Build backend command as an array (safe against injection)
BACKEND_CMD=(
  python3 "$BACKEND"
  --harness "$HARNESS"
  --output "$OUTPUT"
  --prompt-file "$PROMPT_FILE"
  --patch-file "$PATCH_FILE"
  --schema-file "$SCHEMA_FILE"
)
[[ -n "$MODEL" ]] && BACKEND_CMD+=(--model "$MODEL")
[[ -n "$EFFORT" ]] && BACKEND_CMD+=(--effort "$EFFORT")

if [[ -n "${TMUX:-}" ]]; then
  echo "Tmux detected — splitting pane for $HARNESS review..."

  # Create a completion marker
  DONE_MARKER="${OUTPUT}.done"
  rm -f "$DONE_MARKER"

  # Serialize the command safely for tmux
  printf -v BACKEND_CMD_ESCAPED '%q ' "${BACKEND_CMD[@]}"
  printf -v DONE_MARKER_ESCAPED '%q' "$DONE_MARKER"

  # Split vertically, run reviewer in new pane
  tmux split-window -h -l 50% \
    "bash -lc '${BACKEND_CMD_ESCAPED}2>&1; touch ${DONE_MARKER_ESCAPED}; echo; echo \"=== CROSS-REVIEW COMPLETE ===\"; sleep 5'"

  # Poll for completion
  ELAPSED=0
  while [[ ! -f "$DONE_MARKER" ]] && [[ $ELAPSED -lt $TIMEOUT ]]; do
    sleep 2
    ELAPSED=$((ELAPSED + 2))
  done
  rm -f "$DONE_MARKER"

  if [[ ! -f "$OUTPUT" ]]; then
    echo "ERROR: Cross-review timed out after ${TIMEOUT}s"
    exit 1
  fi
else
  echo "Running $HARNESS review in foreground..."
  "${BACKEND_CMD[@]}"
fi

echo "$OUTPUT"
