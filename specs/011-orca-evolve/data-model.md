# Data Model: Orca Evolve

## Harvest Entry

Represents one external pattern or feature under Orca adoption review.

Fields:

- `entry_id`: canonical identifier
- `title`: short human-readable name
- `source_name`: source repo or system name
- `source_ref`: path, spec, doc, or other durable source pointer
- `summary`: concise idea summary
- `decision`: `direct-take` | `adapt-heavily` | `defer` | `reject`
- `rationale`: why the decision was made
- `entry_kind`: `pattern` | `wrapper-capability`
- `target_kind`: `existing-spec` | `future-feature` | `capability-pack` | `roadmap` | `none`
- `target_ref`: target spec id or future feature identifier
- `status`: `open` | `mapped` | `implemented` | `deferred` | `rejected`
- `follow_up_ref`: optional spec/doc/link reference
- `external_dependency`: optional external system or skill the wrapper depends on
- `ownership_boundary`: optional note describing what Orca owns vs delegates
- `adoption_scope`: `portable-principle` | `host-specific-detail` | `mixed`
- `created_at`
- `updated_at`

## Harvest Index

Represents the operator-facing overview of current adoption work.

Fields:

- `open_entries`
- `mapped_entries`
- `implemented_entries`
- `deferred_entries`
- `rejected_entries`

## Adoption Mapping

Represents the relationship between a harvest entry and an Orca destination.

Fields:

- `entry_id`
- `target_kind`
- `target_ref`
- `mapping_notes`
