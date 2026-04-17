# Data Model: Orca YOLO

## Entity: Yolo Run

- **Description**: One durable full-cycle Orca orchestration attempt.
- **Fields**:
  - run id
  - feature or artifact anchor
  - start mode
  - current stage
  - run policy
  - linked artifact paths
  - current outcome
  - stop reason
  - optional lane agent binding (present when matriarch-supervised)
- **Relationships**:
  - references one or more upstream workflow artifacts
  - contains one current run policy
  - resolves to one current run outcome
  - may hold at most one Lane Agent Binding linking it to a matriarch lane

## Entity: Run Stage

- **Description**: A defined workflow stage `orca-yolo` can enter, complete,
  pause at, or fail at.
- **Stages** (happy-path order): brainstorm, specify, clarify, review-spec,
  plan, tasks, assign (optional), implement, review-code, pr-ready,
  pr-create (opt-in), review-pr (post-merge)
- **Fields**:
  - stage id
  - stage order
  - required upstream artifacts
  - completion criteria
  - downstream handoff expectations
- **Relationships**:
  - belongs to the `Yolo Run` stage model
  - may emit or consume `012-review-model` and `007-orca-context-handoffs` artifacts

## Entity: Run Policy

- **Description**: The explicit settings controlling how a `Yolo Run` behaves.
- **Fields**:
  - ask level
  - start-from stage
  - resume mode
  - worktree mode
  - retry policy
  - PR completion policy
  - supervision mode (`standalone` | `matriarch-supervised`)
  - deployment kind (`standalone` | `direct-session` | `tmux`)
- **Relationships**:
  - belongs to one `Yolo Run`
  - governs one or more `Run Stage` transitions
  - supervision mode determines whether a Lane Agent Binding is required

## Entity: Run Outcome

- **Description**: The current or final status of a `Yolo Run`.
- **Fields**:
  - outcome state
  - timestamped status summary
  - blocking condition if any
  - final artifact links
  - last upward report reference (supervised mode only)
- **Relationships**:
  - belongs to one `Yolo Run`
  - can reference review artifacts, PR outputs, and handoff state
  - in supervised mode, can reference mailbox events emitted to matriarch

## Entity: Lane Agent Binding

- **Description**: Optional link between a `Yolo Run` and a
  `010-orca-matriarch` lane identity. Present only when the run is
  matriarch-supervised. Carries just enough matriarch context to participate
  as a Lane Agent without duplicating matriarch's lane state inside `009`.
- **Fields**:
  - lane id (matches matriarch lane identity, defaults to primary spec id)
  - mailbox path (points at the matriarch-owned lane mailbox)
  - deployment kind (matches the deployment the lane is running under)
  - last outbound event id (most recent event emitted to the Lane Mailbox)
- **Relationships**:
  - belongs to at most one `Yolo Run`
  - references one matriarch lane (by id) without owning its lifecycle
  - references one Lane Mailbox path without owning its contents
