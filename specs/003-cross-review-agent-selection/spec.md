# Feature Specification: Orca Cross-Review Agent Selection

**Feature Branch**: `003-cross-review-agent-selection`  
**Created**: 2026-04-09  
**Status**: Draft  
**Input**: User description: "Expand Orca cross-review to support agent-based reviewer selection with --agent, config migration from harness to agent, opencode support, cursor-agent readiness, support tiers, selection precedence, and review artifact reporting based on the broader provider-agnostic workflow findings from the cc-spex repomix analysis."

## Context

The `cc-spex` repomix analysis made one thing clearer: the real value is not a
pile of one-off commands, but a workflow system where optional capabilities are
made explicit, composable, and durable. Orca's current cross-review flow still
violates that direction because:

- the installer already knows many agent names, but cross-review only supports
  `codex`, `claude`, and `gemini`
- the runtime still thinks in terms of a narrow `harness` field instead of a
  broader agent-selection capability
- users can manually run `opencode`, but Orca cannot use it through the normal
  review path
- adjacent Orca docs still describe cross-review as a three-runner feature even
  though Orca itself is trying to be provider-agnostic

This feature brings cross-review into alignment with the broader Orca direction:
reviewer choice becomes a first-class, explicit, policy-driven workflow
capability rather than a hard-coded special case.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Explicit Reviewer Agent Selection (Priority: P1)

A developer wants to choose the review agent directly when running
`speckit.orca.cross-review`, for example `opencode` for design review or
`claude` for a second opinion on code.

**Why this priority**: This is the minimum useful behavior. Without explicit
agent selection, Orca still cannot use newly supported reviewers reliably.

**Independent Test**: Run cross-review with `--agent <name>` and verify the
requested agent is used, reported, and persisted in the review artifact output.

**Acceptance Scenarios**:

1. **Given** a supported review agent such as `opencode`, **When** the user runs
   `/speckit.orca.cross-review --agent opencode`, **Then** Orca invokes that
   agent through the normal cross-review runtime and reports it as the resolved
   reviewer.
2. **Given** a legacy invocation using `--harness claude`, **When** cross-review
   runs, **Then** Orca accepts it as backward-compatible input while normalizing
   the resolved reviewer as an agent choice.
3. **Given** a supported review run completes, **When** Orca writes review
   output, **Then** the artifact records requested agent, resolved agent, model,
   effort, and selection reason.

---

### User Story 2 - Smart Agent Resolution When None Is Specified (Priority: P1)

A developer runs cross-review without `--agent` and expects Orca to choose a
good reviewer using a stable, explainable policy instead of a hard-coded
fallback.

**Why this priority**: Provider-agnostic orchestration requires predictable
selection behavior, not hidden defaults.

**Independent Test**: Run cross-review without `--agent` in repos with
different installed agents and verify Orca selects according to the documented
precedence order and explains why.

**Acceptance Scenarios**:

1. **Given** `crossreview.agent` is configured, **When** the user omits
   `--agent`, **Then** Orca uses the configured agent.
2. **Given** no explicit agent is provided and multiple supported agents are
   installed, **When** Orca auto-selects a reviewer, **Then** it prefers a
   non-current agent according to the documented tier and precedence rules.
3. **Given** the selection is materially ambiguous, **When** cross-review is
   triggered in a non-interactive workflow, **Then** Orca MUST use a
   deterministic fallback instead of blocking: it chooses the highest-ranked
   installed Tier 1 non-current reviewer and records that fallback in
   `selection_reason`.

---

### User Story 3 - Clear Support Tiers And Honest Failures (Priority: P2)

A developer has many Orca-known agents installed and needs to know which ones
are actually review-capable, which are selectable but not auto-selected, and
which are known but unsupported.

**Why this priority**: Without explicit support tiers, users will assume false
parity across installed agents and lose trust in the review pipeline.

**Independent Test**: Attempt cross-review with supported, best-effort, and
unsupported known agents and verify Orca behaves according to the declared
support matrix.

**Acceptance Scenarios**:

1. **Given** a Tier 1 supported agent, **When** it is selected, **Then** Orca
   runs it through a verified adapter path.
