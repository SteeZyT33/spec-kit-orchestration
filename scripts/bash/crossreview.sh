#!/usr/bin/env bash
set -euo pipefail

# Cross-review launcher.
# Detects tmux and splits pane if available. Otherwise runs in foreground.
# Delegates to crossreview-backend.py for actual agent selection and invocation.

usage() {
  echo "Usage: crossreview.sh [--agent <name> | --harness <name>] --output <path> --prompt-file <path> --patch-file <path> --schema-file <path> [--model <model>] [--effort <effort>] [--active-agent <name>] [--timeout <seconds>]"
  exit 1
}

AGENT=""
HARNESS=""
ACTIVE_AGENT="${ORCA_ACTIVE_AGENT:-}"
MODEL=""
EFFORT=""
OUTPUT=""
PROMPT_FILE=""
PATCH_FILE=""
SCHEMA_FILE=""
TIMEOUT="${CROSSREVIEW_TIMEOUT:-300}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent) AGENT="$2"; shift 2 ;;
    --harness) HARNESS="$2"; shift 2 ;;
    --active-agent) ACTIVE_AGENT="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --effort) EFFORT="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --prompt-file) PROMPT_FILE="$2"; shift 2 ;;
    --patch-file) PATCH_FILE="$2"; shift 2 ;;
    --schema-file) SCHEMA_FILE="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

if ! [[ "$TIMEOUT" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: --timeout must be a positive integer (seconds)"
  exit 1
fi

[[ -z "$OUTPUT" || -z "$PROMPT_FILE" || -z "$PATCH_FILE" || -z "$SCHEMA_FILE" ]] && usage

# Skip PATH-only agent checks. The backend owns CLI discovery and support policy.

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
  --output "$OUTPUT"
  --prompt-file "$PROMPT_FILE"
  --patch-file "$PATCH_FILE"
  --schema-file "$SCHEMA_FILE"
  --timeout "$TIMEOUT"
)
[[ -n "$AGENT" ]] && BACKEND_CMD+=(--agent "$AGENT")
[[ -n "$HARNESS" ]] && BACKEND_CMD+=(--harness "$HARNESS")
[[ -n "$ACTIVE_AGENT" ]] && BACKEND_CMD+=(--active-agent "$ACTIVE_AGENT")
[[ -n "$MODEL" ]] && BACKEND_CMD+=(--model "$MODEL")
[[ -n "$EFFORT" ]] && BACKEND_CMD+=(--effort "$EFFORT")

if [[ -n "${TMUX:-}" ]]; then
  REVIEWER_LABEL="${AGENT:-${HARNESS:-auto}}"
  echo "Tmux detected - splitting pane for ${REVIEWER_LABEL} review..."

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
  REVIEWER_LABEL="${AGENT:-${HARNESS:-auto}}"
  echo "Running ${REVIEWER_LABEL} review in foreground..."
  "${BACKEND_CMD[@]}"
fi

echo "$OUTPUT"
