# Contract: Cross-Review Configuration

## Canonical Shape

```yaml
crossreview:
  agent: null
  model: null
  effort: "high"
  ask_on_ambiguous: true
  remember_last_success: true
```

## Compatibility Rules

- `crossreview.agent` is canonical
- `crossreview.harness` remains accepted temporarily as a legacy alias
- if both are present, `crossreview.agent` wins

## Behavioral Meaning

- `agent`: preferred explicit reviewer
- `model`: adapter-specific model override when supported
- `effort`: adapter-specific reasoning effort when supported
- `ask_on_ambiguous`: deferred workflow-level behavior; the backend currently
  remains deterministic and does not prompt on its own
- `remember_last_success`: whether supplied reviewer memory may be used as
  advisory selection context
