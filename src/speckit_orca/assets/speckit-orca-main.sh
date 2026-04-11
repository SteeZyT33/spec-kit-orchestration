#!/usr/bin/env bash
set -euo pipefail

# speckit-orca
#
# Install spec-kit + orchestration layer for one or more AI agents.
#
#   speckit-orca                    # Default: claude
#   speckit-orca codex              # Set up current repo for a different agent
#   speckit-orca --minimal claude   # No companion extensions
#   speckit-orca --status           # Show current repo status
#   speckit-orca --doctor           # Diagnose common install/config issues
#   speckit-orca --list             # Show available agents

VERSION="1.4.1"
ORCH_URL="https://github.com/SteeZyT33/spec-kit-orca/archive/refs/tags/v${VERSION}.zip"
LOCAL_BIN="${HOME}/.local/bin"
LOCAL_LINK="${LOCAL_BIN}/speckit-orca"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1" >&2; exit 1; }
dim()  { echo -e "  ${DIM}$1${NC}"; }

backup_orca_state() {
  local backup_dir
  backup_dir="$(mktemp -d)"

  if [[ -d ".specify/extensions/orca" ]]; then
    cp -R ".specify/extensions/orca" "$backup_dir/orca"
  fi
  if [[ -f ".specify/extensions/.registry" ]]; then
    cp ".specify/extensions/.registry" "$backup_dir/.registry"
  fi

  echo "$backup_dir"
}

restore_orca_state() {
  local backup_dir="$1"
  mkdir -p ".specify/extensions"
  rm -rf ".specify/extensions/orca"

  if [[ -d "$backup_dir/orca" ]]; then
    cp -R "$backup_dir/orca" ".specify/extensions/orca"
  fi
  if [[ -f "$backup_dir/.registry" ]]; then
    cp "$backup_dir/.registry" ".specify/extensions/.registry"
  fi
}

replace_orca_extension() {
  local progress_label="$1"
  local success_message="$2"
  local failure_message="$3"
  local backup_dir=""

  backup_dir="$(backup_orca_state)"
  echo -ne "  ${DIM}  ${progress_label}${NC}"

  if ! specify extension remove orca --keep-config --force 1>/dev/null 2>&1; then
    rm -rf "$backup_dir"
    fail "${failure_message} Removal failed before reinstall."
  fi

  if specify extension add orca --from "$ORCH_URL" 1>/dev/null 2>&1; then
    rm -rf "$backup_dir"
    echo -e "\r  ${GREEN}✓${NC} ${success_message}          "
    return 0
  fi

  restore_orca_state "$backup_dir"
  rm -rf "$backup_dir"
  fail "${failure_message} Previous Orca installation restored."
}

resolve_self_path() {
  local source_path="${BASH_SOURCE[0]}"

  if command -v realpath >/dev/null 2>&1; then
    realpath "$source_path"
    return
  fi

  python3 - "$source_path" <<'PY'
import os
import pathlib
import sys

print(pathlib.Path(os.path.realpath(sys.argv[1])).resolve())
PY
}

ensure_community_catalog() {
  local catalog_file=".specify/extension-catalogs.yml"

  if python3 - "$catalog_file" <<'PY'
import pathlib
import sys

catalog_path = pathlib.Path(sys.argv[1])
community_url = "https://raw.githubusercontent.com/github/spec-kit/main/extensions/catalog.community.json"
default_block = (
    "catalogs:\n"
    "  - name: default\n"
    "    url: https://raw.githubusercontent.com/github/spec-kit/main/extensions/catalog.json\n"
    "    priority: 1\n"
    "    install_allowed: true\n"
    "  - name: community\n"
    f"    url: {community_url}\n"
    "    priority: 2\n"
    "    install_allowed: true\n"
)

if not catalog_path.exists():
    catalog_path.write_text(default_block, encoding="utf-8")
    raise SystemExit(10)

lines = catalog_path.read_text(encoding="utf-8").splitlines()
blocks = []
current = []
for line in lines:
    if line.startswith("  - ") and current:
        blocks.append(current)
        current = [line]
    else:
        current.append(line)
if current:
    blocks.append(current)

updated_blocks = []
found = False
changed = False
for block in blocks:
    text = "\n".join(block)
    is_community = "name: community" in text or community_url in text
    if not is_community:
        updated_blocks.append(block)
        continue

    found = True
    new_block = []
    install_written = False
    for line in block:
        stripped = line.strip()
        if stripped.startswith("install_allowed:"):
            install_written = True
            if stripped != "install_allowed: true":
                new_block.append("    install_allowed: true")
                changed = True
            else:
                new_block.append(line)
            continue
        new_block.append(line)
    if not install_written:
        new_block.append("    install_allowed: true")
        changed = True
    updated_blocks.append(new_block)

if not found:
    changed = True
    if updated_blocks and updated_blocks[-1]:
        updated_blocks.append([])
    updated_blocks.append([
        "  - name: community",
        f"    url: {community_url}",
        "    priority: 2",
        "    install_allowed: true",
    ])

rendered = "\n".join("\n".join(block) for block in updated_blocks).strip() + "\n"
if changed:
    catalog_path.write_text(rendered, encoding="utf-8")
    raise SystemExit(11)
PY
  then
    ok "Community catalog enabled"
  else
    case $? in
      10|11) ok "Community catalog enabled" ;;
      *) fail "Failed to validate $catalog_file" ;;
    esac
  fi
}

