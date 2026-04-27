#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CANONICAL_SCRIPT="${SCRIPT_DIR}/orca-main.sh"

if [[ ! -f "$CANONICAL_SCRIPT" ]]; then
  echo "orca canonical launcher missing: $CANONICAL_SCRIPT" >&2
  exit 1
fi

exec bash "$CANONICAL_SCRIPT" "$@"
