# flow-state-projection

Projects an SDD feature directory into a JSON snapshot of its current stage, milestones, review status, and recommended next step. Thin adapter over `orca.flow_state.compute_flow_state` - the heavy lifting (artifact discovery, review-milestone derivation, evidence collection) lives in `flow_state.py`, which this capability does not own.

## Input

Either:
- `feature_dir`: absolute or repo-relative path to the feature directory
- OR `feature_id` + `repo_root`: capability resolves `repo_root/specs/feature_id`

See `schema/input.json`.

## Output

See `schema/output.json`. Mirrors `FlowStateResult.to_dict()` exactly. Top-level fields are stable; `completed_milestones[]` / `incomplete_milestones[]` / `review_milestones[]` items use `{"type": "object"}` in the schema rather than detailed item shapes - those shapes are owned by `orca.flow_state` and may evolve. Consumers needing strict per-milestone schemas should depend on `orca.flow_state` types directly.

## Errors

- `INPUT_INVALID`: missing both `feature_id` and `feature_dir`; resolved feature directory does not exist; `feature_id` provided without `repo_root`.
- `INTERNAL`: unexpected exception from `compute_flow_state` (filesystem error, malformed feature artifact). Detail includes `underlying` exception class name.

## CLI

`orca-cli flow-state-projection --feature-dir specs/001-foo`
or
`orca-cli flow-state-projection --feature-id 001-foo --repo-root /path/to/repo`
