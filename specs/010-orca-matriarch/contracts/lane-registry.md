# Contract: Lane Registry

## Purpose

Define the durable metadata layer Matriarch owns.

## Required Properties

- one canonical lane record per active supervised lane
- explicit mapping from lane to spec/branch/worktree where known
- explicit dependency relationships
- explicit ownership/assignment records
- durable timestamps for creation and latest update

## Registry Rules

- registry metadata is authoritative for orchestration intent
- live git/worktree state is authoritative for observed runtime reality
- Matriarch must detect and surface drift between registry intent and live
  state
- archived lanes remain inspectable but are excluded from default active views
