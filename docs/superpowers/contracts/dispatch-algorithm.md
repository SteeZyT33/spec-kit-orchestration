# Subagent-Dispatch Algorithm Contract

**Status:** Active contract for any host-side runtime that dispatches subagents to produce an orca findings file
**Origin:** Adapted from Symphony SPEC §10.6 (host-side dispatch with stall detection); generalized for orca's multi-runtime consumer set
**Audience:** Perf-lab dispatch wrapper authors (bash), Claude Code slash command authors, Codex host integrators, and any future runtime that drives an orca file-backed reviewer

## Why this contract exists

Orca's file-backed reviewer pattern (Phase 4a) splits responsibilities cleanly: the **host runtime** dispatches a subagent, captures its response, parses it via `orca-cli parse-subagent-response`, and writes a findings file at a path that orca's path-safety contract Class C declares. Orca then reads that file and runs its own logic.

The dispatch step lives outside orca. Each consumer reimplements it in its own runtime:

- **Perf-lab** uses bash wrappers (`scripts/perf-lab/orca-dispatch-{contradict,review}.sh`) sourcing a shared `orca-dispatch-lib.sh`. Phase 4b's T0Z06 ships these.
- **Claude Code slash commands** (`plugins/claude-code/commands/review-spec.md`, `review-code.md`, `review-pr.md`) dispatch via the harness's Agent tool. Phase 4a shipped these without explicit stall detection; this contract motivates a future tightening.
- **Codex hosts** drive subagents via the app-server protocol with per-turn timeouts.

There is no shared cross-repo bash helper. Each runtime implements the loop natively against this spec. Without a shared algorithm spec, each consumer would invent its own timeout, sentinel format, and error vocabulary, and orca's downstream skills would have to detect N variants of "the dispatch failed."

This contract is the single source of truth for: when to time out, what JSON to write on failure, what the reserved error.kind values are, and where the findings file lands.

## Inputs

A dispatch invocation receives:

| Input | Source | Notes |
|-------|--------|-------|
| `prompt` | `orca-cli build-review-prompt --kind <kind> --criteria <c1> --criteria <c2> ...` | Free-text; consumers MUST NOT mutate before passing to the subagent. |
| `harness` | Env or wrapper-arg (`HARNESS=claude-code \| codex`) | Determines dispatch mechanics; does not change the contract output. |
| `claim_id` and `round_id` (perf-lab) OR `feature_dir` (in-repo) | Wrapper args / slash-command frontmatter | Used only to compute the findings-file path per path-safety Class C. |
| `criteria` | List of strings | Already embedded in the prompt; carried through for telemetry only. |
| `target_path` | Wrapper arg / slash-command argument | The content the subagent reviews. Must already be path-safety-validated by the caller. |
| `findings_file_path` | Computed (see below) | The exact filesystem location the dispatch loop writes to. |

The dispatch wrapper does NOT validate paths itself; it assumes the caller (perf-lab skill or slash command) has already enforced path-safety. The dispatch wrapper's only path-touching responsibility is writing to `findings_file_path` exactly once.

## Outputs

A single regular file at `findings_file_path` containing one of two shapes:

1. **Success:** A JSON array of finding objects, as defined by `orca-cli parse-subagent-response` and consumed by orca's reviewers. The dispatch wrapper does not invent this shape; it pipes the subagent's response through `parse-subagent-response`, which validates and normalizes.
2. **Failure (sentinel):** A single JSON object with `ok: false` and an `error` block. See "Sentinel format" below.

**Same-path invariant.** The dispatch wrapper writes exactly one file at `findings_file_path`, regardless of whether the dispatch succeeded or hit a sentinel-producing failure mode. Consumers MUST read from this single path; they MUST NOT look for `<path>.error.json` or any sibling file. The two possible shapes (success findings array vs `{ok: false, error: {...}}` sentinel) are distinguished by parsing the JSON and checking for the `ok` key.

The findings-file path itself is governed by `path-safety.md` Class C; the dispatch wrapper does not duplicate those rules. In particular:

- Perf-lab dispatches write under `/shared/orca/<claim_id>/<round_id>/...` (Class C, perf-lab variant).
- In-repo slash commands write under `<feature-dir>/.<command>-<reviewer>-findings.json` (Class C, in-repo variant).

