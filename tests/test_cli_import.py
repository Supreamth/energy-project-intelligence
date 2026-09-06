from __future__ import annotations

import json
import uuid
from pathlib import Path

import psycopg

from energy_intelligence.cli import main

DSN = "postgresql://hermes@127.0.0.1:55432/intelligence"


def test_cli_import_creates_pending_evidence(tmp_path: Path, monkeypatch):
    key = f"cli-{uuid.uuid4()}"
    contract = {
        "schema_version": "0.2",
        "source_code": "demo_manual",
        "external_key": key,
        "extractor_version": "manual-0.2.0",
        "fetched_at": "2026-09-06T09:00:00Z",
        "payload": {"uri": "inline", "sha256": "pending", "content_type": "application/json"},
        "assertions": [
            {
                "extraction_key": "phase-a-it-load",
                "subject_external_key": f"{key}:phase-a",
                "predicate": "capacity.dc_it_load.phase.planned",
                "value": {"value": 40, "unit": "MW", "scope": "phase", "capacity_status": "planned"},
                "excerpt": "Phase A planned IT load 40 MW",
                "locator": {"json_path": "$.phase_a.it_load"},
                "review_status": "pending",
            }
        ],
    }
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(contract), encoding="utf-8")
    monkeypatch.setenv("OBJECT_STORE_DIR", str(tmp_path / "objects"))
    rc = main(["import", str(path)])
    assert rc == 0
    with psycopg.connect(DSN) as conn:
        status = conn.execute(
            """
            SELECT ev.review_status FROM intelligence.evidence ev
            JOIN intelligence.raw_records r ON r.id = ev.raw_record_id
            WHERE r.external_key = %s
            """,
            (key,),
        ).fetchone()
    assert status == ("pending",)
