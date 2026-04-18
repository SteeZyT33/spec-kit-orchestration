# Design: add-dark-mode

## Approach
Theme provider at root. CSS variables keyed on `data-theme`.

## Open Questions
- Persist across tabs? Yes via `storage` event.
