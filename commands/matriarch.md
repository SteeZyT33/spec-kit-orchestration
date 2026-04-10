# /speckit.orca.matriarch

Use Matriarch when you need one durable view over multiple active specs, lanes,
owners, dependencies, and readiness states.

Matriarch is a supervisor, not a hidden swarm runtime. It should expose state,
assignment, blockers, mailbox/report traffic, and optional deployment metadata
without pretending a running session means the work is healthy or done.

## What It Owns

- lane registration for one primary spec per lane
- lane assignment and reassignment history
- dependency relationships between lanes
- readiness aggregation from durable flow and review evidence
- durable mailbox/report queues for lane-local workers
- optional deployment attachment metadata for `tmux` or `direct-session`
- claim-safe delegated work records inside a lane

## What It Does Not Own

- feature-stage semantics owned by flow-state
- review evidence semantics owned by review artifacts
- handoff document semantics owned by context handoffs
- uncontrolled autonomous execution

## Runtime Surface

Use the repo-local launcher:

```bash
bash scripts/bash/orca-matriarch.sh status
bash scripts/bash/orca-matriarch.sh lane register 010-orca-matriarch --owner-type human --owner-id taylor
bash scripts/bash/orca-matriarch.sh lane list
bash scripts/bash/orca-matriarch.sh lane show 010-orca-matriarch
bash scripts/bash/orca-matriarch.sh lane depend 010-orca-matriarch --on 011-orca-evolve --target-kind lane_exists
bash scripts/bash/orca-matriarch.sh lane mailbox send 010-orca-matriarch --direction to_lane --sender matriarch --recipient worker-1 --type instruction --payload '{"step":"inspect"}'
bash scripts/bash/orca-matriarch.sh lane startup-ack 010-orca-matriarch --sender worker-1 --deployment-id 010-orca-matriarch-direct-session
bash scripts/bash/orca-matriarch.sh lane work create 010-orca-matriarch T001 --title "Implement registry runtime"
```

## Safety Rules

- one lane owns one primary spec in v1
- lane state is durable and inspectable even if a session dies
- deployment health is separate from workflow readiness
- `direct-session` is first-class for long-lived interactive CLIs such as Claude Code
- mailbox/report files are the source of truth, not tmux keystrokes
