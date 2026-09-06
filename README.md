# Energy Project Intelligence

Thailand Energy & Digital Infrastructure Intelligence — track solar farms and data centers in Thailand with evidence-backed facts.

**Live reference (login required):** https://enerise.sprees.net/

Local clone: `/opt/data/workspace/energy-project-intelligence`  
Live docs origin: `/opt/data/docs/energy-project-intelligence/` (served with HTTP Basic Auth)

This repository is the code and documentation source. Schema v0.1 is a design contract only. Application code, migrations, and collectors are not in yet.

## Rule for every change

1. Update the live site files under `/opt/data/docs/energy-project-intelligence/` so https://enerise.sprees.net/ stays current.
2. Copy the same public docs into `docs/reference/`.
3. Never commit secrets, `auth.json`, passwords, or `.env`.

Read `AGENTS.md` and `docs/reference/handoff.md` before continuing work.

## Current phase

0 — Reference docs live. Local git clone exists. First push waits on a GitHub token on this machine. Next product step after push: schema v0.2.

## MVP

Open one project → company, site, capacity/load, status, dates → original evidence for each value → conflicting values and why one was chosen.

Out of scope for now: satellite imagery, Solar Portfolio, auto-merge, LLM-approved facts, Kubernetes, public API.
