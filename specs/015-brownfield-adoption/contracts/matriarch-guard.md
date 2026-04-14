# Contract: Matriarch Lane-Registration Guard for Adoption Records

**Status**: Draft
**Parent**: [015-brownfield-adoption plan.md](../plan.md)
**Binds**: `src/speckit_orca/matriarch.py` (runtime enforcement)
**Sibling**: 013's
[spec-lite matriarch-guard.md](../../013-spec-lite/contracts/matriarch-guard.md)
— 015's guard is the parallel guard for adoption records, runs in
the same `register_lane` precondition block, and follows the same
ordering rules.

---

Defines the guard that prevents adoption records from anchoring
matriarch lanes. This is the enforcement side of the 015 plan's
position-C resolution: ARs are reference-only documents describing
existing features, never active work. The matriarch primitive
coordinates active work; coordinating against documentation is a
category error.

## Rule

When `register_lane` (or any lane-creation entrypoint) receives a
`spec_id`, it MUST check whether the identifier refers to an
adoption record **before** any filesystem side effects (mailbox
root creation, reports directory creation, delegated-task file
write) and **before** resolving the spec path via `_feature_dir`.
If the check returns `True`, registration is rejected with a
structured error. No lane is created, and no runtime artifacts
are left on disk for the rejected `spec_id`.

The check runs before `_feature_dir` because `_feature_dir`
resolves under `specs/`, but adoption records live at
`.specify/orca/adopted/<id>.md` — a path `_feature_dir` would
never find.

The check runs before mailbox / reports / delegated-task creation
because the current `register_lane` performs those filesystem
side effects before flow-state is computed. A guard that fires
only at the flow-state stage would leave junk artifacts on disk
for rejected AR registrations. **This ordering is load-bearing**
— it was identified as a critical issue in the 015 plan
cross-review, and the matriarch test suite asserts the
no-side-effect invariant explicitly.

## Detection function

```python
def _is_adoption_record(
    paths: MatriarchPaths,
    spec_id: str,
) -> bool:
    """Return True if spec_id refers to an adoption record.

    Checks the canonical storage path first (fast), then falls
    back to a glob and a scoped header check (defensive — handles
    ID collisions and misplaced files).
    """
    adopted_dir = paths.repo_root / ".specify" / "orca" / "adopted"

    # 1. Canonical path check
    canonical = adopted_dir / f"{spec_id}.md"
    if canonical.exists():
        return True

    # 2. Glob for candidate files under adopted/, then require an
    #    exact stem match or a slug suffix separated by "-". This
    #    avoids prefix collisions such as spec_id="AR-001" matching
    #    a file named "AR-0010-foo.md".
    if adopted_dir.is_dir():
        for candidate in adopted_dir.glob(f"{spec_id}*.md"):
            if candidate.name == "00-overview.md":
                continue
            stem = candidate.stem
            if stem != spec_id and not stem.startswith(spec_id + "-"):
                continue
            if re.fullmatch(r"AR-\d{3}(?:-.+)?", stem):
                return True

    # 3. Scoped header check on specs/<spec_id>/spec.md — catches
    #    an AR file mistakenly authored under specs/ instead of
    #    under .specify/orca/adopted/. NOT a repo-wide scan; only
    #    this one path is checked.
    feature_dir = paths.repo_root / "specs" / spec_id
    spec_file = feature_dir / "spec.md"
    if spec_file.exists():
        # First non-blank line, matching the contract's "Header
        # match" rule in adoption-record.md.
        first_nonblank = next(
            (ln for ln in spec_file.read_text().splitlines() if ln.strip()),
            "",
        )
        if re.match(r"^# Adoption Record: AR-\d{3}(:.*)?$", first_nonblank):
            return True

    return False
```

### Parameters

- `paths`: the `MatriarchPaths` instance for the current
  repository (provides `paths.repo_root` as the repo root; paths
  are derived as `paths.repo_root / ".specify" / "orca" / ...`
  and `paths.repo_root / "specs" / ...`)
- `spec_id`: the raw identifier the operator passed to lane
  registration (e.g., `AR-001-cli-entrypoint` or just `AR-001`)

### Return value

`True` if `spec_id` resolves to an adoption record by any of
the three detection methods. `False` otherwise.

## Guard placement

```python
def register_lane(*, spec_id: str, ...) -> LaneRecord:
    # GUARDS FIRST — no filesystem side effects have run yet.
    # Both spec-lite and adoption guards MUST fire here, before
    # mailbox root creation, reports dir creation, or
    # delegated-task file writes.
    if _is_spec_lite_record(paths, spec_id):
        raise MatriarchError(
            f"Cannot register lane for spec-lite record {spec_id!r}. "
            f"Spec-lite does not participate in matriarch lanes in v1. "
            f"Spec-lite is a reference-only shape; if you need lane "
            f"coordination, hand-author a full spec under specs/ and "
            f"register that instead. The spec-lite record can be used "
            f"as reference content when drafting the full spec."
        )
    if _is_adoption_record(paths, spec_id):
        raise MatriarchError(
            f"Cannot register lane for adoption record {spec_id!r}. "
            f"Adoption records describe pre-existing features, not "
            f"active work. To coordinate work that touches "
            f"{spec_id!r}, hand-author a full spec under specs/ and "
            f"register that instead. The adoption record can be "
            f"used as reference content when drafting the full spec."
        )

    # Only now do we start the actual lane setup.
    spec_path = _feature_dir(paths, spec_id)
    mailbox_root = _ensure_mailbox_root(paths, spec_id)
    reports_dir = _ensure_reports_dir(paths, spec_id)
    ...
```