install_self() {
  local self_path
  self_path="$(resolve_self_path)"
  mkdir -p "$LOCAL_BIN"
  ln -sfn "$self_path" "$LOCAL_LINK"
  ok "Installed launcher: $LOCAL_LINK -> $self_path"
  if command -v speckit-orca >/dev/null 2>&1; then
    ok "Available on PATH as: $(command -v speckit-orca)"
  else
    warn "~/.local/bin is not active in this shell yet"
    echo "  Add to ~/.zshrc or ~/.shell.sh:"
    echo '    export PATH="$HOME/.local/bin:$PATH"'
  fi
}

uninstall_self() {
  if [[ -L "$LOCAL_LINK" || -f "$LOCAL_LINK" ]]; then
    rm -f "$LOCAL_LINK"
    ok "Removed launcher: $LOCAL_LINK"
  else
    warn "No launcher installed at $LOCAL_LINK"
  fi
}

refresh_catalog_extension() {
  local ext="$1"
  local label="${2:-$1}"

  if extension_registered "$ext"; then
    echo -ne "  ${DIM}  Refreshing ${label}...${NC}"
    if specify extension remove "$ext" --keep-config --force 1>/dev/null 2>&1 && \
       specify extension add "$ext" 1>/dev/null 2>&1; then
      echo -e "\r  ${GREEN}✓${NC} ${label}                    "
      return 0
    fi
    echo -e "\r  ${YELLOW}!${NC} ${label} — refresh failed   "
    return 1
  fi

  echo -ne "  ${DIM}  Adding ${label}...${NC}"
  if specify extension add "$ext" 1>/dev/null 2>&1; then
    echo -e "\r  ${GREEN}✓${NC} ${label}                    "
    return 0
  fi
  echo -e "\r  ${YELLOW}!${NC} ${label} — unavailable      "
  return 1
}

extension_registered() {
  local ext="$1"
  local registry=".specify/extensions/.registry"
  [[ -f "$registry" ]] || return 1

  python3 - "$registry" "$ext" <<'PY' >/dev/null 2>&1
import json
import sys

registry_path, ext = sys.argv[1], sys.argv[2]
with open(registry_path, "r", encoding="utf-8") as f:
    data = json.load(f)
extensions = data.get("extensions", {})
raise SystemExit(0 if ext in extensions else 1)
PY
}

KNOWN_AGENTS="claude codex copilot cursor-agent opencode windsurf junie amp auggie kiro-cli qodercli roo kilo bob shai gemini tabnine kimi generic"

normalize_agent_name() {
  local agent="${1#--}"
  agent="${agent#-}"
  echo "$agent"
}

read_active_integration() {
  local integration_file=".specify/integration.json"
  [[ -f "$integration_file" ]] || return 1

  python3 - "$integration_file" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

value = data.get("name") or data.get("integration") or data.get("ai")
if value:
    print(value)
    raise SystemExit(0)
raise SystemExit(1)
PY
}

read_orca_version() {
  local extension_yml=".specify/extensions/orca/extension.yml"
  [[ -f "$extension_yml" ]] || return 1
  grep -m1 '^  version:' "$extension_yml" | sed 's/.*"\(.*\)".*/\1/'
}

show_status() {
  echo ""
  echo -e "  ${BOLD}speckit-orca status${NC}"
  echo "  ─────────────────────"
  echo ""
  echo "  repo: $(pwd)"

  if [[ -d ".specify" ]]; then
    ok "Spec Kit project detected"
  else
    warn "Spec Kit project not initialized in this directory"
  fi

  if active_integration="$(read_active_integration 2>/dev/null)"; then
    ok "Active integration: ${active_integration}"
  else
    warn "Active integration: unknown"
  fi

  if [[ -d ".specify/extensions/orca" ]]; then
    local orca_version
    orca_version="$(read_orca_version 2>/dev/null || echo "unknown")"
    ok "Orca extension installed (${orca_version})"
  else
    warn "Orca extension not installed in this repo"
  fi

  if [[ -f ".specify/extensions/.registry" ]]; then
    ok "Extension registry present"
  else
    warn "Extension registry missing"
  fi

  if [[ -d ".specify/orca" ]]; then
    ok "Orca metadata directory present"
  else
    warn "Orca metadata directory not present yet"
  fi

  if command -v specify >/dev/null 2>&1; then
    ok "specify CLI available"
  else
    warn "specify CLI missing"
  fi

  echo ""
}

