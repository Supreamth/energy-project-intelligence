# Energy Project Intelligence

Thailand Energy & Digital Infrastructure Intelligence — evidence-backed solar farms and data centers in Thailand.

**Live reference (login required):** https://enerise.sprees.net/

Local clone: `/opt/data/workspace/energy-project-intelligence`

## Current phase

Foundation is up on this machine: PostgreSQL 18.6 + PostGIS 3.6, schema v0.2 migrated, DB roles, local object store. Next: manual ingestion.

Docker is not available here; `docker-compose.yml` is for a later host. Postgres runs user-space:

```bash
./scripts/start_postgres.sh
uv sync --extra dev
uv run alembic upgrade head
uv run pytest -v
```

DB: `127.0.0.1:55432` database `intelligence`. Data dir `var/` and `.conda/` are gitignored.

## Rule for every change

1. Update `/opt/data/docs/energy-project-intelligence/` so https://enerise.sprees.net/ stays current, including the Next prompt.
2. Copy public docs into `docs/reference/`.
3. Never commit secrets, `auth.json`, `.env`, `var/`, `.conda/`, `.venv/`.
