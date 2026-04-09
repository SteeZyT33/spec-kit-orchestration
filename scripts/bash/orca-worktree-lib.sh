#!/usr/bin/env bash
set -euo pipefail

orca_repo_root() {
  git rev-parse --show-toplevel
}

orca_git_dir() {
  git rev-parse --git-dir
}

orca_current_branch() {
  git rev-parse --abbrev-ref HEAD
}

orca_repo_name() {
  basename "$(orca_repo_root)"
}

orca_is_main_worktree() {
  local repo_root git_dir
  repo_root="$(orca_repo_root)"
  git_dir="$(orca_git_dir)"
  [[ "$git_dir" == ".git" || "$git_dir" == "$repo_root/.git" ]]
}

orca_require_main_worktree() {
  if ! orca_is_main_worktree; then
    echo "ERROR: Already inside a git worktree. Nested Orca worktree creation is not supported." >&2
    return 1
  fi
}

orca_default_branch() {
  local default_branch candidate

  default_branch="$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')"
  if [[ -n "$default_branch" ]]; then
    echo "$default_branch"
    return 0
  fi

  for candidate in main master; do
    if git rev-parse --verify "$candidate" >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done

  echo "main"
}

orca_now_utc() {
  python3 - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
PY
}

orca_orca_root() {
  echo "$(orca_repo_root)/.specify/orca"
}

orca_worktrees_dir() {
  echo "$(orca_orca_root)/worktrees"
}

orca_registry_path() {
  echo "$(orca_worktrees_dir)/registry.json"
}

orca_lane_path() {
  local lane_id="$1"
  echo "$(orca_worktrees_dir)/${lane_id}.json"
}

orca_config_path() {
  echo "$(orca_orca_root)/config.json"
}

orca_active_ai() {
  local init_options
  init_options="$(orca_repo_root)/.specify/init-options.json"
  python3 - "$init_options" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
if not path.exists():
    print("generic")
    raise SystemExit(0)

try:
    data = json.loads(path.read_text())
except Exception:
    print("generic")
    raise SystemExit(0)

print(data.get("ai") or data.get("integration") or "generic")
PY
}

orca_worktree_base_path_raw() {
  if [[ -n "${ORCA_WORKTREE_BASE_PATH:-}" ]]; then
    echo "$ORCA_WORKTREE_BASE_PATH"
    return 0
  fi

  python3 - "$(orca_config_path)" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
if not path.exists():
    print("..")
    raise SystemExit(0)

try:
    data = json.loads(path.read_text())
except Exception:
    print("..")
    raise SystemExit(0)

worktrees = data.get("worktrees", {})
print(worktrees.get("base_path", ".."))
PY
}

