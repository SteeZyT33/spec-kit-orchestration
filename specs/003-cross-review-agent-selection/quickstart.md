# Quickstart: Orca Cross-Review Agent Selection

## Goal

Validate that Orca can select, invoke, and report review agents honestly and
consistently.

## Setup

1. Work in the Orca repo with the cross-review runtime available.
2. Ensure at least one existing Tier 1 adapter and `opencode` are installed.
3. Run syntax and Python checks on touched launcher/backend files.

## Scenario 1: Explicit `--agent`

1. Run cross-review with `--agent opencode`.
2. Verify:
   - `opencode` is invoked through Orca's normal runtime path
   - output records requested and resolved agent as `opencode`
   - selection reason indicates explicit request

## Scenario 2: Legacy `--harness`

1. Run cross-review with `--harness claude`.
2. Verify:
   - the review still runs
   - output marks legacy input usage
   - resolved reviewer is still recorded as an agent

## Scenario 3: Auto-selection

1. Run cross-review with no explicit reviewer configured.
2. Verify:
   - Orca selects according to documented precedence
   - output includes the selection reason
   - if the selected reviewer matches the active provider, Orca warns that the
     run is not truly cross-agent

## Scenario 4: Unsupported known agent

1. Run cross-review with a known but unsupported agent.
2. Verify:
   - Orca returns structured unsupported-agent output
   - no artifact claims substantive review succeeded

## Scenario 5: Adjacent documentation consistency

1. Review `cross-review`, `pr-review`, `self-review`, config docs, and README.
2. Verify:
   - `agent` is canonical terminology
   - `harness` appears only as compatibility language
