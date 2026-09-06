# AI Handoff — Energy Project Intelligence

Updated: 2026-09-06 (UTC). Read this file first, then `status.json`, then the live site.

## Current truth

- Live docs: https://enerise.sprees.net/
- Git clone: `/opt/data/workspace/energy-project-intelligence`
- Schema v0.2 is closed AND migrated on real PostgreSQL 18.6 + PostGIS 3.6 at `127.0.0.1:55432`
- Start DB: `scripts/start_postgres.sh` (user-space conda prefix `.conda/`, data in `var/pgdata`, not in git)
- Roles: `epi_migration`, `epi_ingestion`, `epi_review`, `epi_product_read`
- `epi_ingestion` cannot INSERT canonical_selections (pytest)
- Local object store: `src/energy_intelligence/storage.py`
- Docker daemon is unavailable; `docker-compose.yml` is present for later
- Next: manual ingestion end-to-end
- Update https://enerise.sprees.net/ and Next prompt on every change
- Never commit secrets, `var/`, `.conda/`, `.venv/`

## Ordered work

0–3 done. 4 Manual ingestion. 5 Review UI. 6 Product page.

Copy Next prompt from https://enerise.sprees.net/#next-prompt