orca_resolve_base_path() {
  local base_path repo_root
  base_path="$(orca_worktree_base_path_raw)"
  repo_root="$(orca_repo_root)"

  if [[ "$base_path" = /* ]]; then
    (cd "$base_path" && pwd)
  else
    (cd "$repo_root/$base_path" && pwd)
  fi
}

orca_path_separator() {
  local resolved_base
  resolved_base="$(orca_resolve_base_path)"

  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*|Windows_NT)
      echo "--"
      ;;
    Linux)
      if [[ "$resolved_base" == /mnt/[a-z]/* ]] && grep -qi microsoft /proc/version 2>/dev/null; then
        echo "--"
      else
        echo ":"
      fi
      ;;
    *)
      echo ":"
      ;;
  esac
}

orca_compute_worktree_path() {
  local branch_name="$1"
  local explicit_path="${2:-}"
  local base_path repo_name separator

  if [[ -n "$explicit_path" ]]; then
    python3 - "$explicit_path" "$(pwd)" <<'PY'
import os
import sys

path = sys.argv[1]
cwd = sys.argv[2]
if os.path.isabs(path):
    print(os.path.abspath(path))
else:
    print(os.path.abspath(os.path.join(cwd, path)))
PY
    return 0
  fi

  base_path="$(orca_resolve_base_path)"
  repo_name="$(orca_repo_name)"
  separator="$(orca_path_separator)"
  echo "${base_path}/${repo_name}${separator}${branch_name}"
}

orca_feature_from_branch() {
  local branch_name="$1"

  if [[ "$branch_name" =~ ^[0-9]{3}- ]]; then
    echo "$branch_name"
    return 0
  fi

  echo ""
}

orca_ensure_runtime_dirs() {
  mkdir -p "$(orca_worktrees_dir)" "$(orca_orca_root)/logs" "$(orca_orca_root)/inbox"
}

orca_registry_init() {
  local registry_path repo_name
  registry_path="$(orca_registry_path)"
  repo_name="$(orca_repo_name)"

  orca_ensure_runtime_dirs

  python3 - "$registry_path" "$repo_name" <<'PY'
import json
import pathlib
import sys
import tempfile
from datetime import datetime, timezone

path = pathlib.Path(sys.argv[1])
repo_name = sys.argv[2]

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def write_atomic(target: pathlib.Path, payload: dict) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=target.parent) as tmp:
        json.dump(payload, tmp, indent=2)
        tmp.write("\n")
        temp_name = tmp.name
    pathlib.Path(temp_name).replace(target)

if path.exists():
    data = json.loads(path.read_text())
    if not isinstance(data.get("lanes"), list):
      raise SystemExit(f"Invalid registry: {path}")
    if "schema_version" not in data:
      raise SystemExit(f"Invalid registry: {path}")
    raise SystemExit(0)

write_atomic(
    path,
    {
        "schema_version": "1.0",
        "repo_name": repo_name,
        "lanes": [],
        "updated_at": now(),
    },
)
PY
}

orca_registry_lane_ids() {
  python3 - "$(orca_registry_path)" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
if not path.exists():
    raise SystemExit(0)

data = json.loads(path.read_text())
for lane_id in data.get("lanes", []):
    print(lane_id)
PY
}

orca_registry_add_lane() {
  local lane_id="$1"
  python3 - "$(orca_registry_path)" "$lane_id" <<'PY'
import json
import pathlib
import sys
import tempfile
from datetime import datetime, timezone

path = pathlib.Path(sys.argv[1])
lane_id = sys.argv[2]
data = json.loads(path.read_text())
lanes = data.setdefault("lanes", [])
if lane_id not in lanes:
    lanes.append(lane_id)
data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent) as tmp:
    json.dump(data, tmp, indent=2)
    tmp.write("\n")
    temp_name = tmp.name
pathlib.Path(temp_name).replace(path)
PY
}

orca_registry_remove_lane() {
  local lane_id="$1"
  python3 - "$(orca_registry_path)" "$lane_id" <<'PY'
import json
import pathlib
import sys
import tempfile
from datetime import datetime, timezone

path = pathlib.Path(sys.argv[1])
lane_id = sys.argv[2]
if not path.exists():
    raise SystemExit(0)

data = json.loads(path.read_text())
lanes = [item for item in data.get("lanes", []) if item != lane_id]
data["lanes"] = lanes
data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent) as tmp:
    json.dump(data, tmp, indent=2)
    tmp.write("\n")
    temp_name = tmp.name
pathlib.Path(temp_name).replace(path)
PY
}

orca_lane_field() {
  local lane_file="$1"
  local field_name="$2"
  python3 - "$lane_file" "$field_name" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
field_name = sys.argv[2]

if not path.exists():
    raise SystemExit(1)

data = json.loads(path.read_text())
value = data.get(field_name)
if value is None:
    raise SystemExit(1)
if isinstance(value, list):
    for item in value:
        print(item)
else:
    print(value)
PY
}

orca_lane_ids_for_feature() {
  local feature="$1"
  python3 - "$(orca_registry_path)" "$(orca_worktrees_dir)" "$feature" <<'PY'
import json
import pathlib
import sys

registry = pathlib.Path(sys.argv[1])
worktrees_dir = pathlib.Path(sys.argv[2])
feature = sys.argv[3]

if not registry.exists():
    raise SystemExit(0)

data = json.loads(registry.read_text())
for lane_id in data.get("lanes", []):
    lane_path = worktrees_dir / f"{lane_id}.json"
    if not lane_path.exists():
        continue
    lane = json.loads(lane_path.read_text())
    if lane.get("feature") == feature:
        print(lane_id)
PY
}

orca_find_duplicate_branch_owner() {
  local branch_name="$1"
  python3 - "$(orca_registry_path)" "$(orca_worktrees_dir)" "$branch_name" <<'PY'
import json
import pathlib
import sys

registry = pathlib.Path(sys.argv[1])
worktrees_dir = pathlib.Path(sys.argv[2])
branch_name = sys.argv[3]

if not registry.exists():
    raise SystemExit(0)

data = json.loads(registry.read_text())
for lane_id in data.get("lanes", []):
    lane_path = worktrees_dir / f"{lane_id}.json"
    if not lane_path.exists():
        continue
    lane = json.loads(lane_path.read_text())
    if lane.get("branch") == branch_name:
        print(lane_id)
        raise SystemExit(0)
PY
}

orca_write_lane_record() {
  local lane_file="$1"
  local lane_id="$2"
  local feature="$3"
  local branch_name="$4"
  local worktree_path="$5"
  local agent="$6"
  local role="$7"
  local task_scope_csv="$8"
  local status="$9"
  local base_ref="${10}"
  local parent_feature_branch="${11}"
  local notes="${12}"
  local shared_files_csv="${13}"

  python3 - "$lane_file" "$lane_id" "$feature" "$branch_name" "$worktree_path" "$agent" "$role" "$task_scope_csv" "$status" "$base_ref" "$parent_feature_branch" "$notes" "$shared_files_csv" <<'PY'
import json
import pathlib
import sys
import tempfile
from datetime import datetime, timezone

lane_file = pathlib.Path(sys.argv[1])
lane_id = sys.argv[2]
feature = sys.argv[3]
branch_name = sys.argv[4]
worktree_path = sys.argv[5]
agent = sys.argv[6]
role = sys.argv[7]
task_scope_csv = sys.argv[8]
status = sys.argv[9]
base_ref = sys.argv[10]
parent_feature_branch = sys.argv[11]
notes = sys.argv[12]
shared_files_csv = sys.argv[13]

task_scope = [item for item in task_scope_csv.split(",") if item]
shared_files = [item for item in shared_files_csv.split(",") if item]
timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

existing = {}
if lane_file.exists():
    existing = json.loads(lane_file.read_text())

payload = {
    "schema_version": "1.0",
    "id": lane_id,
    "feature": feature,
    "branch": branch_name,
    "path": worktree_path,
    "agent": agent,
    "role": role,
    "task_scope": task_scope,
    "status": status,
    "base_ref": base_ref,
    "shared_files": shared_files,
    "notes": notes,
    "created_at": existing.get("created_at", timestamp),
    "updated_at": timestamp,
}

if parent_feature_branch:
    payload["parent_feature_branch"] = parent_feature_branch

with tempfile.NamedTemporaryFile("w", delete=False, dir=lane_file.parent) as tmp:
    json.dump(payload, tmp, indent=2)
    tmp.write("\n")
    temp_name = tmp.name
pathlib.Path(temp_name).replace(lane_file)
PY
}

orca_update_lane_status() {
  local lane_file="$1"
  local new_status="$2"
  python3 - "$lane_file" "$new_status" <<'PY'
import json
import pathlib
import sys
import tempfile
from datetime import datetime, timezone

lane_file = pathlib.Path(sys.argv[1])
new_status = sys.argv[2]

if not lane_file.exists():
    raise SystemExit(1)

data = json.loads(lane_file.read_text())
data["status"] = new_status
data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

with tempfile.NamedTemporaryFile("w", delete=False, dir=lane_file.parent) as tmp:
    json.dump(data, tmp, indent=2)
    tmp.write("\n")
    temp_name = tmp.name
pathlib.Path(temp_name).replace(lane_file)
PY
}

orca_validate_lane_record() {
  local lane_file="$1"
  python3 - "$lane_file" <<'PY'
import json
import pathlib
import sys

required = [
    "schema_version",
    "id",
    "feature",
    "branch",
    "path",
    "agent",
    "role",
    "task_scope",
    "status",
    "base_ref",
    "created_at",
    "updated_at",
]
allowed_statuses = {"planned", "active", "blocked", "merged", "retired"}

path = pathlib.Path(sys.argv[1])
if not path.exists():
    raise SystemExit(f"Missing lane record: {path}")

data = json.loads(path.read_text())
for field in required:
    if field not in data:
        raise SystemExit(f"Lane record missing required field '{field}': {path}")

if not isinstance(data["task_scope"], list):
    raise SystemExit(f"Lane record has invalid task_scope: {path}")

if data["status"] not in allowed_statuses:
    raise SystemExit(f"Lane record has invalid status '{data['status']}': {path}")

if not data["task_scope"] and data["status"] != "planned":
    raise SystemExit(f"Lane record has empty task_scope for non-planned lane: {path}")
PY
}

orca_validate_target_path() {
  local target_path="$1"
  local repo_root
  repo_root="$(orca_repo_root)"

  python3 - "$target_path" "$repo_root" <<'PY'
import os
import pathlib
import sys

target = pathlib.Path(sys.argv[1]).expanduser()
repo_root = pathlib.Path(sys.argv[2]).resolve()
target_abs = target.resolve(strict=False)

if target_abs == repo_root or repo_root in target_abs.parents:
    raise SystemExit(f"ERROR: Worktree path is inside the main repository: {target_abs}")

if target_abs.exists():
    raise SystemExit(f"ERROR: Target path already exists: {target_abs}")

parent = target_abs.parent
if not parent.exists():
    raise SystemExit(f"ERROR: Parent directory does not exist for worktree path: {parent}")
PY
}

orca_current_lane_id() {
  python3 - "$(orca_registry_path)" "$(orca_worktrees_dir)" "$(pwd)" "$(orca_current_branch)" <<'PY'
import json
import pathlib
import sys

registry = pathlib.Path(sys.argv[1])
worktrees_dir = pathlib.Path(sys.argv[2])
cwd = pathlib.Path(sys.argv[3]).resolve()
branch = sys.argv[4]

if not registry.exists():
    raise SystemExit(0)

data = json.loads(registry.read_text())
for lane_id in data.get("lanes", []):
    lane_path = worktrees_dir / f"{lane_id}.json"
    if not lane_path.exists():
        continue
    lane = json.loads(lane_path.read_text())
    lane_cwd = pathlib.Path(lane.get("path", ".")).resolve(strict=False)
    if lane.get("branch") == branch or lane_cwd == cwd:
        print(lane_id)
        raise SystemExit(0)
PY
}

orca_git_worktree_snapshot() {
  python3 - <<'PY'
import subprocess

result = subprocess.run(
    ["git", "worktree", "list", "--porcelain"],
    check=True,
    capture_output=True,
    text=True,
)

current = {}
for raw_line in result.stdout.splitlines():
    line = raw_line.strip()
    if not line:
        if current.get("worktree"):
            print(f"{current.get('worktree','')}\t{current.get('branch','')}")
        current = {}
        continue
    if line.startswith("worktree "):
        current["worktree"] = line.split(" ", 1)[1]
    elif line.startswith("branch refs/heads/"):
        current["branch"] = line.removeprefix("branch refs/heads/")

if current.get("worktree"):
    print(f"{current.get('worktree','')}\t{current.get('branch','')}")
PY
}
