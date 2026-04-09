#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./orca-worktree-lib.sh
source "$SCRIPT_DIR/orca-worktree-lib.sh"

usage() {
  cat <<'EOF'
Usage:
  orca-worktree.sh create [--feature <feature>] [--lane <lane>] [--branch <branch>] [--path <path>] [--agent <agent>] [--role <role>] [--task-scope <csv>] [--notes <text>] [--base-ref <branch>]
  orca-worktree.sh list [--feature <feature>] [--all]
  orca-worktree.sh status [--feature <feature>] [--lane <lane-id>] [--all]
  orca-worktree.sh cleanup [--feature <feature>] [--all] [--apply]
EOF
}

fail() {
  echo "$1" >&2
  exit 1
}

current_feature_context() {
  local current_lane lane_file lane_feature branch_feature

  current_lane="$(orca_current_lane_id || true)"
  if [[ -n "$current_lane" ]]; then
    lane_file="$(orca_lane_path "$current_lane")"
    if [[ -f "$lane_file" ]]; then
      lane_feature="$(orca_lane_field "$lane_file" feature || true)"
      if [[ -n "$lane_feature" ]]; then
        echo "$lane_feature"
        return 0
      fi
    fi
  fi

  branch_feature="$(orca_feature_from_branch "$(orca_current_branch)")"
  echo "$branch_feature"
}

print_drift_warnings() {
  local feature_filter="${1:-}"
  local registry_lane_ids=()
  local lane_id lane_file lane_feature lane_branch lane_path lane_status git_branch
  local -A git_paths=()
  local -A git_branches=()
  local found_any=0

  while IFS=$'\t' read -r worktree_path branch_name; do
    [[ -z "${worktree_path:-}" ]] && continue
    git_paths["$worktree_path"]=1
    git_branches["$branch_name"]="$worktree_path"
  done < <(orca_git_worktree_snapshot)

  while IFS= read -r lane_id; do
    [[ -z "$lane_id" ]] && continue
    registry_lane_ids+=("$lane_id")
  done < <(orca_registry_lane_ids)

  for lane_id in "${registry_lane_ids[@]}"; do
    lane_file="$(orca_lane_path "$lane_id")"
    if [[ ! -f "$lane_file" ]]; then
      echo "WARNING: Registry entry '$lane_id' has no matching lane record."
      found_any=1
      continue
    fi

    lane_feature="$(orca_lane_field "$lane_file" feature || true)"
    if [[ -n "$feature_filter" && "$lane_feature" != "$feature_filter" ]]; then
      continue
    fi

    lane_branch="$(orca_lane_field "$lane_file" branch || true)"
    lane_path="$(orca_lane_field "$lane_file" path || true)"
    lane_status="$(orca_lane_field "$lane_file" status || true)"

    if [[ "$lane_status" != "merged" && "$lane_status" != "retired" && ! -d "$lane_path" ]]; then
      echo "WARNING: Lane '$lane_id' points at a missing path: $lane_path"
      found_any=1
    fi

    if [[ "$lane_status" != "merged" && "$lane_status" != "retired" && -z "${git_paths[$lane_path]:-}" ]]; then
      echo "WARNING: Lane '$lane_id' path is not present in 'git worktree list': $lane_path"
      found_any=1
    fi

    git_branch="${git_branches[$lane_branch]:-}"
    if [[ "$lane_status" != "merged" && "$lane_status" != "retired" && -n "$git_branch" && "$git_branch" != "$lane_path" ]]; then
      echo "WARNING: Lane '$lane_id' branch '$lane_branch' is checked out at '$git_branch', not '$lane_path'."
      found_any=1
    fi
  done

  while IFS= read -r lane_file; do
    lane_id="$(basename "$lane_file" .json)"
    if [[ "$lane_id" == "registry" ]]; then
      continue
    fi
    local member_pattern=" ${lane_id} "
    if [[ ! " ${registry_lane_ids[*]} " =~ $member_pattern ]]; then
      echo "WARNING: Lane record '$lane_id' exists on disk but is missing from the registry."
      found_any=1
    fi
  done < <(find "$(orca_worktrees_dir)" -maxdepth 1 -name '*.json' -type f 2>/dev/null | sort)

  return "$found_any"
}

