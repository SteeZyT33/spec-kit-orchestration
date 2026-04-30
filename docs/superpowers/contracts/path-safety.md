# Path-Safety Contract

**Status:** Active contract for all orca capabilities and plugins that accept path arguments
**Origin:** Lifted and generalized from Symphony SPEC §9.5 (2026-04-28); adapted to orca's path universe
**Audience:** Orca capability authors, plugin authors (slash commands, perf-lab skills), CLI maintainers

## Why this contract exists

Orca capabilities and the plugins that wrap them (`/orca:review-spec`, `perf-cite`, etc.) accept many path-shaped arguments: `--content-path`, `--evidence-path`, `--target`, `--findings-file`, `--reference-set`, `--feature-id`, plus implicit paths discovered from feature dirs. Symphony's SPEC §9.5 codifies three invariants for its single workspace path. Orca has more path classes and more capabilities; without a shared contract, each capability invents its own validation logic, drifts, and leaves traversal/symlink gaps.

This document is the single source of truth: **every orca capability or plugin that accepts a path-shaped argument MUST validate it against the rules below**, return a typed error on failure, and not pass through unsafe paths to underlying tools (LLMs, shell commands, file reads, etc.).

## Core invariants

The following hold regardless of path class:

1. **Absolute resolution before validation.** Every input path is resolved to an absolute canonical form (Python: `Path(p).resolve(strict=False)`) before any other check. Relative inputs are resolved against the declared root for that path class.
2. **No symlinks in the resolved path.** If any component of the resolved path traverses a symlink, the input is rejected. Use `os.path.realpath` and compare to `os.path.abspath`; mismatch indicates a symlink hop.
3. **Containment in declared root.** The resolved path MUST have the path class's root as a strict prefix (component-wise, not string-prefix — `/shared/orca` is NOT a prefix of `/shared/orca-evil`).
4. **Type matches contract.** A flag declared "regular file" rejects directories, devices, sockets, FIFOs, and broken symlinks. A flag declared "directory" rejects regular files. A flag that accepts either MUST document so explicitly.
5. **Identifier sanitization.** String inputs that become path components (`claim_id`, `feature_id`, `lane_id`, `round_id`) MUST match `[A-Za-z0-9._-]+` and MUST NOT equal `.` or `..`. Reject empty strings.
6. **Defense-in-depth, not blocklist.** Validation is whitelist-based: accept only what matches the rule for the path class. Blocklisting `..` or specific bad strings is insufficient.

These invariants apply at the boundary where input enters orca (CLI argparse handlers, Python library function entry points, plugin wrapper scripts). Internal helpers that operate on already-validated paths do not re-validate.

## Path classes

Orca distinguishes four path classes. Each has its own root and rules.

### Class A: repo paths (in-repo, in-session use)

**Roots:** the user's git repository root (`git rev-parse --show-toplevel`) OR a feature directory resolved via `host_layout.resolve_feature_dir(feature_id)` per the host repo's adoption manifest. The manifest's `host.system` determines the convention: spec-kit (`<repo>/specs/<feature-id>/`), openspec (`<repo>/openspec/changes/<feature-id>/`), superpowers (`<repo>/docs/superpowers/specs/<feature-id>/`), or bare (`<repo>/docs/orca-specs/<feature-id>/`). See `docs/superpowers/specs/2026-04-29-orca-spec-015-brownfield-adoption-design.md`.

**Used by:** Phase 4a slash commands (`/orca:review-spec`, `/orca:review-code`, `/orca:review-pr`), citation-validator's `--reference-set`, contradiction-detector when invoked from in-repo flows.

**Rules:**
- Resolved path MUST be inside the declared root.
- Symlinks rejected anywhere in the resolved path.
- Regular files only unless the flag explicitly accepts directories (e.g., `--reference-set` for citation-validator accepts dirs and walks them with depth limits).
- For `--reference-set` directories, walk depth is capped (default 3) to prevent traversal of large nested trees.

### Class B: shared paths (perf-lab devcontainer)

**Root:** `/shared/` (or `$SHARED_ROOT` if explicitly set in env).

