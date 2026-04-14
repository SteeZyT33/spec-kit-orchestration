# Contract: Matriarch Lane-Registration Guard for Spec-Lite

**Status**: Draft
**Parent**: [013-spec-lite plan.md](../plan.md)
**Binds**: `src/speckit_orca/matriarch.py` (runtime enforcement)

---

Defines the guard that prevents spec-lite records from anchoring
matriarch lanes. This is the enforcement side of the 013 plan's
question 4 resolution: "spec-lite cannot anchor a matriarch lane
in v1."

## Rule

When `register_lane` (or any lane-creation entrypoint) receives a
`spec_id`, it MUST check whether the identifier refers to a
spec-lite record **before** resolving the spec path via
`_feature_dir`. If the check returns `True`, registration is
rejected with a structured error. No lane is created.

The check runs before `_feature_dir` because `_feature_dir`
resolves under `specs/`, but spec-lite records live at
`.specify/orca/spec-lite/<id>.md` — a path `_feature_dir` would
never find.

## Detection function

```python
def _is_spec_lite_record(
    paths: MatriarchPaths,
    spec_id: str,
) -> bool:
    """Return True if spec_id refers to a spec-lite record.

    Checks the canonical storage path first (fast), then falls
    back to a header scan if the file exists but lives outside
    the canonical directory (defensive).
    """
    spec_lite_dir = paths.repo_root / ".specify" / "orca" / "spec-lite"

    # 1. Canonical path check
    canonical = spec_lite_dir / f"{spec_id}.md"
    if canonical.exists():
        return True

    # 2. Glob for any file matching the ID stem under spec-lite/
    if spec_lite_dir.is_dir():
        for candidate in spec_lite_dir.glob(f"{spec_id}*.md"):
            if candidate.name == "00-overview.md":
                continue
            return True

    # 3. Header scan fallback — check if any file with this stem
    #    anywhere in the repo has the spec-lite header marker
    #    (defensive against misplaced files)
    feature_dir = paths.repo_root / "specs" / spec_id
    spec_file = feature_dir / "spec.md"
    if spec_file.exists():
        first_line = spec_file.read_text().split("\n", 1)[0]
        if re.match(r"^# Spec-Lite SL-\d{3}", first_line):
            return True

    return False
```

### Parameters

- `paths`: the `MatriarchPaths` instance for the current
  repository (provides `paths.repo_root` as the repo root; paths
  are derived as `paths.repo_root / ".specify" / "orca" / ...`
  and `paths.repo_root / "specs" / ...`)
- `spec_id`: the raw identifier the operator passed to lane
  registration (e.g., `SL-001-my-feature` or just `SL-001`)

### Return value

`True` if `spec_id` resolves to a spec-lite record by any of
the three detection methods. `False` otherwise.

## Guard placement

```python
def register_lane(*, spec_id: str, ...) -> LaneRecord:
    if _is_spec_lite_record(paths, spec_id):
        raise MatriarchError(
            f"Cannot register lane for spec-lite record {spec_id!r}. "
            f"Spec-lite does not participate in matriarch lanes in v1. "
            f"Spec-lite is a reference-only shape; if you need lane "
            f"coordination, hand-author a full spec under specs/ and "
            f"register that instead. The spec-lite record can be used "
            f"as reference content when drafting the full spec."
        )
    spec_path = _feature_dir(paths, spec_id)
    ...
```

The guard fires **before** `_feature_dir`. This is load-bearing:
`_feature_dir` does not know about `.specify/orca/spec-lite/` and
would either fail or return a wrong path for spec-lite IDs.

## Error shape

The error message MUST:

1. Name the rejected `spec_id`
2. State that spec-lite does not participate in lanes "in v1"
   (leaves room for future relaxation without a contract change)
3. Direct the operator to hand-author a full spec under `specs/`
4. Note that the spec-lite record can be used as reference content

The error is a `MatriarchError` — the same exception type used
for other lane-registration failures (e.g., missing spec, invalid
spec_id). Callers that catch `MatriarchError` will handle this
case uniformly.

## Invariants

- No matriarch lane ever references a spec-lite record as its
  anchor
- The guard fires for ALL spec-lite records regardless of their
  `Status` field (`open`, `implemented`, `abandoned`)
- The guard fires before `_feature_dir` resolves (ordering is
  load-bearing)
- The guard does NOT fire for full specs under `specs/` — a full
  spec that happens to cite a spec-lite by ID in its body is
  perfectly valid as a lane anchor

## Testing

Tests live in the existing `tests/test_matriarch.py`:

- **Guard fires**: create a spec-lite record at
  `.specify/orca/spec-lite/SL-001-test.md`, call `register_lane`
  with `spec_id="SL-001-test"`, assert `MatriarchError` with the
  expected message substring
- **Guard does not misfire**: create a full spec at
  `specs/020-test/spec.md`, call `register_lane` with
  `spec_id="020-test"`, assert lane creation succeeds
- **Guard catches ID-only input**: call `register_lane` with
  `spec_id="SL-001"` (no slug), assert `MatriarchError`
- **Guard catches misplaced file**: create a file at
  `specs/SL-001-test/spec.md` with a `# Spec-Lite SL-001:` header,
  assert `MatriarchError` via header-scan fallback

## Supersedes

This guard is new in 013. It does not supersede an existing
contract, but it constrains `matriarch.py`'s `register_lane`
function by adding a precondition check that did not exist before.