Consumers that read the findings file (orca's `cross-agent-review`, `contradiction-detector`) detect the sentinel by parsing JSON and checking `ok === false`. They translate sentinel `error.kind` values into orca's standard `INPUT_INVALID` error envelope per the mapping in "Sentinel format" below.

## Algorithm

Pseudocode. Consumers translate to their runtime; semantics are normative.

**Atomic-write rule (all runtimes).** Every write to `findings_file_path` — success array or sentinel — MUST go through a write-then-rename: write to `<findings_file_path>.partial`, then atomically rename to `findings_file_path`. Consumers reading mid-write would otherwise observe truncated JSON. This applies to bash, Codex, Claude Code, and any future host equally.

**Keepalive handling.** Any non-null event, including zero-byte keepalives, resets `last_event_at`. Only genuine silence (no events for the stall window) triggers `DISPATCH_STALL`.

```text
function dispatch_subagent(prompt, target_content, findings_file_path):
    # 1. Path is precomputed by caller per path-safety Class C. Do not re-validate.

    # 2. Parameters from environment (with defaults).
    stall_timeout_s  = env("ORCA_DISPATCH_STALL_TIMEOUT", default=300)
    hard_timeout_s   = env("ORCA_DISPATCH_HARD_TIMEOUT", default=600)

    # 3. Start the subagent. The exact mechanism is runtime-specific
    #    (Agent tool call, app-server turn, bash subprocess); the contract
    #    requires only that the runtime can: (a) read events as they arrive,
    #    (b) kill the subagent on demand.
    dispatch_start = monotonic_now()
    last_event_at  = dispatch_start
    subagent       = start_subagent(prompt=prompt, content=target_content)

    response_buffer = ""
    while subagent.is_alive():
        # 4. Watchdog tick. Implementations sleep ~1s between checks; do not
        #    busy-loop. Bash uses a separate watchdog process; Codex uses its
        #    per-turn stall_timeout_ms; Claude Code Agent tool plumbs both
        #    timeouts through the harness call.
        event = subagent.poll(timeout_ms=1000)

        if event is not None:
            last_event_at = monotonic_now()
            response_buffer += event.payload

        # 5. Stall detection.
        if monotonic_now() - last_event_at > stall_timeout_s:
            subagent.kill()
            elapsed = round(monotonic_now() - dispatch_start)
            write_sentinel(findings_file_path, kind="DISPATCH_STALL",
                           elapsed_seconds=elapsed)
            return

        # 6. Hard timeout.
        if monotonic_now() - dispatch_start > hard_timeout_s:
            subagent.kill()
            elapsed = round(monotonic_now() - dispatch_start)
            write_sentinel(findings_file_path, kind="DISPATCH_TIMEOUT",
                           elapsed_seconds=elapsed)
            return

    # 7. Subagent terminated normally. Parse and write.
    parse_result = run("orca-cli parse-subagent-response",
                       stdin=response_buffer,
                       outfile=findings_file_path)
    if parse_result.exit_code != 0:
        elapsed = round(monotonic_now() - dispatch_start)
        truncated = response_buffer[:2048]
        write_sentinel(findings_file_path, kind="PARSE_FAILURE",
                       elapsed_seconds=elapsed,
                       raw_truncated=truncated)
        return

    # 8. Success path: parse-subagent-response wrote the findings array
    #    directly to findings_file_path. No further action.
    return
```

The `MISSING_AGENT_TOOL` sentinel is written when a host runtime detects, before step 3, that no Agent-tool equivalent is available. This is the Codex case where the app-server tool injection has not been configured for the current session. The wrapper writes the sentinel and returns without starting a subagent.

Implementations MAY add additional pre-flight checks (e.g., subagent binary missing, network unreachable). These map onto existing reserved kinds where possible (`MISSING_AGENT_TOOL` for "no dispatcher available") or surface as runtime-native errors that the caller catches and converts into a sentinel before returning. New `error.kind` values require a docs PR amending this contract.

## Sentinel format

A sentinel findings file is a single JSON object (NOT an array). Field rules (normative):

- `ok` MUST be the literal boolean `false`. Consumers detect sentinels by `ok === false`.
- `error.kind` MUST be one of the four reserved values listed below. Producers MUST emit one of the four reserved values. Consumers SHOULD log unknown values for forward compatibility (in case a future docs PR adds a fifth kind), but the producer side is a closed enum and adding new kinds requires this contract to be amended first.
- `error.elapsed_seconds` is a non-negative integer (seconds since dispatch start, rounded). Required for `DISPATCH_STALL`, `DISPATCH_TIMEOUT`, and `PARSE_FAILURE`; absent for `MISSING_AGENT_TOOL` (the failure happens before dispatch starts, so elapsed time is meaningless).
- `error.raw_truncated` (field renamed from `raw` in the original draft to make the size cap visible at point of use) is OPTIONAL and used only by `PARSE_FAILURE`. Truncate to the first 2048 UTF-8 codepoints. If a codepoint is split mid-encoding at the cap, drop that codepoint to ensure the result is valid UTF-8. Do NOT append a truncation marker (`...` or similar) — consumers detect truncation by the field's presence rather than its content. Producers MUST NOT pass `raw_truncated` content to LLMs (it is operator debugging only).

Reserved `error.kind` values (closed enum; new values require a docs PR):

| Kind | Trigger | Required fields |
|------|---------|-----------------|
| `DISPATCH_STALL` | `now - last_event_at > stall_timeout` | `kind`, `elapsed_seconds` |
| `DISPATCH_TIMEOUT` | `now - dispatch_start > hard_timeout` | `kind`, `elapsed_seconds` |
| `PARSE_FAILURE` | `parse-subagent-response` exited non-zero | `kind`, `elapsed_seconds`; `raw_truncated` recommended |
| `MISSING_AGENT_TOOL` | Host has no Agent-tool equivalent (e.g., Codex without app-server tool injection) | `kind` |

### Concrete examples (one per kind)

`DISPATCH_STALL`:

```json
{
  "ok": false,
  "error": {
    "kind": "DISPATCH_STALL",
    "elapsed_seconds": 301
  }
}
```

`DISPATCH_TIMEOUT`:

```json
{
  "ok": false,
  "error": {
    "kind": "DISPATCH_TIMEOUT",
    "elapsed_seconds": 600
  }
}
```

`PARSE_FAILURE`:

```json
{
  "ok": false,
  "error": {
    "kind": "PARSE_FAILURE",
    "elapsed_seconds": 47,
    "raw_truncated": "I'll review the spec now.\n\nLooking at section 2..."
  }
}
```

`MISSING_AGENT_TOOL` (note: no `elapsed_seconds`):

```json
{
  "ok": false,
  "error": {
    "kind": "MISSING_AGENT_TOOL"
  }
}
```

### Timeout tuning

The default timeouts (300s stall, 600s hard) come from Symphony's empirical tuning: 300s is long enough that healthy LLM responses on slow models (deep-thinking, large context) do not trip the stall, but short enough that a hung subagent emitting zero events frees the dispatch slot in 5 minutes rather than 10. The hard cap of 600s covers the case where the subagent emits events steadily but never finishes (e.g., a runaway tool-use loop, or a model that emits low-rate keepalive tokens indefinitely). Operators tune via `ORCA_DISPATCH_STALL_TIMEOUT` and `ORCA_DISPATCH_HARD_TIMEOUT`; orca-side capabilities never set these — only the dispatch host does. Both env vars accept integer seconds. Values below 30 or above 3600 MUST be rejected with a startup error. Clamping silently violates operator intent and is forbidden.

### Mapping to orca's `INPUT_INVALID` envelope

Consumers reading a sentinel translate it into orca's `INPUT_INVALID` envelope per the path-safety contract. Path-safety's `rule_violated` enum is closed and does not enumerate dispatch-failure kinds; therefore:

- Sentinel `error.kind` (any of the four) maps to `rule_violated: "malformed_findings_file"`.
- The original sentinel `error.kind` value is preserved in the envelope's `message` field (e.g., `"DISPATCH_STALL after 312s"`).
- Sentinel `error.elapsed_seconds`, when present, is included in the message.
- Sentinel `error.raw_truncated`, when present, is logged at debug level and surfaced via `value_redacted` in the orca envelope so operators can debug the upstream parser failure without re-running the subagent.
- The orca capability returns exit 1 with the standard envelope; it does not exit 2 (path-safety reserves exit 2 for pre-flight path errors, which sentinels are not).

This keeps path-safety's `rule_violated` enum closed while preserving the dispatch-side detail in the message.

A worked example: perf-lab's `orca-dispatch-contradict.sh` invokes a subagent that hangs waiting for a tool response. After 300s the watchdog kills the subagent and writes the `DISPATCH_STALL` JSON above to `/shared/orca/claim-42/round-3/contradict-findings-2026-04-29T12-00-00Z.json`. Perf-lab's `perf-contradict` skill, which is waiting on that file, reads it, sees `ok: false`, and propagates the error to its own envelope. Orca itself never observes the stall directly; the dispatch wrapper is the single point of failure handling.

## Implementation notes

### Bash (perf-lab wrappers)

The shared library is `scripts/perf-lab/orca-dispatch-lib.sh`, sourced by `orca-dispatch-contradict.sh` and `orca-dispatch-review.sh`. Caveats:

- **Hard cap vs stall detection.** Use `timeout(1)` (or your shell's equivalent) for the hard cap (`ORCA_DISPATCH_HARD_TIMEOUT`). Implement stall detection as a parallel watchdog — `timeout(1)` cannot detect inter-event silence, only wallclock elapsed. The watchdog: main process runs the subagent and writes each event to a file (or named pipe); a sibling `sleep 1` loop checks `stat -c %Y <event-file>` and `kill -TERM`s the subagent PID when `now - mtime > stall_timeout`.
- **Signal handling.** Use `trap` to ensure the watchdog dies when the main wrapper exits, even on normal completion. Without this, an orphaned watchdog can outlive the dispatch and confuse subsequent runs.
- **PID groups.** Subagents may spawn children. Track the dispatch as its own process group (`setsid`) and signal the group on stall to ensure children die too.

### Claude Code slash commands

Phase 4a's commands (`review-spec.md`, `review-code.md`, `review-pr.md`) dispatch subagents via the harness's Agent tool inline, without explicit stall detection (as of 2026-04-29). They rely on the harness's own timeout (configurable per session, but not per-dispatch). This contract motivates a future enhancement: each command should plumb the two timeouts through to the Agent tool call, and on harness-detected timeout write the sentinel to the same path it would have written the findings to.

The implementation outline for slash commands:

1. Compute `findings_file_path` from frontmatter (feature dir + reviewer name) per path-safety Class C.
2. Call the Agent tool with the prompt; the harness handles streaming.
3. On harness timeout or subagent error, the slash command's bash post-step (the part that calls `orca-cli parse-subagent-response`) detects the missing or empty response and writes the appropriate sentinel.
4. Until the harness exposes per-call stall/hard timeouts, slash commands rely on session-level defaults; this is acceptable for in-repo interactive use where an operator can intervene, but unacceptable for unattended perf-lab runs (which is why perf-lab uses bash wrappers, not slash commands).

### Codex hosts

The Codex app-server protocol exposes a per-turn `stall_timeout_ms`. Set it to `ORCA_DISPATCH_STALL_TIMEOUT * 1000` (default 300000). The app-server raises a stall event when no model output arrives within the window; the dispatch wrapper catches that event and writes the `DISPATCH_STALL` sentinel. The hard timeout is enforced by a wrapper-side wallclock check around the turn, since the app-server protocol does not currently expose a hard turn cap separate from stall.

When the Codex session lacks the Agent-tool equivalent (app-server tool injection not configured), the wrapper detects this at startup (the tool list does not include the dispatcher) and writes a `MISSING_AGENT_TOOL` sentinel without attempting the turn. This is the only `error.kind` that fires before any subagent work begins.

## Cross-references

- **Symphony SPEC §10.6** (`~/symphony/SPEC.md`) — the original host-side dispatch + stall-detection contract this document generalizes. Symphony's 300s default and event-monitoring loop are reused verbatim.
- **Path-safety contract** (`docs/superpowers/contracts/path-safety.md` § "Class C") — defines the `findings_file_path` shape and validation rules for both perf-lab (`/shared/orca/<claim_id>/<round_id>/...`) and in-repo (`<feature-dir>/.<command>-<reviewer>-findings.json`) variants. This contract delegates path computation entirely to path-safety.
- **Phase 4a parse-subagent-response capability** — reads the subagent's raw response and writes the validated findings array. Failure to parse triggers the `PARSE_FAILURE` sentinel; the dispatch wrapper does not implement parsing logic itself.
- **Phase 4b spec** (`docs/superpowers/specs/2026-04-28-orca-phase-4b-perf-lab-integration-design.md` § "Stall detection on subagent dispatch") — the design that introduced this contract as a Phase 4b prerequisite. The spec also covers the perf-lab T0Z06 task that implements `orca-dispatch-lib.sh` against this algorithm.
- **Phase 4a slash commands** (`plugins/claude-code/commands/review-spec.md`, `review-code.md`, `review-pr.md`) — current consumers without explicit stall enforcement; this contract motivates the future tightening described under "Claude Code slash commands" above.
