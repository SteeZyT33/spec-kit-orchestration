# Feature Specification: Orca Brainstorm Memory

**Feature Branch**: `002-brainstorm-memory`  
**Created**: 2026-04-09  
**Status**: Implemented  
**Input**: User description: "Orca brainstorm memory: persist brainstorm sessions as numbered documents with an overview index, revisit/update behavior, parked ideas, and forward links into specs so later flow-state, review-artifacts, context-handoffs, and orca-yolo can consume durable idea history."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Saved Brainstorms Become Durable Project Memory (Priority: P1)

A developer uses `speckit.orca.brainstorm` to think through a new feature. When the session produces a meaningful idea, parked concept, or spec-ready direction, Orca writes a numbered brainstorm document into a project-local brainstorm memory area so the reasoning is not lost when the session ends.

**Why this priority**: This is the core value. Without durable brainstorm artifacts, Orca still loses ideation context between sessions and cannot support later flow-state or orchestration reliably.

**Independent Test**: Run a brainstorm session, choose to save it, and verify a numbered brainstorm document is created with the required sections and metadata.

**Acceptance Scenarios**:

1. **Given** no brainstorm memory directory exists, **When** a meaningful brainstorm session is saved, **Then** Orca creates the directory and writes a numbered brainstorm document there.
2. **Given** existing brainstorm documents `01-auth.md` and `02-review-flow.md`, **When** a new brainstorm is saved, **Then** the new document is numbered sequentially as the next available entry.
3. **Given** a saved brainstorm session, **When** the document is written, **Then** it contains enough structured information to reconstruct the problem framing, approaches considered, current outcome, and open questions without replaying the chat.

---

### User Story 2 - Overview View Shows the Current Idea Landscape (Priority: P1)

A developer returns to a repo after time away and needs to understand which brainstorms exist, which are active, which are parked, and which already led to specs. Orca maintains a single overview document that summarizes all brainstorm memory entries and their current state.

**Why this priority**: Multiple brainstorm docs only become usable memory if there is a navigable overview. This is the main usability layer over the raw documents.

**Independent Test**: Save multiple brainstorm entries with different statuses, regenerate the overview, and verify the index, open threads, and parked/linked status are reflected correctly.

**Acceptance Scenarios**:

1. **Given** the first saved brainstorm in a project, **When** the document is written, **Then** Orca also creates an overview file with an index entry for that brainstorm.
2. **Given** multiple saved brainstorms already exist, **When** a new brainstorm is saved or an existing one is updated, **Then** the overview is refreshed rather than overwritten with partial data.
3. **Given** brainstorms with unresolved questions, **When** the overview is regenerated, **Then** their open threads are aggregated into a single place that a user can scan quickly.

---

### User Story 3 - Incomplete Or Parked Brainstorms Can Still Be Saved Intentionally (Priority: P2)

A developer explores an idea but decides not to move into specification yet. Orca should preserve worthwhile exploration when the user chooses to save it, while avoiding automatic clutter for trivial or abandoned interactions.

**Why this priority**: Many useful ideas do not immediately become specs. Orca needs to support “not ready yet” as a first-class workflow state.

**Independent Test**: End a brainstorm before spec creation, choose to save it, and verify the resulting memory entry is marked as parked or abandoned rather than spec-created.

**Acceptance Scenarios**:

1. **Given** a brainstorm that reached meaningful exploration but no spec was created, **When** the user chooses to save it, **Then** Orca writes the brainstorm document with a non-spec status such as parked or abandoned.
2. **Given** a brainstorm with minimal or no meaningful interaction, **When** the session ends, **Then** Orca does not create a saved document unless the user explicitly overrides that default.
3. **Given** a user declines to save an incomplete brainstorm, **When** the session ends, **Then** no brainstorm memory document is created and the overview remains unchanged.

---

### User Story 4 - Revisiting A Topic Updates Existing Memory Intentionally (Priority: P2)

A developer starts brainstorming a topic that overlaps with an earlier idea. Orca detects the likely overlap and lets the user choose whether to create a new brainstorm entry or append to the existing one.

**Why this priority**: Without revisit handling, brainstorm memory becomes noisy and fragmented, and later Orca systems will not know whether multiple docs represent one evolving idea or separate ideas.

**Independent Test**: Start a brainstorm on a topic similar to an existing brainstorm and verify Orca offers update-vs-new behavior and records the result appropriately.

**Acceptance Scenarios**:

1. **Given** a related brainstorm document already exists, **When** a new brainstorm starts on the same topic area, **Then** Orca surfaces that overlap and offers the user a choice to update the existing entry or create a new one.
2. **Given** the user chooses to update an existing brainstorm, **When** the session is saved, **Then** Orca appends or merges the new reasoning into that brainstorm while preserving prior history.
3. **Given** the user chooses to create a new brainstorm instead, **When** the session is saved, **Then** Orca creates a distinct new numbered document and updates the overview accordingly.

---

### User Story 5 - Brainstorm Memory Links Forward Into Later Workflow Artifacts (Priority: P3)

A developer uses brainstorm memory as the start of a larger Orca workflow. When a brainstorm leads to a spec, Orca records the forward link so later flow-state, review artifacts, context handoffs, and `orca-yolo` can see where the idea turned into execution.

**Why this priority**: This is what makes brainstorm memory part of a workflow system rather than a note archive.

**Independent Test**: Save a brainstorm, create a spec from it, and verify the brainstorm record and overview capture a forward reference to the resulting spec or feature branch.

