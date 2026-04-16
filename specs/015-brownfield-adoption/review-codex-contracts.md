> **Historical audit trail** — codex gpt-5.4 (high effort) cross-review
> of 015 contracts, run on 2026-04-15 against commit `52a03e4` (before
> 013 runtime PR #40 merged). The "still broken" verdict and claims
> about absent `spec_lite.py` / missing guards reflected accurate
> runtime state AT THAT TIME. The issues identified were addressed
> in the forward-looking framing revision and later resolved
> definitively by PR #40 (013 runtime) shipping. Preserved here as
> an audit trail; treat all runtime-state claims as historical, not
> current.

### Verdict
**still broken** *(historical — see note above)*.

### Critical issues (must fix before merge)

- `013` is not a shipped runtime surface in this checkout, so 015 is still mirroring code that does not exist. `specs/013-spec-lite/contracts/spec-lite-record.md:5-9` says 013 binds `src/speckit_orca/spec_lite.py`, but that file is absent. `src/speckit_orca/flow_state.py:148-158` still emits only the full-spec `FlowStateResult`, and `src/speckit_orca/flow_state.py:388-396` still assumes a feature directory with `brainstorm.md/spec.md/plan.md/tasks.md/...`. That makes 015’s “013 first, then 015” and “per-file mirror” claims false at `specs/015-brownfield-adoption/data-model.md:266-270`, `specs/015-brownfield-adoption/contracts/adoption-record.md:267-302`, and `specs/015-brownfield-adoption/quickstart.md:80-115`. The review prompt assumes #36 shipped a 013 runtime; the code in this repo does not back that up.

- The `review_state` contract is anchored to a phantom API. 015 says adoption hard-codes `review_state: "not-applicable"` “parallel to 013’s spec-lite view” in `specs/015-brownfield-adoption/contracts/adoption-record.md:290-296` and `specs/015-brownfield-adoption/data-model.md:151-158`. But current `flow_state.py` has no `review_state` field anywhere; it returns `review_milestones` inside `FlowStateResult` (`src/speckit_orca/flow_state.py:138-158`, `715-731`). 012’s actual contract is still `review_spec_status` / `review_code_status` / `review_pr_status` / `overall_ready_for_merge` (`specs/012-review-model/data-model.md:235-264`). So this is not just “a fourth enum value might break aggregation.” There is no existing per-file flow-state view or `review_state` enum in runtime to extend.

- The guard-ordering claim is still ungrounded against current `register_lane`. 015 now correctly says the guard must fire before side effects (`specs/015-brownfield-adoption/contracts/matriarch-guard.md:23-30`, `115-159`), and the quickstart asserts the mailbox/report paths remain absent after rejection (`specs/015-brownfield-adoption/quickstart.md:150-166`). But `src/speckit_orca/matriarch.py:706-736` has no spec-lite or adoption precondition block at all and eagerly creates `mailbox_root`, report directories, and delegated-task JSON before anything else. `specs/015-brownfield-adoption/data-model.md:266-268` and `contracts/matriarch-guard.md:6-10` both talk as if 013’s guard already exists “alongside” 015’s. It does not.

- The 010 mailbox cross-reference overstates current runtime truth. `specs/015-brownfield-adoption/data-model.md:268` points implementers to `specs/010-orca-matriarch/contracts/event-envelope.md` as the authoritative accepted-type list. That contract includes `archived` and `resolved` and a required `references` field for some events (`specs/010-orca-matriarch/contracts/event-envelope.md:23-29`). Current `src/speckit_orca/matriarch.py` accepts only eight types (`30-39`), and `EventEnvelope` / `send_mailbox_event` has no `references` field at all (`52-64`, `923-957`). 015 may not modify mailbox behavior, but the doc is still making a grounding claim that current code contradicts.

### Design concerns (consider before merge)

- The parser is not actually “spec-lite-like,” and the prose still blurs that. 015 explicitly allows unknown headings in an `extra` bucket and tolerates status/optional-section mismatches (`specs/015-brownfield-adoption/contracts/adoption-record.md:155-169`, `327-364`). 013’s contract stays strict on headings and does not define unknown-section capture (`specs/013-spec-lite/contracts/spec-lite-record.md:153-170`, `243-261`). The repeated “matches ... spec-lite conventions” phrasing at `specs/015-brownfield-adoption/contracts/adoption-record.md:329-331` and `data-model.md:279-285` makes it too easy for an implementer to copy the wrong parser shape.

- The tightened filename regex and the guard helper compose functionally, but the wording is sloppy. `specs/015-brownfield-adoption/contracts/adoption-record.md:178-186` says `AR-NNN` without a slug is not a valid on-disk record name. `specs/015-brownfield-adoption/contracts/matriarch-guard.md:61-78` still treats `adopted_dir / f"{spec_id}.md"` as the “canonical path” and would return `True` for malformed `AR-001.md`. That is defensible for a rejection guard, but then say explicitly that the helper is intentionally broader than the record-validity rule.

- The quickstart validation block reads like implementation evidence, not contract intent. `specs/015-brownfield-adoption/quickstart.md:332-352` claims each step “conforms” today, but several steps depend on flow-state file-target support and pre-side-effect matriarch guards that do not exist in current `src/`. That section should be softened or it will mislead reviewers.

### Style / polish nits (optional)

- `specs/015-brownfield-adoption/contracts/matriarch-guard.md:80-83` correctly says the fallback is not a repo-wide scan. Keep that narrower wording everywhere; earlier 015 wording drifted.
- `specs/015-brownfield-adoption/quickstart.md:30` uses `/speckit.orca.adopt` while the runtime examples use `python -m speckit_orca.adoption`. If those names intentionally differ, say so once.

### What looks right (brief, <100 words)

The v2 contracts did fix the earlier design problems: ARs are separate from spec-lite, touch-point coordination is gone, and 012 is no longer treated as owning `review_state`. The supersede/retire record shape is internally coherent. The glob logic itself is sane too: for `spec_id="AR-001"`, it ignores `AR-0010-bar.md` and will match `AR-001-foo.md` / `AR-001-foo-bar.md`. The blockers now are mostly grounding problems against current `src/`, not the AR primitive itself.