run_doctor() {
  echo ""
  echo -e "  ${BOLD}speckit-orca doctor${NC}"
  echo "  ─────────────────────"
  echo ""

  local problems=0

  if command -v specify >/dev/null 2>&1; then
    ok "specify CLI found"
  else
    warn "specify CLI missing"
    echo "    Install with:"
    echo "    uv tool install specify-cli --from git+https://github.com/github/spec-kit.git"
    problems=$((problems + 1))
  fi

  if command -v speckit-orca >/dev/null 2>&1; then
    ok "speckit-orca available on PATH"
  else
    warn "speckit-orca not on PATH"
    echo '    Ensure ~/.local/bin is on PATH: export PATH="$HOME/.local/bin:$PATH"'
    problems=$((problems + 1))
  fi

  if [[ -d ".specify" ]]; then
    ok "Spec Kit project detected"
  else
    warn "Current directory is not initialized with Spec Kit"
    echo "    Run: speckit-orca claude"
    problems=$((problems + 1))
  fi

  if [[ -d ".specify" && ! -f ".specify/integration.json" ]]; then
    warn "Spec Kit project exists but active integration file is missing"
    problems=$((problems + 1))
  fi

  if [[ -d ".specify" && ! -d ".specify/extensions/orca" ]]; then
    warn "Spec Kit project exists but Orca extension is not installed"
    echo "    Run: speckit-orca claude --force"
    problems=$((problems + 1))
  fi

  if [[ $problems -eq 0 ]]; then
    ok "No obvious install or repo problems found"
  else
    warn "${problems} issue(s) detected"
  fi

  echo ""
}

# ── Parse args ────────────────────────────────────────────────────────────────
AGENTS=()
MINIMAL=0
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-self)
      install_self
      exit 0 ;;
    --uninstall-self)
      uninstall_self
      exit 0 ;;
    --status)
      show_status
      exit 0 ;;
    --doctor)
      run_doctor
      exit 0 ;;
    --force) FORCE=1; shift ;;
    --minimal) MINIMAL=1; shift ;;
    --all)
      AGENTS=($KNOWN_AGENTS)
      shift ;;
    --list)
      echo "Available agents: $KNOWN_AGENTS"
      exit 0 ;;
    --help|-h)
      echo "Usage: speckit-orca [OPTIONS] [AGENT...]"
      echo ""
      echo "Install or refresh Orca in the current repo."
      echo "Install the CLI once with: uv tool install --force git+https://github.com/SteeZyT33/spec-kit-orca.git"
      echo ""
      echo "Examples:"
      echo "  speckit-orca                     # claude (default)"
      echo "  speckit-orca codex               # current repo for a different agent"
      echo "  speckit-orca -claude             # short provider form also works"
      echo "  speckit-orca --minimal claude    # no companion extensions"
      echo "  speckit-orca --status            # repo status"
      echo "  speckit-orca --doctor            # diagnose issues"
      echo ""
      echo "Options:"
      echo "  --status        Show current repo status"
      echo "  --doctor        Diagnose install and repo issues"
      echo "  --force         Refresh Orca in the current repo"
      echo "  --install-self  Symlink this launcher into ~/.local/bin"
      echo "  --uninstall-self Remove ~/.local/bin/speckit-orca"
      echo "  --minimal       Skip companion and adopted extensions"
      echo "  --all           Populate agent list with every known agent (only"
      echo "                  the primary/first is installed; extras are ignored"
      echo "                  with a warning — kept for scripting convenience)"
      echo "  --list          Show available agent names"
      exit 0 ;;
    -*)
      candidate="$(normalize_agent_name "$1")"
      if [[ " $KNOWN_AGENTS " == *" $candidate "* ]]; then
        AGENTS+=("$candidate")
        shift
      else
        echo "Unknown option: $1 (try --help)" >&2
        exit 1
      fi ;;
    *)
      AGENTS+=("$1"); shift ;;
  esac
done

