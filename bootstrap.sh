#!/usr/bin/env bash
set -euo pipefail

# bootstrap.sh — Install spec-kit with the orchestration layer and companion extensions.
#
# Usage:
#   bash bootstrap.sh [project-path] [--ai claude|codex|copilot|...] [--script sh|ps]
#
# What it does:
#   1. Verifies specify CLI is available
#   2. Runs specify init with the chosen AI agent
#   3. Installs the orchestration extension (review, assign, crossreview, self-review)
#   4. Installs companion extensions (superb, verify, reconcile, status)
#   5. Reports what was installed
#
# Environment:
#   SPECKIT_AI       — AI agent override (default: claude)
#   SPECKIT_SCRIPT   — Script type override (default: sh)
#   SKIP_COMPANIONS  — Set to 1 to skip companion extension install

PROJECT_PATH="${1:-.}"
AI_AGENT="${SPECKIT_AI:-claude}"
SCRIPT_TYPE="${SPECKIT_SCRIPT:-sh}"
SKIP_COMPANIONS="${SKIP_COMPANIONS:-0}"

# Parse flags from arguments
shift 2>/dev/null || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --ai) AI_AGENT="$2"; shift 2 ;;
    --script) SCRIPT_TYPE="$2"; shift 2 ;;
    --skip-companions) SKIP_COMPANIONS=1; shift ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# ── Colors ────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
DIM='\033[2m'
NC='\033[0m'

step() { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
fail() { echo -e "${RED}✗${NC} $1" >&2; exit 1; }
info() { echo -e "${DIM}  $1${NC}"; }

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  spec-kit + orchestration bootstrap          ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Step 1: Check specify CLI ─────────────────────────────────────────────────
if ! command -v specify &>/dev/null; then
  fail "specify CLI not found. Install: uv tool install specify-cli --from git+https://github.com/github/spec-kit.git"
fi
SPECKIT_VERSION=$(specify version 2>/dev/null | head -1 || echo "unknown")
step "specify CLI found (${SPECKIT_VERSION})"

# ── Step 2: Initialize project ────────────────────────────────────────────────
if [[ "$PROJECT_PATH" == "." ]]; then
  INIT_ARGS="--here"
  DISPLAY_PATH="$(pwd)"
else
  INIT_ARGS="$PROJECT_PATH"
  DISPLAY_PATH="$PROJECT_PATH"
fi

if [[ -d "${PROJECT_PATH}/.specify" ]]; then
  step "Project already initialized at ${DISPLAY_PATH}"
else
  echo ""
  info "Initializing spec-kit project..."
  specify init ${INIT_ARGS} --ai "$AI_AGENT" --script "$SCRIPT_TYPE" --no-git
  step "Project initialized: ${DISPLAY_PATH} (ai=${AI_AGENT}, script=${SCRIPT_TYPE})"
fi

# Resolve to absolute path for extension installs
PROJECT_PATH="$(cd "$PROJECT_PATH" && pwd)"

# ── Step 3: Install orchestration extension ───────────────────────────────────
echo ""
info "Installing orchestration extension..."

ORCH_URL="https://github.com/SteeZyT33/spec-kit-orchestration/archive/refs/tags/v1.1.0.zip"

# Check if already installed
if [[ -d "${PROJECT_PATH}/.specify/extensions/orchestration" ]]; then
  step "Orchestration extension already installed"
else
  (cd "$PROJECT_PATH" && specify extension add orchestration --from "$ORCH_URL") || {
    warn "Extension install via catalog failed, trying direct URL..."
    (cd "$PROJECT_PATH" && specify extension add --from "$ORCH_URL") || {
      fail "Could not install orchestration extension"
    }
  }
  step "Orchestration extension installed (review, assign, crossreview, self-review)"
fi

# ── Step 4: Install companion extensions ──────────────────────────────────────
if [[ "$SKIP_COMPANIONS" == "1" ]]; then
  warn "Skipping companion extensions (SKIP_COMPANIONS=1)"
else
  echo ""
  info "Installing companion extensions..."

  # Extension catalog IDs — these install from the community catalog
  # Companions: directly complement our orchestration commands
  COMPANIONS=(
    "superb|Superpowers bridge (TDD, verification gates, debug protocol)"
    "verify|Evidence-based completion validation"
    "reconcile|Spec-implementation drift detection"
    "status|Workflow progress dashboard"
  )

  # Adopted: high-value extensions that fill gaps we don't cover
  ADOPTED=(
    "archive|Post-merge feature archival to project memory"
    "doctor|Project health diagnostics"
    "fixit|Spec-aware reactive bug fixing"
    "repoindex|Repo overview and module index for agent orientation"
    "ship|Release pipeline automation (changelog, CI, PR)"
    "speckit-utils|Resume interrupted workflows and traceability checks"
    "verify-tasks|Detect phantom task completions"
  )

  INSTALLED=0
  SKIPPED=0
  FAILED=0

  for entry in "${COMPANIONS[@]}"; do
    EXT_ID="${entry%%|*}"
    EXT_DESC="${entry#*|}"

    if [[ -d "${PROJECT_PATH}/.specify/extensions/${EXT_ID}" ]]; then
      info "  ${EXT_ID} — already installed"
      ((SKIPPED++))
    else
      if (cd "$PROJECT_PATH" && specify extension add "$EXT_ID" 2>/dev/null); then
        step "  ${EXT_ID} — ${EXT_DESC}"
        ((INSTALLED++))
      else
        warn "  ${EXT_ID} — install failed (may not be in cached catalog, install manually)"
        ((FAILED++))
      fi
    fi
  done

  echo ""
  step "Companions: ${INSTALLED} installed, ${SKIPPED} already present, ${FAILED} failed"

  # ── Step 4b: Install adopted extensions ───────────────────────────────────
  echo ""
  info "Installing adopted extensions..."

  ADOPTED_INSTALLED=0
  ADOPTED_SKIPPED=0
  ADOPTED_FAILED=0

  for entry in "${ADOPTED[@]}"; do
    EXT_ID="${entry%%|*}"
    EXT_DESC="${entry#*|}"

    if [[ -d "${PROJECT_PATH}/.specify/extensions/${EXT_ID}" ]]; then
      info "  ${EXT_ID} — already installed"
      ((ADOPTED_SKIPPED++))
    else
      if (cd "$PROJECT_PATH" && specify extension add "$EXT_ID" 2>/dev/null); then
        step "  ${EXT_ID} — ${EXT_DESC}"
        ((ADOPTED_INSTALLED++))
      else
        warn "  ${EXT_ID} — install failed (may not be in cached catalog, install manually)"
        ((ADOPTED_FAILED++))
      fi
    fi
  done

  echo ""
  step "Adopted: ${ADOPTED_INSTALLED} installed, ${ADOPTED_SKIPPED} already present, ${ADOPTED_FAILED} failed"
fi

# ── Step 5: Summary ──────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  Setup complete                              ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  Project:    ${DISPLAY_PATH}"
echo "  AI Agent:   ${AI_AGENT}"
echo "  Script:     ${SCRIPT_TYPE}"
echo ""
echo "  Core commands:"
echo "    /speckit.specify        Create feature spec"
echo "    /speckit.plan           Generate implementation plan"
echo "    /speckit.tasks          Break down into tasks"
echo "    /speckit.implement      Execute tasks"
echo ""
echo "  Orchestration commands:"
echo "    /speckit.assign         Assign agents to tasks"
echo "    /speckit.review         Post-implementation review"
echo "    /speckit.crossreview    Adversarial cross-harness review"
echo "    /speckit.self-review    Process retrospective"
echo ""

if [[ "$SKIP_COMPANIONS" != "1" ]]; then
  echo "  Companion commands:"
  echo "    /speckit.superb.*       TDD, verify, critique, debug, finish"
  echo "    /speckit.verify.run     Evidence-based completion gate"
  echo "    /speckit.reconcile.run  Drift detection and repair"
  echo "    /speckit.status.show    Workflow progress dashboard"
  echo ""
  echo "  Adopted commands:"
  echo "    /speckit.archive.run    Archive merged features to memory"
  echo "    /speckit.doctor.run     Project health diagnostics"
  echo "    /speckit.fixit.run      Spec-aware bug fixing"
  echo "    /speckit.repoindex.*    Repo overview and module index"
  echo "    /speckit.ship.run       Release pipeline automation"
  echo "    /speckit.utils.*        Resume workflows, traceability"
  echo "    /speckit.verify-tasks   Detect phantom completions"
  echo ""
fi

echo "  Recommended workflow:"
echo "    specify → plan → tasks → assign → implement → review → crossreview → self-review"
echo "                                                    ↓ (if shipping)"
echo "    verify-tasks → ship → archive"
echo ""
