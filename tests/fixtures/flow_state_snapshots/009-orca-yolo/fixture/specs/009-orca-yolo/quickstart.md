# Quickstart: Orca YOLO

## Validate The First-Version Orchestration Contract

1. Start from a durable brainstorm-memory or spec artifact and verify the run
   can identify a legal starting stage.
2. Review the run-stage contract in `contracts/run-stage-model.md` and verify it
   aligns with existing Orca workflow language.
3. Review the run-state contract in `contracts/run-state.md` and verify it is
   sufficient to support resume without chat reconstruction.
4. Review the orchestration policy contract in
   `contracts/orchestration-policies.md` and verify ask/start/resume/retry/PR
   behavior is explicit.
5. Cross-check `009` against `005`, `012`, `007`, and `008` and verify `orca-yolo`
   consumes their contracts rather than replacing them.
6. Verify the default end state is at least PR-ready completion and that PR
   publication remains explicit policy.