# Default to claude if no agents specified
if [[ ${#AGENTS[@]} -eq 0 ]]; then
  AGENTS=("claude")
fi

echo ""
echo -e "  ${BOLD}speckit-orca${NC}"
echo "  ──────────────────"
echo ""

# ── 1. Check specify CLI ─────────────────────────────────────────────────────
if ! command -v specify &>/dev/null; then
  fail "specify CLI not found. Install: uv tool install specify-cli --from git+https://github.com/github/spec-kit.git"
fi
ok "specify CLI found"

# ── 2. Init with first agent, add integrations for the rest ───────────────────
PRIMARY="${AGENTS[0]}"

if [[ -d ".specify" ]]; then
  ok "Existing spec-kit project"
else
  dim "Initializing with ${PRIMARY}..."
  specify init --here --ai "$PRIMARY" --script sh --no-git 2>&1 | tail -1
  ok "Initialized (primary: $PRIMARY)"
fi

# Note: spec-kit supports one active integration at a time.
# Multi-agent support would require upstream changes.
if [[ ${#AGENTS[@]} -gt 1 ]]; then
  warn "spec-kit supports one active integration at a time"
  warn "Primary agent: $PRIMARY (additional agents ignored: ${AGENTS[*]:1})"
  warn "To switch later: specify integration switch <agent>"
fi

# ── 2b. Ensure community catalog is install-allowed ──────────────────────────
ensure_community_catalog

# ── 3. Install or update orchestration ────────────────────────────────────────
# Migrate from old "orchestration" ID to "orca" if needed
if [[ -d ".specify/extensions/orchestration" && ! -d ".specify/extensions/orca" ]]; then
  dim "Migrating from orchestration → orca..."
  specify extension remove orchestration --force 2>/dev/null 1>/dev/null
  ok "Old orchestration extension removed"
fi

if [[ -d ".specify/extensions/orca" ]]; then
  # Check installed version against this script's version
  INSTALLED_VER=$(grep -m1 '^  version:' .specify/extensions/orca/extension.yml 2>/dev/null | sed 's/.*"\(.*\)".*/\1/' || echo "0.0.0")
  if [[ "$FORCE" == "1" ]]; then
    dim "Refreshing orchestration for current integration..."
    replace_orca_extension "Reinstalling..." "Orchestration refreshed" "Refresh failed — try: specify extension add orca --from $ORCH_URL."
  elif [[ "$INSTALLED_VER" == "$VERSION" || "$INSTALLED_VER" == "v${VERSION}" ]]; then
    dim "Refreshing orchestration v${INSTALLED_VER} for current integration..."
    replace_orca_extension "Reinstalling..." "Orchestration v${VERSION} refreshed" "Refresh failed — try: specify extension add orca --from $ORCH_URL."
  else
    dim "Updating orchestration ${INSTALLED_VER} → v${VERSION}..."
    replace_orca_extension "Downloading..." "Orchestration updated to v${VERSION}" "Update failed — try: specify extension add orca --from $ORCH_URL."
  fi
else
  echo -ne "  ${DIM}  Installing orchestration v${VERSION}...${NC}"
  if specify extension add orca --from "$ORCH_URL" 1>/dev/null 2>&1; then
    echo -e "\r  ${GREEN}✓${NC} Orchestration: brainstorm, micro-spec, code-review, pr-review, assign, cross-review, self-review          "
  else
    fail "Install failed — try: specify extension add orca --from $ORCH_URL"
  fi
fi

# ── 4. Companions + adopted ──────────────────────────────────────────────────
if [[ "$MINIMAL" == "1" ]]; then
  warn "Minimal — skipping companions"
else
  EXTENSIONS=(
    superb verify reconcile status
    archive doctor fixit repoindex ship speckit-utils verify-tasks
  )

  ADDED=0 PRESENT=0 UNAVAIL=0
  for ext in "${EXTENSIONS[@]}"; do
    if extension_registered "$ext"; then
      if refresh_catalog_extension "$ext"; then
        PRESENT=$((PRESENT + 1))
      else
        UNAVAIL=$((UNAVAIL + 1))
      fi
    else
      if refresh_catalog_extension "$ext"; then
        ADDED=$((ADDED + 1))
      else
        UNAVAIL=$((UNAVAIL + 1))
      fi
    fi
  done
  ok "Extensions: $ADDED added, $PRESENT refreshed, $UNAVAIL unavailable"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "  ${BOLD}Agents:${NC} ${AGENTS[*]}"
echo ""
echo "  Core:  /speckit.specify  .plan  .tasks  .implement"
echo "  Orca:  /speckit.orca.brainstorm  .micro-spec  .assign  .code-review  .pr-review  .cross-review  .self-review"
echo ""
echo "  Workflow: brainstorm → specify → plan → tasks → assign → implement → code-review → cross-review → pr-review → self-review"
echo "            micro-spec → mini-plan → verification-plan → implement → code-review"
echo ""
