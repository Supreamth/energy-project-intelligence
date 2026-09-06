# Schema v0.2 — closed contract

Status: **closed for MVP** on 2026-09-06. This is a data contract, not a migration that has been run. Do not reopen these decisions unless the user asks. Do not execute DDL until Foundation (real PostgreSQL + PostGIS).

Schema version string: `0.2`

## Locked decisions

### 1. Capacity: split scope and status

v0.1 `basis` mixed two axes. v0.2 forbids that.

| Axis | Field | Allowed values |
|---|---|---|
| What is counted | `scope` | `project`, `phase`, `unknown` |
| What state the number describes | `capacity_status` | `planned`, `operating`, `unknown` |
| What kind of power | `metric` | `solar_dc`, `solar_ac`, `export_limit`, `dc_it_load`, `dc_facility_power`, `contracted_power` |
| Unit | always `MW` for the metrics above | BESS power/energy are later metrics, never stuffed into `value_mw` |

`capacity_facts` columns for MVP:

- `subject_entity_id` (project or phase)
- `metric`
- `value_mw` numeric, must be > 0 when present; missing capacity is no row, never 0
- `scope`
- `capacity_status`
- `as_of_date` date null allowed
- `evidence_id`

Predicate form:

`capacity.{metric}.{scope}.{capacity_status}`

Example: `capacity.dc_it_load.phase.planned`

Canonical field_key equals the predicate for capacity.

Forbidden:

- Combining MWp with MWac or IT load with facility power
- Aggregating project-scope with phase-scope in one number
- Inventing a phase to hold a campus total
- `scope=phase` when subject kind is `project`

### 2. License identity

`status_observations` for regulatory status MUST carry:

- `dimension` = `regulatory`
- `license_kind`: `erc_generation` | `boi_promotion` | `other`
- `license_external_key` text null allowed (registration / promotion / license number as published)
- `status_code`: `submitted` | `approved` | `rejected` | `expired` | `unknown`

Canonical field_key:

- `regulatory.erc.generation`
- `regulatory.boi.promotion`
- `regulatory.other.{license_kind}` only when kind is `other`

ERC and BOI must never overwrite each other.

### 3. Review history is append-only

Keep `evidence.review_status` as the **current** snapshot.

Add `evidence_review_events`:

- `id`, `evidence_id`, `from_status`, `to_status`, `actor`, `reason`, `at`
- no updates, no deletes
- every non-pending transition inserts one event in the same transaction as the snapshot change

`reviewed_by` / `reviewed_at` on `evidence` are convenience copies of the latest event. History queries use the event table.

### 4. Publication classes

Two product surfaces:

- `internal` — default for MVP
- `external` — not enabled in MVP

`sources.rights_status` stays: `unknown` | `internal_only` | `derived_outputs_allowed` | `redistribution_allowed`

Gates:

- `unknown` and `internal_only` cannot be selected for `publication_class=external`
- MVP product reads only `publication_class=internal`
- Do not ship a public API/export in MVP

`canonical_selections` gains `publication_class` with unique current row per `(subject_entity_id, field_key, publication_class)` where `superseded_at` is null.

### 5. Canonical invalidation

Do not auto-pick a replacement.

Invalidate (set `superseded_at`, `invalidation_reason`) when:

- selected evidence `review_status` becomes `rejected` or `superseded`
- selected evidence subject is unmatched / changed
- source `rights_status` no longer permits that `publication_class`
- predicate no longer maps to `field_key` in the registry version used

Product views must exclude superseded rows. A human or approved rule must insert a new selection.

### 6. Fetch failure without raw

`fetch_events.raw_record_id` is **nullable**.

When HTTP 404 / timeout / robots / auth failure:

- insert `ingestion_runs` error counters
- insert `fetch_events` with `http_status` and `error_class`
- do **not** create a raw snapshot
- do **not** mark the project cancelled

`error_class`: `http_4xx` | `http_5xx` | `timeout` | `dns` | `tls` | `robots` | `parse` | `other`

Unique: `(run_id, raw_record_id)` only where `raw_record_id IS NOT NULL`. Failures are identified by `fetch_events.id`.

### 7. Predicate registry

Versioned table `predicate_registry` (also stored as JSON in docs for review):

- `predicate` text PK with `registry_version`
- `subject_kinds` text[] 
- `value_schema` jsonb
- `unit` text null
- `canonical_field_key` text
- `enabled` boolean

Ingestion rejects unknown predicates. Canonical selection rejects predicate/field_key mismatch.

MVP registry_version: `0.2.0`

### 8. Ingestion contract 0.2

Required fields:

- `schema_version`: `"0.2"`
- `source_code`
- `external_key` (stable per source record)
- `extractor_version`
- `fetched_at` RFC3339 UTC
- `payload.uri`, `payload.sha256`, `payload.content_type`
- `assertions[]` each with `extraction_key`, `predicate`, `value`, `locator`, `extractor_version` (may inherit), `review_status` default `pending`

Subject resolution:

1. `subject_external_key` present
2. look up `source_entity_links` for `(source_id, external_key)`
3. if missing, store evidence with `subject_entity_id` NULL (unresolved)
4. accept/canonical is forbidden until subject is linked

LLM extractors must not invent values absent from the payload.

## Pass / fail examples

Pass:

```json
{
  "schema_version": "0.2",
  "source_code": "demo_manual",
  "external_key": "demo-project-001",
  "extractor_version": "manual-0.2.0",
  "fetched_at": "2026-09-06T09:00:00Z",
  "payload": {
    "uri": "object://raw/demo/record.json",
    "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "content_type": "application/json"
  },
  "assertions": [
    {
      "extraction_key": "phase-a-it-load",
      "subject_external_key": "demo-project-001:phase-a",
      "predicate": "capacity.dc_it_load.phase.planned",
      "value": {"value": 40, "unit": "MW", "scope": "phase", "capacity_status": "planned"},
      "excerpt": "Phase A planned IT load 40 MW",
      "locator": {"json_path": "$.phase_a.it_load"},
      "confidence": 0.99,
      "review_status": "pending"
    }
  ]
}
```

Fail:

- `basis: campus_total` without `scope` / `capacity_status`
- `value: 0` meaning unknown
- `predicate: capacity.dc_it_load.phase.planned` on a project subject
- mixing 50 MWp and 40 MWac into one assertion
- selecting pending/rejected evidence as canonical
- publishing `rights_status=unknown` as external
- treating fetch HTTP 404 as `commercial=cancelled`

## MVP tables to migrate later (Foundation)

From v0.1 starter, plus:

- `sites`, `phases`, `entity_aliases`, `match_candidates`
- `project_parties`, `capacity_facts` (with scope + capacity_status), `milestone_facts`, `status_observations` (with license_kind + license_external_key)
- `predicate_registry`
- `evidence_review_events`
- nullable `fetch_events.raw_record_id`
- `canonical_selections.publication_class` and `invalidation_reason`

Still out of MVP migrations: imagery_*, portfolio/tenant tables.
