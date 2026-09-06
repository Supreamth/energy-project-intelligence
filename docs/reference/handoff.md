# AI Handoff — Energy Project Intelligence

Updated: 2026-09-06 (UTC). Read this file first, then `status.json`, then `index.html`.

## What this is

Thailand Energy & Digital Infrastructure Intelligence. Track solar farms and data centers in Thailand with evidence-backed facts. Schema v0.1 exists as a design contract only. Implementation has not started.

GitHub: https://github.com/Supreamth/energy-project-intelligence
Docs: `/opt/data/docs/energy-project-intelligence/`
Public: `https://enerise.sprees.net/` (HTTP Basic Auth; username `supree`; password hash only in `/opt/data/home/.enerise/auth.json`)

Source sessions:
- `@session:default/20260906_025242_b8fba1` — schema review + setup plan
- `@session:default/20260906_030903_baf0e5` — continue work; user asked for the list, then approved items 1–2 (this website)

## Current truth (do not assume otherwise)

- Local clone exists: `/opt/data/workspace/energy-project-intelligence`
- GitHub remote: https://github.com/Supreamth/energy-project-intelligence (public, main pushed)
- Live docs: https://enerise.sprees.net/  (HTTP Basic Auth; hash in `/opt/data/home/.enerise/auth.json`)
- No application code, no migrations, no fixtures
- GitHub device login succeeded for user Supreamth; token is local-only, never in git
- Docker CLI exists; Docker daemon is not running; `docker compose` is not available
- PostgreSQL/PostGIS/psql/alembic are not installed
- User asked to install on THIS machine
- User wants a single browser-readable reference; **update https://enerise.sprees.net/ on every change**
- Do not start collectors, imagery, Solar Portfolio, Kubernetes, or LLM auto-approval
- Never commit secrets

## Ordered work

0. Reference website + local HTTP + public login (done)
1. Clone/connect GitHub (done — origin/main pushed)
2. Schema v0.2 decisions before migration
3. Foundation: repo layout, Postgres+PostGIS, Alembic, roles, private object storage
4. Manual ingestion end-to-end
5. Review UI + canonical selection
6. Project Intelligence product page

## MVP definition of done

Open one project → see company, site, capacity/load, status, key dates → click through to original evidence for each value → see conflicting values and why one was chosen.

## Data rules that must not be violated

- Three layers: Raw (immutable snapshot) → Evidence (claims with locators) → Canonical (selected product values)
- NULL means unknown; never store 0 for missing
- Timestamps UTC; display Asia/Bangkok; Buddhist-era dates keep original + validated CE
- Do not invent phases from a total MW figure
- Do not use HQ address as site location
- Construction complete ≠ operating
- Missing source / HTTP 404 ≠ cancelled project
- Do not mix MWp, MWac, IT load, facility power
- Do not add project total to phase total
- Planned dates stay ranges; do not coerce Q4/2027 into 2027-10-01 opening
- Ambiguous identity match goes to review queue; no auto-merge
- rights_status unknown must not publish

## Schema v0.2 gaps to close next (after GitHub, before DDL)

- Split capacity scope (project/phase) from status (planned/operating)
- License identity so ERC and BOI do not collide
- Append-only review events (not only latest reviewed_by)
- Internal-use vs external-publish rights
- Canonical invalidation when evidence is rejected/superseded or rights change
- Fetch failures without a raw_record (e.g. HTTP 404)
- Predicate registry: predicate, value shape, unit, subject kind, canonical field_key
- Ingestion contract: extractor_version + subject_external_key resolution

## Suggested stack (not installed yet)

PostgreSQL + PostGIS, Python + FastAPI, SQLAlchemy + Alembic, Pydantic, S3-compatible private object storage, server-rendered HTML + HTMX, CLI import, pytest against real Postgres/PostGIS, Docker Compose.

## Continue prompt (paste into a new session)

```
Continue Energy Project Intelligence from /opt/data/docs/energy-project-intelligence/.
Read handoff.md and status.json first. Do not re-litigate MVP scope.
Current next step: close schema v0.2 before any migration.
Every status change MUST update https://enerise.sprees.net/ then sync docs/reference/. Never commit secrets.
User prefers Thai for generated articles; this project docs may stay bilingual but UI copy for the user should be Thai when talking in chat.
```

## Verification already done for this step

See index.html “สถานะเครื่อง” and “เข้าถึงเอกสาร”. Update `status.json` when GitHub clone, Docker, or schema version changes.
