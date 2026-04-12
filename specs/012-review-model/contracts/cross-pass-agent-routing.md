# Contract: Cross-Pass Agent Routing Policy

**Status**: Draft
**Parent**: [012-review-model plan.md](../plan.md)
**Binds**: `src/speckit_orca/matriarch.py` (runtime enforcement),
`commands/review-*.md` (prompt rendering), and `src/speckit_orca/yolo.py`
(014 runtime, which calls into matriarch for cross-pass agent selection)

---

Defines the policy for selecting which agent runs a cross-pass
review. This contract is the source of truth for cross-pass
routing; neither the command prompts nor the yolo runtime define
their own policy.

## Policy (from 012 brainstorm question 3, user answer)

### Rule 1 — Always a different agent

The cross-pass agent MUST NOT be the same as the agent that
authored the artifact being reviewed.

- For `review-spec`: the author agent is whichever agent wrote
  the spec being reviewed. Usually recorded in the spec's
  frontmatter or derivable from git blame on the latest spec
  edit. Fallback: the agent that completed the most recent
  `speckit.clarify` session.
- For `review-code`: the author agent is the self-pass agent in
  the matching phase subsection. E.g., a `## US1 Cross Pass` cannot
  run with the same agent as the `## US1 Self Pass`.

### Rule 2 — Prefer highest-tier agents

Agent tiers are defined in `003-cross-review-agent-selection` and
implemented in `scripts/bash/crossreview-backend.py`'s
`AGENT_SPECS` table:

- **Tier 1** (preferred): `codex`, `claude`, `gemini`, `opencode`
  — marked `auto_selectable=True` in the backend
- **Tier 2** (fallback): `cursor-agent` — marked
  `auto_selectable=False` in the backend's general selection logic,
  but **eligible for automatic fallback in cross-pass routing
  specifically**. The 012 cross-pass routing policy overrides the
  backend's general `auto_selectable` flag for the narrow case of
  timeout-downgrade fallback: when all Tier-1 agents are
  exhausted (author, unavailable, or timed out), the policy
  automatically falls through to Tier 2 without requiring operator
  intervention. Outside of cross-pass routing, Tier-2 agents still
  require manual selection per the backend's default behavior.
- **Tier 3** (last resort): any other agent registered in the
  cross-review backend

Selection walks Tier 1 first, excludes the author agent, and
picks the first available Tier-1 agent. If no eligible Tier-1
agent remains (all are the author, timed out, or unavailable),
Tier 2 is checked next (automatic in cross-pass routing). Tier 3
is a last resort.

### Rule 3 — Downgrade only on timeout

The selected agent runs the cross-pass. If it **times out**, the
policy triggers a downgrade:

1. Record the timeout using the heading format required by the
   artifact kind:
   - For `review-spec`: `## Cross Pass (agent: <timed-out-agent>, date: YYYY-MM-DD)`
   - For `review-code`: `## <phase> Cross Pass (agent: <timed-out-agent>, date: YYYY-MM-DD)` in the same phase subsection as the attempted cross-pass
   The body MUST indicate `TIMEOUT: review did not complete within runtime budget`.
2. Walk the tier list again, excluding both the author agent and
   the timed-out agent
3. Run the cross-pass with the next-highest tier's first available agent
4. Record the retry as a new cross-pass entry in the same artifact,
   again using the artifact's required heading format (`## Cross
   Pass` for `review-spec`; `## <phase> Cross Pass` for `review-code`)

**Downgrade only fires on timeout**, not on content disagreement,
not on low-quality output, not on any other failure mode. A
non-timeout failure (e.g., agent unavailable, API error) fails the
review explicitly — see Rule 4.

### Rule 4 — No same-agent fallback

If all tiers are exhausted or unavailable or time out, the review
**fails explicitly** with a clear error. The policy does NOT fall
back to running the cross-pass with the author agent.

Rationale: a same-agent cross-pass is indistinguishable from a
self-pass and provides no adversarial value. Exposing "your review
just ran with the same agent that wrote the code" to the operator
is more valuable than silently completing a worthless pass.

Error message shape (enforced by matriarch):

```text
cross-pass failed: no different-agent alternative available for
<artifact-path>. Author agent: <author>. Excluded: [<timed-out
agents>]. Tried: [<tier-1-attempts>, <tier-2-attempts>, <tier-3-attempts>].
No fallback to same-agent pass because adversarial review requires
a different agent. Reschedule or configure a different agent for
this repo.
```

### Rule 5 — No operator override at command level

Operators do NOT pass `--agent codex` or similar flags to review
commands. Routing is **deterministic** based on author-agent
exclusion and tier preference. If an operator needs a specific
agent, they must change the **author** agent upstream (e.g., by
running the implement phase with a different agent) rather than
override at review time.

This rule is the resolution of 012 brainstorm question 3's explicit
"no explicit override" answer from the user.

## Enforcement

### Matriarch runtime (`src/speckit_orca/matriarch.py`)

Matriarch is the **authority** that implements this policy. It
exports a function:

```python
def select_cross_pass_agent(
    *,
    author_agent: str,
    timed_out_agents: list[str] | None = None,
    repo_root: Path | None = None,
) -> str:
    """Select the cross-pass agent per 012's routing policy.

    Raises MatriarchError if no eligible agent is available.
    """
```

