---
description: "Review report template for post-implementation review output"
---

# Review: [FEATURE NAME]

**Feature Branch**: `[###-feature-name]`
**Spec**: [spec.md](spec.md)

<!--
  This file is generated and maintained by the /speckit.review command.
  Each phase review appends a new section below. Previous sections are never overwritten.
  This is the authoritative record of all review findings, fixes, and PR status.
-->

## Phase N Review — [DATE]

### Merge Conflicts: PASS | FAIL
<!-- PASS when no conflicts with target branch; FAIL lists conflicting files -->
<!-- Findings in CONFLICT ZONE files are flagged — resolve before relying on results -->
- [conflicting file list, or "No conflicts with main"]

### Spec Compliance: PASS | FAIL
<!-- For each finding, include file:line reference and the specific spec requirement -->
- [findings with file:line references]

### Code Quality: PASS | FAIL
<!-- For each finding, include file:line reference and the plan.md section it relates to -->
- [findings with file:line references]

### Security: PASS | FAIL | SKIPPED
<!-- SKIPPED when spec doesn't touch sensitive areas and --security not passed -->
<!-- For each finding, include OWASP category and file:line reference -->
- [findings with file:line references]

### Actions Taken
- AUTO-FIXED: [count] issues ([commit SHAs])
- SUGGESTED: [count] issues ([accepted/pending/rejected])
- FLAGGED: [count] issues
- ISSUED: [count] issues ([issue numbers or descriptions if GH unavailable])

### PR: #[number] — [status]
- Comments: [total] | Addressed: [n] | Rejected: [n] | Issued: [n] | Clarify: [n]
- Batch-rejected: [count] ([path pattern])

### External Comment Responses
<!-- Populated when --comments-only is used or when processing PR reviewer comments -->
| # | Reviewer | File | Status | Detail |
|---|---------|------|--------|--------|

### Post-Merge Verification
<!-- Populated when --post-merge is used or after merge is detected -->
- REVERTED: [count] | OK: [count] | Issues created: [issue numbers]

<!--
  If GitHub tools are unavailable, replace the PR section with:
  ### PR: Not created (GitHub tools unavailable)
  - Review findings are recorded above. Create PR manually if needed.
-->
