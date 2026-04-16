#!/usr/bin/env bash
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  echo "orca-matriarch.sh requires 'uv' in PATH" >&2
  exit 1
fi

# Resolve the speckit_orca Python package location. The script may be
# invoked from multiple locations (source repo's scripts/bash/, target
# project's scripts/bash/, or target project's .specify/scripts/bash/).
# Walk up from SCRIPT_DIR to find a project that has either:
#   - `.specify/extensions/orca/pyproject.toml` (installed extension)
#   - `pyproject.toml` with `name = "spec-kit-orca"` (source repo)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
find_orca_project() {
  local dir="$1"
  while [[ "$dir" != "/" ]]; do
    if [[ -f "$dir/.specify/extensions/orca/pyproject.toml" ]]; then
      echo "$dir/.specify/extensions/orca"
      return 0
    fi
    if [[ -f "$dir/pyproject.toml" ]] && grep -q 'name = "spec-kit-orca"' "$dir/pyproject.toml" 2>/dev/null; then
      echo "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}

if ! ORCA_PROJECT="$(find_orca_project "$SCRIPT_DIR")"; then
  echo "orca-matriarch.sh: unable to locate speckit_orca module (searched upward from $SCRIPT_DIR)" >&2
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
  exec uv run --project "$ORCA_PROJECT" python -m speckit_orca.matriarch --repo-root "$repo_root" "${args[@]}"
fi

exec uv run --project "$ORCA_PROJECT" python -m speckit_orca.matriarch --repo-root "$repo_root"
