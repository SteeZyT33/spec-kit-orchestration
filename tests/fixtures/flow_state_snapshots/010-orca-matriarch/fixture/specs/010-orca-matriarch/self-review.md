# Self Review: Orca Matriarch

## Verdict

`010` is now structurally coherent and no longer has missing system seams.
The remaining risk is not missing architecture; it is leaving the tmux
operator flow too underspecified and accidentally creating a high-friction
or non-portable runtime.

## Findings

1. **Low risk: tmux launch policy should be narrowed further before implementation.**
   The current contracts correctly say tmux is optional and supervised, but
   they still leave too much room for multiple launch styles. That would create
   drift between repos and operators.

2. **Low risk: report-back transport is right, but command ergonomics should stay minimal.**
   The file-backed report path is the correct v1 choice because it survives
   detaches, shell exits, and provider variation. The launch surface should be
   built around that simplicity, not around advanced tmux choreography.

## Recommendation

Use the least-friction tmux model in v1:

- one lane maps to one tmux session
- one primary worker process runs in that session
- Matriarch only supports `launch`, `attach`, `inspect`, and `mark-missing`
- session naming should be deterministic: `<repo>-<lane-id>`
- launch should run a repo-local bootstrap command inside tmux, not construct
  complex pane/window layouts
- agent-to-Matriarch communication should remain file-backed under
  `.specify/orca/matriarch/reports/<lane-id>/`
- `checkout --exec` should prefer tmux attach when a healthy lane deployment
  exists; otherwise it should print the next safe action instead of guessing

## Why This Is The Best V1

- universal: tmux is widely available and does not depend on one AI provider
- durable: files survive detaches and can be inspected manually
- debuggable: operator can inspect the raw session and raw report files
- reversible: manual lanes and non-tmux lanes still work normally
- conservative: Matriarch supervises, but does not become a swarm runtime

## Final Judgment

`010` is ready to stop expanding in scope. The next good move is to treat the
tmux recommendation above as the default implementation posture and commit the
planning package.

## Final Addendum

After the latest refinement pass, the main remaining issues from external
review have been closed at the planning-contract level:

- shared mailbox/report event envelope is now explicit
- registry write-safety is now concrete enough for implementation planning
- `lane_id = spec_id` is fixed for v1
- `direct-session` is now a first-class deployment case for Claude Code and
  other non-tmux workers

Current judgment:

- `010` is planning-complete enough to commit
- the remaining open choices are implementation-policy details, not structural
  design gaps

## Implementation Addendum

The implementation stayed within the intended boundary:

- deterministic Python runtime first
- thin Bash wrapper second
- durable state over chat memory or tmux state
- `direct-session` treated as first-class rather than as an absent deployment

What review improved:

- the first external code pass caught real runtime issues before commit
- the locking model now actually covers lane-file persistence, not just the
  top-level registry
- the event layer is clearer because ACK state is explicit in emitted events
- delegated-work completion now records when work finished instead of leaving
  only claim-time evidence

Residual risk:

- `opencode` timed out on the final follow-up pass, so the last external review
  signal is “issues found and fixed,” not “fresh clean approval”

Current judgment:

- merge readiness: yes
- scope discipline: strong
- conservative supervisor posture: preserved
