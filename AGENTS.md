# Agent instructions — Energy Project Intelligence

## Always

1. Read `docs/reference/handoff.md` and `docs/reference/status.json` first.
2. After any status change, update the live website **in the same turn**:
   - https://enerise.sprees.net/
   - files in `/opt/data/docs/energy-project-intelligence/` (`index.html`, `handoff.md`, `status.json`)
   - then copy those three files into `docs/reference/`
3. Do not commit `/opt/data/home/.enerise/auth.json`, passwords, tokens, or `.env`.
4. Do not start collectors, satellite imagery, Solar Portfolio, Kubernetes, or LLM auto-approval.
5. Do not write migrations until schema v0.2 is closed. It is now closed; Foundation may implement it. Do not reopen v0.2 unless the user asks.
6. Keep https://enerise.sprees.net/#next-prompt and `next-prompt.txt` accurate whenever work stops or the next task changes.

## Layout

- Git working copy: `/opt/data/workspace/energy-project-intelligence`
- Live docs server: `/opt/data/docs/energy-project-intelligence/serve.py` on `127.0.0.1:8091`
- Public hostname: `enerise.sprees.net` via Cloudflare tunnel `loopen`

## Next work

Close schema v0.2 is done. Next is Foundation (Postgres+PostGIS + Alembic) without reopening v0.2.