list_lanes() {
  local feature_filter="$1"
  local include_all="$2"
  local lane_ids=()
  local lane_id lane_file feature branch path status role

  while IFS= read -r lane_id; do
    [[ -z "$lane_id" ]] && continue
    lane_ids+=("$lane_id")
  done < <(orca_registry_lane_ids)

  if [[ ${#lane_ids[@]} -eq 0 ]]; then
    echo "No Orca worktree metadata found."
    return 0
  fi

  printf "%-36s %-28s %-12s %-12s %s\n" "Lane" "Branch" "Status" "Role" "Path"
  printf "%-36s %-28s %-12s %-12s %s\n" "----" "------" "------" "----" "----"

  for lane_id in "${lane_ids[@]}"; do
    lane_file="$(orca_lane_path "$lane_id")"
    [[ -f "$lane_file" ]] || continue
    feature="$(orca_lane_field "$lane_file" feature || true)"
    status="$(orca_lane_field "$lane_file" status || true)"

    if [[ -n "$feature_filter" && "$feature" != "$feature_filter" ]]; then
      continue
    fi

    if [[ "$include_all" != "true" && "$status" != "planned" && "$status" != "active" && "$status" != "blocked" ]]; then
      continue
    fi

    branch="$(orca_lane_field "$lane_file" branch || true)"
    path="$(orca_lane_field "$lane_file" path || true)"
    role="$(orca_lane_field "$lane_file" role || true)"

    printf "%-36s %-28s %-12s %-12s %s\n" "$lane_id" "$branch" "$status" "$role" "$path"
  done
}

run_create() {
  local feature="" lane="" branch_name="" explicit_path=""
  local agent role task_scope notes base_ref parent_feature_branch=""
  local current_branch default_branch inferred_feature lane_id worktree_path lane_file
  local target_branch branch_exists existing_lane_by_branch

  agent="$(orca_active_ai)"
  role="implementer"
  task_scope="UNSCOPED"
  notes=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --feature) feature="$2"; shift 2 ;;
      --lane) lane="$2"; shift 2 ;;
      --branch) branch_name="$2"; shift 2 ;;
      --path) explicit_path="$2"; shift 2 ;;
      --agent) agent="$2"; shift 2 ;;
      --role) role="$2"; shift 2 ;;
      --task-scope) task_scope="$2"; shift 2 ;;
      --notes) notes="$2"; shift 2 ;;
      --base-ref) base_ref="$2"; shift 2 ;;
      *) fail "Unknown create option: $1" ;;
    esac
  done

  [[ -n "$lane" && -n "$branch_name" ]] && fail "ERROR: Use either --lane or --branch, not both."

  orca_require_main_worktree
  orca_registry_init

  current_branch="$(orca_current_branch)"
  [[ "$current_branch" != "HEAD" ]] || fail "ERROR: Detached HEAD is not supported for Orca worktree creation."

  inferred_feature="$(orca_feature_from_branch "$current_branch")"
  if [[ -z "$feature" ]]; then
    feature="$inferred_feature"
  fi
  [[ -n "$feature" ]] || fail "ERROR: Could not infer feature from current branch '$current_branch'. Pass --feature explicitly."

  if [[ -n "$lane" ]]; then
    target_branch="${feature}-${lane}"
    parent_feature_branch="$feature"
  elif [[ -n "$branch_name" ]]; then
    target_branch="$branch_name"
    if [[ "$branch_name" != "$feature" ]]; then
      parent_feature_branch="$feature"
    fi
  else
    target_branch="$current_branch"
    if [[ "$current_branch" != "$feature" ]]; then
      parent_feature_branch="$feature"
    fi
  fi

  lane_id="$target_branch"
  [[ "$lane_id" =~ ^[A-Za-z0-9._-]+$ ]] || fail "ERROR: Lane ID '$lane_id' contains unsupported characters."

  existing_lane_by_branch="$(orca_find_duplicate_branch_owner "$target_branch" || true)"
  if [[ -n "$existing_lane_by_branch" ]]; then
    fail "ERROR: Branch '$target_branch' is already registered to lane '$existing_lane_by_branch'."
  fi

  lane_file="$(orca_lane_path "$lane_id")"
  [[ ! -f "$lane_file" ]] || fail "ERROR: Lane record already exists: $lane_file"

  worktree_path="$(orca_compute_worktree_path "$target_branch" "$explicit_path")"
  orca_validate_target_path "$worktree_path"

  default_branch="${base_ref:-$(orca_default_branch)}"
  local switched_branch="false"
  if [[ "$target_branch" == "$current_branch" && "$current_branch" != "$default_branch" ]]; then
    if ! git checkout "$default_branch" >/dev/null 2>&1; then
      fail "ERROR: Could not switch to default branch '$default_branch' before creating the worktree. Commit or stash local changes first."
    fi
    switched_branch="true"
  fi

  branch_exists="false"
  if git rev-parse --verify "$target_branch" >/dev/null 2>&1; then
    branch_exists="true"
  fi

  if [[ "$branch_exists" == "true" ]]; then
    if ! git worktree add "$worktree_path" "$target_branch"; then
      fail "ERROR: Failed to create worktree for existing branch '$target_branch' at '$worktree_path'."
    fi
  else
    if ! git worktree add -b "$target_branch" "$worktree_path" "$current_branch"; then
      fail "ERROR: Failed to create worktree branch '$target_branch' from '$current_branch' at '$worktree_path'."
    fi
  fi

  if ! orca_write_lane_record "$lane_file" "$lane_id" "$feature" "$target_branch" "$worktree_path" "$agent" "$role" "$task_scope" "active" "$default_branch" "$parent_feature_branch" "$notes" ""; then
    git worktree remove "$worktree_path" >/dev/null 2>&1 || true
    fail "ERROR: Worktree was created but metadata write failed. Removed the new worktree to avoid partial state."
  fi

  orca_validate_lane_record "$lane_file"
  orca_registry_add_lane "$lane_id"

  cat <<EOF