**Acceptance Scenarios**:

1. **Given** a brainstorm leads to a new spec, **When** specification is created from that brainstorm, **Then** the brainstorm record can be marked as spec-created with a pointer to the resulting spec artifact or feature identity.
2. **Given** a saved brainstorm has an associated spec, **When** the overview is regenerated, **Then** the overview shows that link in the brainstorm index.
3. **Given** later Orca systems need upstream ideation context, **When** they inspect the brainstorm record, **Then** they can discover the linked spec identity without requiring chat history.

### Edge Cases

- What happens when the brainstorm memory directory exists but the overview file is missing? The system MUST regenerate the overview from existing brainstorm documents.
- What happens when brainstorm documents have numbering gaps because some were deleted manually? The system MUST use `max + 1` rather than reusing missing numbers.
- What happens when a brainstorm topic contains only punctuation or very weak text? The system MUST still produce a valid, readable fallback title/slug when saving is requested.
- What happens when a revisit matches multiple prior brainstorms? The system MUST present the likely matches clearly enough for the user to choose update vs new entry.
- What happens when the brainstorm document was manually edited between sessions? The system MUST preserve existing content and avoid destructive overwrite during updates or overview regeneration.
- What happens when a brainstorm has no linked spec yet? The system MUST still appear correctly in the overview as an active, parked, or abandoned idea.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Orca MUST persist saved brainstorm sessions as numbered project-local brainstorm documents rather than relying on transient chat context.
- **FR-002**: Orca MUST create the brainstorm memory directory automatically when the first saved brainstorm requires it.
- **FR-003**: Orca MUST assign brainstorm numbers sequentially using the highest existing numbered brainstorm entry plus one.
- **FR-004**: Orca MUST write each saved brainstorm as a structured document that captures, at minimum, topic, date, status, problem framing, approaches considered, current outcome, and open threads.
- **FR-005**: Orca MUST maintain a single overview document for brainstorm memory that summarizes all saved brainstorm entries.
- **FR-006**: The overview MUST include a sessions index with enough information to identify brainstorm number, topic, date, current status, and any linked downstream artifact.
- **FR-007**: The overview MUST aggregate unresolved or open-thread items from saved brainstorm documents into a single scan-friendly section.
- **FR-008**: Orca MUST support at least the following brainstorm statuses: active, parked, abandoned, and spec-created.
- **FR-009**: Orca MUST allow a meaningful brainstorm session to be saved even when it does not proceed to specification.
- **FR-010**: Orca MUST avoid auto-saving trivial or near-empty brainstorm sessions unless the user explicitly asks to preserve them.
- **FR-011**: Orca MUST detect likely overlap with existing brainstorm topics and offer update-versus-new behavior before saving the revisit.
- **FR-012**: When a user chooses to update an existing brainstorm, Orca MUST preserve prior context rather than replacing the earlier brainstorm record wholesale.
- **FR-013**: When a brainstorm leads to a spec, Orca MUST support marking that brainstorm as spec-created and storing a forward link to the resulting spec artifact or feature identity.
- **FR-014**: Overview regeneration MUST be idempotent so repeated refreshes produce the same result from the same underlying brainstorm records.
- **FR-015**: Brainstorm memory artifacts MUST be usable by later Orca systems including flow-state, review-artifacts, context-handoffs, and `orca-yolo` without requiring access to original chat history.
- **FR-016**: Brainstorm memory MUST remain provider-agnostic and MUST NOT rely on Claude-specific session files, naming, or plugin substrate.

### Key Entities *(include if feature involves data)*

- **Brainstorm Record**: A numbered markdown document representing one brainstorm session or one evolving brainstorm thread. It stores topic, date, status, reasoning summary, open threads, and optional links to downstream workflow artifacts.
- **Brainstorm Overview**: A generated index document that summarizes all brainstorm records in a project, including active ideas, parked ideas, spec-linked ideas, and aggregated open threads.
- **Brainstorm Status**: A lifecycle value describing the current state of a brainstorm record, such as active, parked, abandoned, or spec-created.
- **Downstream Link**: A forward reference from a brainstorm record to a later Orca artifact such as a spec, feature branch, or other workflow identity.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every brainstorm session the user chooses to save results in a durable brainstorm record with the required structured sections.
- **SC-002**: The overview document accurately reflects the current set and state of brainstorm records after creation or update operations.
- **SC-003**: A user returning to the repo can identify active, parked, and spec-linked ideas from the overview without opening every brainstorm file individually.
- **SC-004**: A saved brainstorm that later becomes a spec can be traced forward to that spec through the brainstorm record and overview.
- **SC-005**: Orca can consume brainstorm memory as durable workflow input in later systems without relying on prior chat/session context.

## Documentation Impact *(mandatory)*

- **README Impact**: Required
- **Why**: This feature changes where brainstorm artifacts live, adds durable memory behavior, and introduces operator-visible helper commands.
- **Expected Updates**: `README.md`, `commands/brainstorm.md`

## Assumptions

- Brainstorm memory should live in a project-local directory such as `brainstorm/` rather than in provider-specific session storage.
- The exact document template and formatting can evolve later as long as the required information model remains stable.
- Topic overlap detection can begin with lightweight heuristics rather than requiring semantic matching in the first version.
- Brainstorm memory is intended as an additive workflow layer; it does not replace spec artifacts or review artifacts.
- Reverse links from specs back into brainstorm records are valuable but can be deferred as long as forward links from brainstorms to specs are supported.
