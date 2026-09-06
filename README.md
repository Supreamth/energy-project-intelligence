# Energy Project Intelligence

Thailand Energy & Digital Infrastructure Intelligence — evidence-backed solar farms and data centers in Thailand.

**Live reference (login required):** https://enerise.sprees.net/

Local clone: `/opt/data/workspace/energy-project-intelligence`

## Current phase

Foundation is up. Manual ingestion CLI works:

```bash
./scripts/start_postgres.sh
uv sync --extra dev
uv run python -m energy_intelligence import fixtures/demo_phase_a.json
uv run pytest -v
```

Same file twice: one raw row, two fetch events, evidence stays pending. Next: review UI.

DB: `127.0.0.1:55432` database `intelligence`. Data dir `var/` and `.conda/` are gitignored.

## Rule for every change

1. Update `/opt/data/docs/energy-project-intelligence/` so https://enerise.sprees.net/ stays current, including the Next prompt.
2. Copy public docs into `docs/reference/`.
3. Never commit secrets, `auth.json`, `.env`, `var/`, `.conda/`, `.venv/`.
