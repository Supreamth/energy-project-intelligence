# AI Handoff — Energy Project Intelligence

Updated: 2026-09-06 (UTC). Read this file first, then `status.json`, then `index.html` and `schema-v0.2.md`.

## What this is

Thailand Energy & Digital Infrastructure Intelligence. Track solar farms and data centers in Thailand with evidence-backed facts. Schema v0.2 is a **closed contract**. It has not been migrated or run.

GitHub: https://github.com/Supreamth/energy-project-intelligence
Docs: `/opt/data/docs/energy-project-intelligence/`
Public: `https://enerise.sprees.net/`
Schema: `https://enerise.sprees.net/schema-v0.2.html`
Next prompt: `https://enerise.sprees.net/#next-prompt` and `next-prompt.txt`

## Current truth (do not assume otherwise)

- Local clone: `/opt/data/workspace/energy-project-intelligence`
- GitHub origin/main is pushed
- Live docs with HTTP Basic Auth
- Schema v0.2 closed; no application code, no migrations, no fixtures
- Docker CLI exists; Docker daemon is not running; `docker compose` is missing
- PostgreSQL/PostGIS not installed
- Update https://enerise.sprees.net/ and the Next prompt on every change
- Never commit secrets
- Do not reopen schema v0.2 unless the user asks

## Ordered work

0. Reference website + login (done)
1. GitHub connected (done)
2. Schema v0.2 contract (done — not migrated)
3. Foundation: repo layout, Postgres+PostGIS, Alembic, roles, private object storage
4. Manual ingestion end-to-end
5. Review UI + canonical selection
6. Project Intelligence product page

## Schema v0.2 (locked)

See `schema-v0.2.md`. Short form:

- Capacity: `scope` + `capacity_status`, never mixed `basis`
- License: `license_kind` + `license_external_key`
- Append-only `evidence_review_events`
- MVP publication_class=internal only
- Canonical invalidation does not auto-select
- Fetch failures allow null raw_record_id; 404 ≠ cancelled
- Predicate registry 0.2.0
- Ingestion contract schema_version 0.2 + extractor_version

## Continue

Copy the live Next prompt from https://enerise.sprees.net/#next-prompt or `/opt/data/docs/energy-project-intelligence/next-prompt.txt`.