The guards fire **before** any filesystem side effects. This is
load-bearing in two ways:

1. **Path resolution**: `_feature_dir` does not know about
   `.specify/orca/adopted/` (or `.specify/orca/spec-lite/`) and
   would either fail or return a wrong path for AR / SL IDs.
2. **Atomicity**: a rejected AR registration must leave the
   workspace untouched. If mailbox root, reports dir, or
   delegated-task file are created before the guard fires, those
   artifacts persist after the rejection, polluting the repo and
   confusing later operations. Tests assert that after a rejected
   AR registration, none of those artifacts exist on disk for the
   rejected `spec_id`.

## Error shape

The error message MUST:

1. Name the rejected `spec_id`
2. State that adoption records describe pre-existing features,
   not active work (mirrors 013's "in v1" framing — leaves room
   for future relaxation without a contract change)
3. Direct the operator to hand-author a full spec under `specs/`
4. Note that the adoption record can be used as reference content
   when drafting the full spec

The error is a `MatriarchError` — the same exception type used
for other lane-registration failures (e.g., missing spec, invalid
spec_id, spec-lite rejection from 013). Callers that catch
`MatriarchError` will handle this case uniformly.

## Invariants

- No matriarch lane ever references an adoption record as its
  anchor.
- The guard fires for ALL adoption records regardless of their
  `Status` field (`adopted`, `superseded`, `retired`). A
  superseded AR has been replaced by a full spec; the operator
  should register the lane against the full spec, not the AR. A
  retired AR is historical record only; lane registration is
  even more clearly inapplicable.
- The guard fires before `_feature_dir` resolves AND before any
  mailbox / reports / delegated-task side effects (ordering is
  load-bearing).
- The guard does NOT fire for full specs under `specs/` — a full
  spec that happens to cite an adoption record by ID in its body
  (e.g., as background context) is perfectly valid as a lane
  anchor.
- The guard does NOT fire for spec-lite records — those are
  rejected by 013's separate `_is_spec_lite_record` guard, which
  runs first in the precondition block. If a record matches both
  guards (which should not happen but defends against ID
  collisions), the spec-lite error message wins by ordering.
- The guard recognizes ID-only inputs (e.g., `spec_id="AR-001"`
  without slug) via the glob fallback in the detection function.

## Testing

Tests live in the existing `tests/test_matriarch.py`:

- **Guard fires (canonical path)**: create an adoption record at
  `.specify/orca/adopted/AR-001-test.md`, call `register_lane`
  with `spec_id="AR-001-test"`, assert `MatriarchError` with the
  expected message substring.
- **Guard fires (ID-only)**: with the same record on disk, call
  `register_lane` with `spec_id="AR-001"` (no slug), assert
  `MatriarchError` via the glob fallback.
- **Guard fires (misplaced file)**: create a file at
  `specs/AR-001-test/spec.md` with `# Adoption Record: AR-001`
  header, assert `MatriarchError` via the scoped header check.
  This is a defensive path for operator mistakes; it is NOT a
  repo-wide scan.
- **Guard does not misfire on full spec**: create a full spec at
  `specs/020-test/spec.md`, call `register_lane` with
  `spec_id="020-test"`, assert lane creation succeeds (regression
  check — the guard does not break normal lane registration).
- **Guard does not misfire on spec-lite**: create a spec-lite at
  `.specify/orca/spec-lite/SL-001-test.md`, call `register_lane`
  with `spec_id="SL-001-test"`, assert `MatriarchError` whose
  message points at the spec-lite alternative (NOT the adoption
  alternative), confirming the spec-lite guard fires first by
  ordering.
- **Guard fires for all status values**: create three AR files
  with `Status: adopted`, `Status: superseded`, and
  `Status: retired` respectively. Assert all three reject lane
  registration with the same error shape. Status does not
  affect guard behavior.
- **No-side-effects on rejection** (critical): after a rejected
  AR registration, assert that:
    - `<paths.mailbox_root> / spec_id` does NOT exist
    - `<paths.reports_root> / spec_id` does NOT exist
    - any delegated-task file for `spec_id` does NOT exist
  Verifies the guard fires before any filesystem side effects.

## Supersedes

This guard is new in 015. It does not supersede an existing
contract, but it constrains `matriarch.py`'s `register_lane`
function by adding a second precondition check (alongside 013's
spec-lite guard) that did not exist before 013 + 015.