2. **Given** a known but unsupported agent, **When** it is selected,
   **Then** Orca fails with a structured, explicit unsupported-agent result
   rather than pretending review occurred.
3. **Given** a best-effort agent is installed, **When** the user does not
   explicitly request it, **Then** Orca does not auto-select it ahead of Tier 1
   agents.

---

### User Story 4 - Cross-Review Terminology And Artifacts Stay Consistent Across Orca (Priority: P2)

A developer reads Orca docs and review artifacts and needs consistent language
about reviewer choice across `cross-review`, `pr-review`, `self-review`,
configuration, and README documentation.

**Why this priority**: If some places say `harness` and others say `agent`,
Orca will drift into two parallel mental models and confuse users.

**Independent Test**: Review command docs, config docs, and generated review
artifacts after the feature is implemented and verify `agent` is the canonical
term with legacy `harness` handled only as compatibility input.

**Acceptance Scenarios**:

1. **Given** the feature is implemented, **When** a user reads cross-review
   documentation, **Then** `agent` is the canonical selection term.
2. **Given** `pr-review` or `self-review` references cross-review,
   **When** those commands discuss reviewer choice or review friction,
   **Then** they use the same agent-based terminology and expectations.
3. **Given** a review artifact is generated, **When** it is read later,
   **Then** it shows requested agent, resolved agent, and whether the review was
   truly cross-agent or a same-agent fallback.

---

### User Story 5 - New Reviewer Adapters Can Be Added Without Rewriting Selection Policy (Priority: P3)

A maintainer wants to add support for a new reviewer such as `cursor-agent`
without reworking the whole cross-review command each time.

**Why this priority**: The repomix findings point toward composable capability
layers, not repeated hard-coded command rewrites.

**Independent Test**: Add or stub a new adapter entry and verify the command,
config, and selection policy can recognize it without redefining the whole
cross-review workflow.

**Acceptance Scenarios**:

1. **Given** a new adapter such as `cursor-agent` is verified, **When** it is
   added to Orca, **Then** the backend can dispatch it through the same agent
   resolution mechanism rather than a parallel one-off path.
2. **Given** an adapter exists but is not yet trusted for auto-selection,
   **When** Orca resolves a reviewer automatically, **Then** it can remain
   selectable while excluded from auto-pick behavior.
3. **Given** a new adapter is unavailable at runtime, **When** Orca attempts to
   use it, **Then** the failure is reported structurally instead of silently
   degrading.

### Edge Cases

- What happens when `--agent` and legacy `--harness` are both provided? Orca
  MUST give `--agent` precedence and ignore legacy `--harness` for resolution,
  while recording that precedence in the selection reason.
- What happens when the configured agent is installed but matches the active
  provider? Orca MUST warn when the resulting review is no longer truly
  cross-agent.
- What happens when only Tier 2 or unsupported agents are installed? Orca MUST
  either ask the user or fail clearly instead of pretending to have a valid
  default.
- What happens when the most recent successful reviewer is no longer installed?
  Orca MUST ignore stale reviewer memory safely.
- What happens when `opencode` works manually but the Orca adapter fails?
  Orca MUST report that as a runtime failure, not as a completed review.
- What happens when a selected agent has no model override semantics compatible
  with Orca's generic config? Orca MUST either translate the request explicitly
  or reject it clearly.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Orca cross-review MUST accept `--agent <name>` as the canonical
  reviewer selection flag.
- **FR-002**: Orca MUST continue accepting legacy `--harness <name>` input for a
  compatibility window, but MUST normalize reviewer choice internally as an
  agent selection.
- **FR-003**: Orca configuration MUST support `crossreview.agent` as the
  canonical persisted reviewer setting.
- **FR-004**: Orca MUST preserve backward compatibility for legacy
  `crossreview.harness` configuration during the migration window.
- **FR-005**: When no explicit reviewer is provided, Orca MUST resolve a review
  agent using a documented precedence order rather than a hidden hard-coded
  default.
- **FR-006**: Orca MUST support `opencode` as a first-class cross-review agent
  through the normal runtime path, not only through manual invocation.