Worktree created.

Lane ID:  $lane_id
Feature:  $feature
Branch:   $target_branch
Path:     $worktree_path
Base Ref: $default_branch
EOF

  if [[ "$switched_branch" == "true" ]]; then
    echo "Note: Current branch was switched to '$default_branch' to allow worktree checkout of '$target_branch'."
    echo
  fi

  cat <<EOF
Next steps:
  cd $worktree_path
  codex
EOF
}

run_list() {
  local feature="" include_all="false"
  local current_feature

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --feature) feature="$2"; shift 2 ;;
      --all) include_all="true"; shift ;;
      *) fail "Unknown list option: $1" ;;
    esac
  done

  if [[ -z "$feature" ]]; then
    current_feature="$(current_feature_context)"
    feature="${current_feature:-}"
  fi

  list_lanes "$feature" "$include_all"
  print_drift_warnings "$feature" || true
}

run_status() {
  local feature="" requested_lane="" include_all="false"
  local current_lane current_branch current_feature
  local lane_ids=()
  local lane_id lane_file feature_value branch path status task_scope

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --feature) feature="$2"; shift 2 ;;
      --lane) requested_lane="$2"; shift 2 ;;
      --all) include_all="true"; shift ;;
      *) fail "Unknown status option: $1" ;;
    esac
  done

  current_branch="$(orca_current_branch)"
  current_feature="$(current_feature_context)"
  feature="${feature:-$current_feature}"
  current_lane="$(orca_current_lane_id || true)"

  echo "Current branch: $current_branch"
  echo "Current feature: ${feature:-unknown}"
  echo "Current lane: ${current_lane:-none}"
  echo

  if [[ -n "$requested_lane" ]]; then
    lane_ids=("$requested_lane")
  elif [[ -n "$feature" ]]; then
    while IFS= read -r lane_id; do
      [[ -n "$lane_id" ]] && lane_ids+=("$lane_id")
    done < <(orca_lane_ids_for_feature "$feature")
  else
    while IFS= read -r lane_id; do
      [[ -n "$lane_id" ]] && lane_ids+=("$lane_id")
    done < <(orca_registry_lane_ids)
  fi

  if [[ ${#lane_ids[@]} -eq 0 ]]; then
    echo "No matching Orca lanes found."
    print_drift_warnings "$feature" || true
    return 0
  fi

  printf "%-36s %-10s %-28s %s\n" "Lane" "Status" "Branch" "Task Scope"
  printf "%-36s %-10s %-28s %s\n" "----" "------" "------" "----------"

  for lane_id in "${lane_ids[@]}"; do
    lane_file="$(orca_lane_path "$lane_id")"
    [[ -f "$lane_file" ]] || { echo "WARNING: Missing lane record for '$lane_id'."; continue; }
    feature_value="$(orca_lane_field "$lane_file" feature || true)"
    status="$(orca_lane_field "$lane_file" status || true)"
    if [[ "$include_all" != "true" && -n "$feature" && "$feature_value" != "$feature" ]]; then
      continue
    fi
    branch="$(orca_lane_field "$lane_file" branch || true)"
    path="$(orca_lane_field "$lane_file" path || true)"
    task_scope="$(paste -sd, < <(orca_lane_field "$lane_file" task_scope || true))"
    printf "%-36s %-10s %-28s %s\n" "$lane_id" "$status" "$branch" "$task_scope"
    echo "  Path: $path"
  done

  echo
  print_drift_warnings "$feature" || true
}

run_cleanup() {
  local feature="" include_all="false" apply="false"
  local lane_ids=()
  local lane_id lane_file lane_status lane_branch lane_path integration_ref parent_feature_branch
  local merged_in_git candidate_count=0 cleaned_count=0
  local path_is_registered

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --feature) feature="$2"; shift 2 ;;
      --all) include_all="true"; shift ;;
      --apply) apply="true"; shift ;;
      *) fail "Unknown cleanup option: $1" ;;
    esac
  done

  if [[ -z "$feature" && "$include_all" != "true" ]]; then
    feature="$(current_feature_context)"
  fi

  if [[ -n "$feature" ]]; then
    while IFS= read -r lane_id; do
      [[ -n "$lane_id" ]] && lane_ids+=("$lane_id")
    done < <(orca_lane_ids_for_feature "$feature")
  else
    while IFS= read -r lane_id; do
      [[ -n "$lane_id" ]] && lane_ids+=("$lane_id")
    done < <(orca_registry_lane_ids)
  fi

  [[ ${#lane_ids[@]} -gt 0 ]] || { echo "No Orca lanes found for cleanup."; return 0; }

  for lane_id in "${lane_ids[@]}"; do
    lane_file="$(orca_lane_path "$lane_id")"
    [[ -f "$lane_file" ]] || { echo "WARNING: Missing lane record for '$lane_id'."; continue; }

    lane_status="$(orca_lane_field "$lane_file" status || true)"
    lane_branch="$(orca_lane_field "$lane_file" branch || true)"
    lane_path="$(orca_lane_field "$lane_file" path || true)"
    parent_feature_branch="$(orca_lane_field "$lane_file" parent_feature_branch || true)"
    integration_ref="$(orca_lane_field "$lane_file" base_ref || true)"
    if [[ -n "$parent_feature_branch" ]] && git rev-parse --verify "$parent_feature_branch" >/dev/null 2>&1; then
      integration_ref="$parent_feature_branch"
    fi

    merged_in_git="false"
    if git rev-parse --verify "$lane_branch" >/dev/null 2>&1 && git rev-parse --verify "$integration_ref" >/dev/null 2>&1; then
      if git merge-base --is-ancestor "$lane_branch" "$integration_ref" >/dev/null 2>&1; then
        merged_in_git="true"
      fi
    fi

    path_is_registered="false"
    if git worktree list --porcelain | grep -F "worktree $lane_path" >/dev/null 2>&1; then
      path_is_registered="true"
    fi

    if [[ "$lane_status" != "merged" && "$lane_status" != "retired" ]]; then
      if [[ "$merged_in_git" == "true" ]]; then
        echo "WARNING: Lane '$lane_id' is merged into '$integration_ref' in git but still marked '$lane_status'. Review metadata before cleanup."
      else
        echo "WARNING: Lane '$lane_id' is still '$lane_status'. Cleanup skips active or ambiguous lanes."
      fi
      continue
    fi

    if [[ ! -d "$lane_path" && "$path_is_registered" != "true" ]]; then
      continue
    fi

    candidate_count=$((candidate_count + 1))
    echo "Cleanup candidate: $lane_id ($lane_status) -> $lane_path"

    if [[ "$apply" != "true" ]]; then
      continue
    fi

    if [[ ! -d "$lane_path" ]]; then
      git worktree prune >/dev/null 2>&1 || true
    elif [[ "$path_is_registered" == "true" ]]; then
      if ! git worktree remove "$lane_path"; then
        echo "WARNING: Could not remove worktree '$lane_path' for lane '$lane_id'. It may have uncommitted changes. Run 'git worktree remove --force $lane_path' manually if needed."
        continue
      fi
      git worktree prune >/dev/null 2>&1 || true
    elif [[ -d "$lane_path" ]]; then
      echo "WARNING: Skipping '$lane_id' because '$lane_path' exists on disk but is not a registered git worktree."
      continue
    fi

    if [[ "$lane_status" == "merged" ]]; then
      orca_update_lane_status "$lane_file" "merged"
    else
      orca_update_lane_status "$lane_file" "retired"
    fi
    cleaned_count=$((cleaned_count + 1))
  done

  if [[ "$apply" == "true" ]]; then
    echo "Cleanup complete: $cleaned_count lane(s) processed."
  else
    echo "Dry run complete: $candidate_count cleanup candidate(s). Re-run with --apply to remove them."
  fi
}

main() {
  local command="${1:-}"
  [[ -n "$command" ]] || { usage; exit 1; }
  shift || true

  case "$command" in
    create) run_create "$@" ;;
    list) run_list "$@" ;;
    status) run_status "$@" ;;
    cleanup) run_cleanup "$@" ;;
    -h|--help|help) usage ;;
    *) fail "Unknown command: $command" ;;
  esac
}

main "$@"