**Used by:** Phase 4b perf-lab skills (`perf-cite`, `perf-contradict`, `perf-review`), and any capability invoked from inside a perf-lab devcontainer.

**Rules:**
- Resolved path MUST be inside `/shared/`.
- Symlinks rejected.
- Regular files for `--content-path` and `--evidence-path` (no directories — directories enable traversal patterns inside untrusted content trees).
- `--target` (cross-agent-review) accepts files OR directories; directory inputs are walked with depth cap 3.
- Reading from `/shared/orca/` (orca's per-claim subdirectory) requires the calling skill's `CLAIM_ID` env to match the second path segment (`<root>/orca/<CLAIM_ID>/...`); cross-claim reads are rejected.

### Class C: findings-file paths

**Roots:** Phase 4a writes findings to `<feature-dir>/.<command>-<reviewer>-findings.json` (in-repo); Phase 4b writes to `/shared/orca/<claim_id>/<round_id>/<kind>-findings-<timestamp>.json` (perf-lab).

**Used by:** `--claude-findings-file` and `--codex-findings-file` flags on `cross-agent-review` and (per Phase 4b prerequisites) `contradiction-detector`.

**Rules:**
- Resolved path MUST be inside the appropriate root for the calling context.
- Regular file required (writable by host LLM in advance; read-only consumed by orca).
- File MUST be non-empty and parse as JSON via `parse-subagent-response`'s schema. Empty or unparseable files return `Err(INPUT_INVALID)` with `kind = "MISSING_FINDINGS_FILE"` or `"MALFORMED_FINDINGS_FILE"`.
- Symlinks rejected (host LLM should write directly to the canonical path).

### Class D: identifier strings (not raw paths, but become paths)

**Examples:** `--feature-id`, `--claim-id`, `--lane-id`, `--round-id` (where applicable).

**Rules:**
- Match `[A-Za-z0-9._-]+`.
- Reject `.`, `..`, empty, or strings that begin with `-` (avoids argparse confusion).
- Maximum length 128 characters.
- Used only as path components after sanitization; never interpolated into shell commands.

## Validation rules per flag

The following matrix is normative. Capability authors adding new path-shaped flags MUST extend this table (or document the flag's validation rules in the capability's contract doc and link back here).

| Flag | Class | Type | Notes |
|------|-------|------|-------|
| `--content-path` | A or B (context-dependent) | regular file | symlinks rejected; size cap 10 MB |
| `--evidence-path` | A or B | regular file (NOT directory) | repeatable; each entry validated; size cap 10 MB per file |
| `--target` (cross-agent-review) | A or B | regular file OR directory | directory walk depth cap 3 |
| `--reference-set` | A or B | regular file OR directory | repeatable; directory walk depth cap 3 |
| `--findings-file` | C | regular file | non-empty; JSON parses; correct schema |
| `--claude-findings-file` | C | regular file | same as `--findings-file` |
| `--codex-findings-file` | C | regular file | same as `--findings-file` |
| `--feature-id` | D | identifier | `[A-Za-z0-9._-]+`, max 128 |
| `--claim-id` (perf-lab) | D | identifier | `[A-Za-z0-9._-]+`, max 128 |

Default size caps for files (10 MB per file, 100 MB aggregate per invocation) prevent accidental denial-of-service via large inputs. Capabilities MAY raise caps with explicit documentation.

## Error reporting

All path-validation failures return a `Result.Err` with the following payload shape:

```json
{
  "kind": "INPUT_INVALID",
  "message": "human-readable specific reason",
  "field": "--content-path",
  "value_redacted": "/shared/path/that/failed",
  "rule_violated": "symlink_in_resolved_path | path_outside_root | not_a_regular_file | identifier_format | size_cap_exceeded | malformed_findings_file | missing_findings_file"
}
```

Constraints:
- `kind` is always `"INPUT_INVALID"` for path validation; this distinguishes config errors from `BACKEND_FAILURE` (LLM call broke) or `INTERNAL_ERROR` (orca bug).
- `message` is one specific sentence describing the violation. NOT generic ("invalid path") — name the rule.
- `field` names the CLI flag or function parameter that failed.
- `value_redacted` echoes the input so operators can debug, with sensitive components scrubbed (e.g., temp filenames preserved, but absolute paths inside `$HOME` may be relativized at the capability author's discretion).
- `rule_violated` is one of the enumerated values above; new rules require a docs PR adding to this list.

CLI behavior on `INPUT_INVALID`: exit code 2, JSON envelope on stdout, human-readable summary on stderr. Never exit 0; never let the input proceed to the LLM or shell.

## Adoption pattern for new capabilities

A capability that adds a new path-shaped flag MUST:

1. **Cite this contract** in the capability's docs (`docs/capabilities/<name>/contract.md` or equivalent): "Path-shaped flags follow `docs/superpowers/contracts/path-safety.md`."
2. **Map the flag to a path class** (A/B/C/D) explicitly in the capability's CLI argparse layer.
3. **Add the flag to the matrix above** in this contract document.
4. **Implement validation at the entry point** — argparse handler for CLI, function entry for library — using a shared helper (preferred) or inline checks that match the rules.
5. **Add path-safety smoke tests** to the capability's test suite covering at minimum:
   - symlink rejection (create a symlink → flag rejects it)
   - root containment violation (path outside root → rejected)
   - type mismatch (directory passed to file-only flag → rejected)
   - identifier format (bad `feature_id` → rejected)
   - size cap (oversized file → rejected)

A shared helper module (`orca.core.path_safety`) is the recommended implementation surface; today each capability implements its own checks, and consolidating them is a tracked refactor (see "Implementation status" below).

## Implementation status (as of 2026-04-29)

- **Phase 4a**: `cross-agent-review` and the slash commands implement most of these rules ad-hoc — symlinks rejected, root containment checked. Not consolidated into a shared module.
- **Phase 4b spec (v2)**: explicitly cites this contract for `perf-cite`, `perf-contradict`, `perf-review`. Implementation will use shared helpers when consolidated.
- **citation-validator, contradiction-detector, worktree-overlap-check**: have inconsistent path validation today. Tracked as a follow-up: build `orca.core.path_safety` and refactor capabilities to use it. Until then, each capability MUST satisfy this contract independently.

## Why these invariants (rationale)

1. **Symlinks.** A symlink inside `/shared/` could point anywhere on the devcontainer filesystem. If an attacker (or a buggy upstream) writes a symlink under `/shared/`, an unguarded read could exfiltrate `/etc/passwd` or write findings to `/proc/self/...`. Rejecting symlinks at the orca boundary closes the class.
2. **Root containment.** Component-wise prefix check (not string prefix) prevents the `/shared/orca-evil` vs `/shared/orca/` confusion. `Path.is_relative_to()` in Python 3.9+ does this correctly.
3. **Type checks.** Many file-handling tools behave subtly differently on directories vs files vs FIFOs. Locking down at the orca boundary means downstream tools see only what they expect.
4. **Identifier sanitization.** Identifiers become path components or LLM prompt substrings. Path traversal via `../` in a `feature-id` is the obvious risk; LLM prompt injection via shell metacharacters in a `claim-id` is subtler but real.
5. **Size caps.** A 10 GB `--content-path` would tie up the LLM context, the orca process memory, and the host. Capping at the boundary forces explicit per-capability override when genuinely needed.

## Cross-references

- **Phase 4a design** (`docs/superpowers/specs/2026-04-28-orca-phase-4a-in-session-reviewer-design.md`) — established the file-backed reviewer pattern that path Class C codifies.
- **Phase 4b v2 design** (`docs/superpowers/specs/2026-04-28-orca-phase-4b-perf-lab-integration-design.md`) — references this contract for `/shared/`-class paths.
- **See also:** `docs/superpowers/contracts/dispatch-algorithm.md` — the host-side subagent-dispatch contract that consumes Class C findings-file paths and defines the sentinel shape returned on dispatch failure.
- **Symphony SPEC §9.5** (`~/symphony/SPEC.md`) — the original three-invariant statement adapted here.
- **v1 north-star** (`docs/superpowers/specs/2026-04-26-orca-toolchest-v1-design.md`) § "Composition with Outer-Loop Runtimes" — explains why this contract exists (consistent behavior across outer-loop runtimes).
