#!/usr/bin/env bash
# orca-doctor.sh - diagnose an orca install.
#
# Checks (critical = affects exit code):
#   1. orca-cli resolvable          (critical)
#   2. .specify/ exists with init-options.json   (critical)
#   3. 7 SKILL.md files present + valid frontmatter   (critical)
#   4. Reviewer backend availability  (warnings only)
#   5. Bundled extension source loadable   (warning if .specify/extensions/orca/src exists)
#   6. Adoption manifest validation         (info if .orca/adoption.toml exists)
#
# Output format: human-readable, one check per line, prefixed by + / x / !.
# Final line: `orca:doctor: <N>/<total> checks passed`.
# Exit 0 if all critical pass; exit 1 otherwise.

set -u

PASS_MARK="+"
FAIL_MARK="x"
WARN_MARK="!"

passed=0
total=0
critical_failed=0

print_pass() { echo "  ${PASS_MARK} $1"; passed=$((passed+1)); }
print_fail() { echo "  ${FAIL_MARK} $1"; critical_failed=$((critical_failed+1)); }
print_warn() { echo "  ${WARN_MARK} $1"; }

echo "orca:doctor"
echo

# 1. orca-cli resolvable
total=$((total+1))
echo "[1] orca-cli"
if command -v orca-cli >/dev/null 2>&1; then
  print_pass "orca-cli on PATH ($(command -v orca-cli))"
elif [[ -n "${ORCA_PROJECT:-}" ]] && [[ -d "${ORCA_PROJECT}" ]]; then
  print_pass "ORCA_PROJECT=$ORCA_PROJECT (resolvable via uv run)"
elif [[ -d "$HOME/spec-kit-orca" ]]; then
  print_pass "fallback: $HOME/spec-kit-orca (resolvable via uv run)"
else
  print_fail "orca-cli not on PATH; ORCA_PROJECT unset; $HOME/spec-kit-orca missing"
fi
echo

# 2. .specify/ wiring
total=$((total+1))
echo "[2] .specify/ wiring"
if [[ -d ".specify" ]] && [[ -f ".specify/init-options.json" ]]; then
  print_pass ".specify/ present; init-options.json found"
else
  if [[ ! -d ".specify" ]]; then
    print_fail ".specify/ directory not found (cwd: $(pwd))"
  else
    print_fail ".specify/init-options.json missing"
  fi
fi
echo

# 3. 7 SKILL.md files
total=$((total+1))
echo "[3] SKILL.md files"
expected=(brainstorm cite gate review-code review-pr review-spec tui)
skills_dir=""
if [[ -d ".claude/skills" ]]; then
  skills_dir=".claude/skills"
elif [[ -d ".agents/skills" ]]; then
  skills_dir=".agents/skills"
fi

if [[ -z "$skills_dir" ]]; then
  print_fail "no skills dir found (.claude/skills or .agents/skills)"
else
  found=0
  missing=()
  placeholder=()
  for cmd in "${expected[@]}"; do
    f="${skills_dir}/orca-${cmd}/SKILL.md"
    if [[ ! -f "$f" ]]; then
      missing+=("$cmd")
      continue
    fi
    # Verify name: and description: lines, and that description isn't the placeholder.
    if ! grep -q "^name: orca-${cmd}" "$f"; then
      placeholder+=("$cmd (no name:)")
      continue
    fi
    if ! grep -q "^description:" "$f"; then
      placeholder+=("$cmd (no description:)")
      continue
    fi
    if grep -q "Spec-kit workflow command:" "$f"; then
      placeholder+=("$cmd (placeholder description)")
      continue
    fi
    found=$((found+1))
  done
  if [[ "$found" -eq 7 ]]; then
    print_pass "7/7 SKILL.md present and valid (${skills_dir})"
  else
    print_fail "${found}/7 SKILL.md valid (${skills_dir})"
    if [[ "${#missing[@]}" -gt 0 ]]; then
      echo "      missing: ${missing[*]}"
    fi
    if [[ "${#placeholder[@]}" -gt 0 ]]; then
      echo "      invalid: ${placeholder[*]}"
    fi
  fi
fi
echo

# 4. Reviewer backend availability (warnings only, do not affect exit)
echo "[4] reviewer backends (best-effort)"
if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "  ${PASS_MARK} ANTHROPIC_API_KEY set (claude reviewer available)"
else
  print_warn "ANTHROPIC_API_KEY unset (claude reviewer will fail)"
fi
if command -v codex >/dev/null 2>&1; then
  echo "  ${PASS_MARK} codex on PATH ($(command -v codex))"
else
  print_warn "codex not on PATH (codex reviewer unavailable; run 'codex login' after install)"
fi
if [[ -n "${ORCA_REVIEWER_TIMEOUT_S:-}" ]]; then
  echo "  ${PASS_MARK} ORCA_REVIEWER_TIMEOUT_S=${ORCA_REVIEWER_TIMEOUT_S}"
else
  echo "  ${PASS_MARK} ORCA_REVIEWER_TIMEOUT_S unset (codex reviewer uses 120s default)"
fi
echo

# 5. Bundled extension source loadable (only when bundled src is shipped)
if [[ -d ".specify/extensions/orca/src" ]]; then
  total=$((total+1))
  echo "[5] bundled extension source"
  if python3 -c "import sys; sys.path.insert(0, '.specify/extensions/orca/src'); import orca.python_cli; print('OK')" >/dev/null 2>&1; then
    print_pass ".specify/extensions/orca/src loadable (orca.python_cli imports)"
  else
    print_warn ".specify/extensions/orca/src present but orca.python_cli failed to import"
  fi
  echo
fi

# 6. Adoption manifest (Spec 015) - non-critical, only checked when present.
if [[ -f ".orca/adoption.toml" ]]; then
  total=$((total+1))
  echo "[6] adoption manifest"
  if python3 -c "from orca.core.adoption.manifest import load_manifest; from pathlib import Path; load_manifest(Path('.orca/adoption.toml'))" >/dev/null 2>&1; then
    print_pass ".orca/adoption.toml validates"
    # Slash commands consult orca-cli resolve-path (which reads this manifest
    # via host_layout.from_manifest), so the host.feature_dir_pattern is
    # honored end-to-end as of the resolve-path refactor.
    print_pass "host_layout dispatch active (slash commands honor feature_dir_pattern)"
  else
    print_warn ".orca/adoption.toml present but failed schema validation"
  fi
  echo
else
  echo "  ${PASS_MARK} no .orca/adoption.toml (orca not adopted in this repo; run 'orca-cli adopt' to install)"
  echo
fi

# Final summary.
echo
echo "orca:doctor: ${passed}/${total} checks passed"

if [[ "$critical_failed" -gt 0 ]]; then
  exit 1
fi
exit 0
