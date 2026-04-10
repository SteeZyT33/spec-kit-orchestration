#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if ! command -v uv >/dev/null 2>&1; then
  echo "orca-matriarch.sh requires 'uv' in PATH" >&2
  exit 1
fi

repo_root="${PWD}"
args=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-root)
      [[ $# -ge 2 ]] || {
        echo "orca-matriarch.sh: --repo-root requires a value" >&2
        exit 1
      }
      repo_root="$2"
      shift 2
      ;;
    *)
      args+=("$1")
      shift
      ;;
  esac
done

if [[ ${#args[@]} -gt 0 ]]; then
  exec uv run --project "$REPO_ROOT" python -m speckit_orca.matriarch --repo-root "$repo_root" "${args[@]}"
fi

exec uv run --project "$REPO_ROOT" python -m speckit_orca.matriarch --repo-root "$repo_root"
