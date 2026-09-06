# AI Handoff — Energy Project Intelligence

Updated: 2026-09-06 (UTC).

## Current truth

- Live docs: https://enerise.sprees.net/
- Git clone: `/opt/data/workspace/energy-project-intelligence`
- Postgres 18.6 + PostGIS 3.6 at 127.0.0.1:55432 (`./scripts/start_postgres.sh`)
- Schema v0.2 migrated
- Manual import: `python -m energy_intelligence import fixtures/demo_phase_a.json`
- Same snapshot: 1 raw, extra fetch event, evidence stays pending
- Changed snapshot: new raw, old evidence kept
- Next: Review UI + canonical selection

Copy Next prompt from https://enerise.sprees.net/#next-prompt