Parameters:

- `author_agent`: the agent that authored the artifact under review
- `timed_out_agents`: list of agents already tried in this review
  cycle that timed out (starts empty, grows on each downgrade)
- `repo_root`: optional, for reading per-repo agent availability

Returns the selected agent's identifier (`codex`, `claude`, etc.).
Raises `MatriarchError` if no eligible agent exists.

### Command prompts (future, deferred)

When `commands/review-code.md` and `commands/review-spec.md` are
written in the deferred prompt-rewrite task, they call into
matriarch's `select_cross_pass_agent` to determine which agent
runs the cross-pass. They do **not** implement their own routing.

### Yolo runtime (014)

014's runtime calls `matriarch.select_cross_pass_agent` when
advancing into a review stage that requires a cross-pass. The yolo
runtime records the selected agent in its event log and in the
review artifact. Retries on timeout go back through the same
matriarch call with an updated `timed_out_agents` list.

### Cross-review backend (`scripts/bash/crossreview-backend.py`)

The existing cross-review backend already knows about agent tiers
from `003-cross-review-agent-selection`. This contract REUSES 003's
tier model without redefining it. If 003's tier list changes
upstream, this contract automatically inherits the change.

## Configuration

### Per-repo agent availability

Some agents may not be available in all repos (e.g., a repo might
not have cursor-agent installed). Availability is determined by
the cross-review backend's existing logic, which checks:

1. Agent CLI is on PATH
2. Agent is not in the repo's exclusion list (TBD future feature)
3. Agent returned a successful health check recently (if
   supported)

Matriarch's `select_cross_pass_agent` respects the availability
check. Unavailable agents are skipped as if they were Tier 3 or
lower.

### Timeout budget

The cross-pass timeout budget is not defined in this contract; it
is a runtime configuration managed by the cross-review backend
(`crossreview-backend.py`'s `--timeout` flag or per-repo config).

**Defaults today** (observed, not authoritative):
- `crossreview-backend.py` CLI default: `--timeout 600` (600s)
- `crossreview.sh` wrapper default: `CROSSREVIEW_TIMEOUT=300`
  (300s) which gets passed to the backend

In typical usage, the wrapper is the entry point, so the
effective budget is **300s unless overridden**. Operators invoking
the backend directly (or via matriarch) get 600s. A future
harmonization pass should pick one canonical default; for now,
012 runtime code MUST pass an explicit timeout rather than rely
on implicit defaults.

A future per-repo config may override this per tier (e.g., Tier 1
gets 900s, Tier 2 gets 600s, Tier 3 gets 300s) but that is NOT in
012 scope.

## Interaction with 003 cross-review agent selection

This contract **reuses 003's tier model and routing backend**. It
ADDS:

- The explicit "highest tier first, downgrade on timeout" preference
  (003 did not specify a preference)
- The "no same-agent fallback" rule (003 allowed fallback in some cases)
- The recording of retries as additional cross-pass subsections in
  the review artifact

These additions should be back-ported to 003 as a contract
amendment so the two specs stay aligned. If back-porting is not
done, 012's contract supersedes 003's relevant sections by virtue
of being newer. The 012 implementation wave MUST touch 003's
affected sections explicitly (even if only to add a pointer
note).

## Invariants

- No review artifact ever has a cross-pass with the same agent as
  the author. Timeout-downgrade retries may add multiple cross-pass
  entries, but every attempted and successful cross-pass agent must
  still differ from the author agent
- Within a single cross-pass attempt for a phase, there is at
  most one successful (non-TIMEOUT) cross-pass. Additional
  cross-pass subsections within that same attempt are only for
  timeout-downgrade retries, and only one of them can have a
  non-TIMEOUT body. Separate append-only re-review rounds for the
  same phase (e.g., author fixed a cross-pass finding and requested
  a fresh review) may each record their own successful cross-pass
- `select_cross_pass_agent` is deterministic given
  (author_agent, timed_out_agents, availability) — same inputs
  always produce same output
- If the policy cannot select an agent, it raises an error rather
  than falling back to any alternative

## Testing

Tests for this contract live in `tests/test_matriarch.py`
(augmented during the 012 runtime rewrite) and exercise:

- Happy path: author `claude`, returns `codex`
- Tier 1 downgrade within tier: author `claude`, timed-out `codex`,
  returns `gemini`
- Full Tier 1 downgrade: author `claude`, timed-out `codex` and
  `gemini`, returns `opencode` (also Tier 1)
- Tier 2 fallback: author `claude`, timed-out `codex`, `gemini`,
  and `opencode` (all Tier 1 exhausted), returns `cursor-agent`
- No available: author `claude`, all Tier 1 timed out or
  unavailable, `cursor-agent` unavailable, raises MatriarchError
- Determinism: same inputs, same output across 100 runs
- No same-agent fallback: author `claude`, all other tiers
  unavailable, does NOT return `claude`, raises MatriarchError

## Supersedes

This contract is new in 012. It does not supersede an existing
contract file, but it constrains behavior in
`003-cross-review-agent-selection` via Rules 3-5. The 012
implementation wave MUST update 003 to reference this contract as
the cross-pass-specific routing policy.