- **FR-007**: Orca MUST define support tiers for known agents so that
  installer-known agents are not automatically treated as fully supported review
  runners.
- **FR-008**: Orca MUST distinguish at least: supported and auto-selectable,
  supported but not auto-selectable, and known but unsupported review agents.
- **FR-009**: Orca MUST report structured errors when a known but unsupported or
  unavailable review agent is selected.
- **FR-010**: Review output artifacts MUST emit reviewer-selection fields inside
  a `metadata` object, including at least `requested_agent`,
  `resolved_agent`, `active_agent`, `model`, `effort`, `selection_reason`,
  `support_tier`, `status`, `substantive_review`, and `used_legacy_input`.
- **FR-011**: Review output MUST record cross-agent vs same-agent fallback under
  `metadata`, including whether the review was truly cross-agent and whether a
  same-agent fallback occurred.
- **FR-012**: Orca MUST expose the resolved reviewer choice consistently across
  command output, review artifacts, and related documentation using the same
  `metadata` shape produced by the backend contract.
- **FR-013**: Orca MUST update adjacent cross-review references in
  `pr-review`, `self-review`, and README-facing docs so `agent` is the canonical
  term.
- **FR-014**: Orca MUST use a backend adapter model for review agents rather
  than hard-coding selection logic separately for each new agent.
- **FR-015**: Orca MUST allow a new verified review adapter such as
  `cursor-agent` to be added without redefining the whole review-selection
  policy.
- **FR-016**: Orca MUST remain provider-agnostic in reviewer selection behavior
  and MUST NOT assume only the original three review runners exist.
- **FR-017**: If enabled, Orca MAY remember the most recent successful reviewer
  per repo or feature, but that memory MUST remain advisory and safely ignored
  when stale.
- **FR-018**: Orca MAY ask the user when selection is materially ambiguous and
  the surrounding workflow supports prompting, but non-interactive runs MUST use
  a deterministic fallback rather than blocking.

### Key Entities *(include if feature involves data)*

- **Review Agent**: A named reviewer runtime Orca can resolve and invoke for
  cross-review, such as `codex`, `claude`, `gemini`, or `opencode`.
- **Agent Support Tier**: A classification describing whether a review agent is
  auto-selectable, selectable-but-best-effort, or known-but-unsupported.
- **Agent Resolution Result**: The structured outcome of reviewer selection,
  including requested agent, resolved agent, selection reason, and whether the
  result is truly cross-agent.
- **Review Agent Adapter**: The backend-specific invocation contract that maps a
  review agent name to a callable runtime path and normalized output handling.
- **Reviewer Memory Entry**: Optional stored context about the most recent
  successful reviewer for a repo or feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can run cross-review with `--agent opencode` and receive a
  normal review artifact through Orca's standard runtime path.
- **SC-002**: When `--agent` is omitted, Orca's resolved reviewer choice can be
  explained from documented precedence rules without hidden behavior.
- **SC-003**: Known but unsupported agents fail with explicit structured output
  rather than producing false-positive review success.
- **SC-004**: Cross-review, PR review, self-review, config docs, and README use
  consistent agent-based terminology after the feature is implemented.
- **SC-005**: Adding a new verified review adapter requires only adapter
  registration and support-tier declaration, not a redesign of the selection
  model.

## Documentation Impact *(mandatory)*

- **README Impact**: Required
- **Why**: This feature changes cross-review agent selection, configuration, support tiers, and reviewer-facing command behavior.
- **Expected Updates**: `README.md`, `commands/cross-review.md`, `config-template.yml`

## Assumptions

- `opencode` is the immediate next first-class reviewer because it is already
  installed and manually usable in this environment.
- `cursor-agent` is desirable but should not be auto-selectable until its CLI
  contract is verified against Orca's runtime expectations.
- Not every Orca-known installer agent should become a first-class reviewer in
  the same feature.
- The repomix finding about composable optional capabilities applies here:
  reviewer choice should be modeled as explicit policy plus adapters, not as a
  growing list of one-off command exceptions.
- This feature is about cross-review agent selection and runtime support, not a
  broader redesign of `code-review` or the full Orca review pipeline.
