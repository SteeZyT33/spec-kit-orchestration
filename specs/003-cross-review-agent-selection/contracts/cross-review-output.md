# Contract: Cross-Review Output

## Required Review Metadata

Every cross-review result appended to `review.md` must record:

- requested agent
- resolved agent
- active provider when known
- model
- effort
- selection reason
- support tier
- cross-agent vs same-agent fallback

## Structured Result Rules

- If substantive review succeeds, findings are recorded normally.
- If the selected agent is unsupported, the artifact must explicitly say so.
- If the agent runtime fails, the artifact must say substantive review did not
  occur.

## Reporting Goal

A later reader should be able to answer:

- what reviewer was requested?
- what reviewer actually ran?
- why did Orca choose it?
- was the result truly cross-agent?
