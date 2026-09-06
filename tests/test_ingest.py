from __future__ import annotations

import json
import uuid
from pathlib import Path

import psycopg
import pytest

from energy_intelligence.ingest import import_contract
from energy_intelligence.storage import LocalObjectStore

DSN = "postgresql://hermes@127.0.0.1:55432/intelligence"


def _contract(external_key: str, it_load: int = 40) -> dict:
    return {
        "schema_version": "0.2",
        "source_code": "demo_manual",
        "external_key": external_key,
        "extractor_version": "manual-0.2.0",
        "fetched_at": "2026-09-06T09:00:00Z",
        "payload": {
            "uri": "inline",
            "sha256": "pending",
            "content_type": "application/json",
        },
        "assertions": [
            {
                "extraction_key": "phase-a-it-load",
                "subject_external_key": f"{external_key}:phase-a",
                "predicate": "capacity.dc_it_load.phase.planned",
                "value": {
                    "value": it_load,
                    "unit": "MW",
                    "scope": "phase",
                    "capacity_status": "planned",
                },
                "excerpt": f"Phase A planned IT load {it_load} MW",
                "locator": {"json_path": "$.phase_a.it_load"},
                "review_status": "pending",
            }
        ],
    }


def test_same_snapshot_does_not_duplicate_raw_but_adds_fetch_event(tmp_path: Path):
    key = f"demo-{uuid.uuid4()}"
    contract = _contract(key)
    store = LocalObjectStore(tmp_path)
    with psycopg.connect(DSN) as conn:
        first = import_contract(conn, store, contract)
        conn.commit()
        second = import_contract(conn, store, contract)
        conn.commit()
        raw_n = conn.execute(
            "SELECT count(*) FROM intelligence.raw_records WHERE external_key = %s",
            (key,),
        ).fetchone()[0]
        fetch_n = conn.execute(
            """
            SELECT count(*) FROM intelligence.fetch_events e
            JOIN intelligence.raw_records r ON r.id = e.raw_record_id
            WHERE r.external_key = %s
            """,
            (key,),
        ).fetchone()[0]
        ev_n = conn.execute(
            """
            SELECT count(*) FROM intelligence.evidence ev
            JOIN intelligence.raw_records r ON r.id = ev.raw_record_id
            WHERE r.external_key = %s
            """,
            (key,),
        ).fetchone()[0]
    assert first.raw_created is True
    assert second.raw_created is False
    assert first.raw_record_id == second.raw_record_id
    assert raw_n == 1
    assert fetch_n == 2
    assert ev_n == 1


def test_changed_snapshot_creates_new_raw_and_keeps_old_evidence(tmp_path: Path):
    key = f"demo-{uuid.uuid4()}"
    store = LocalObjectStore(tmp_path)
    with psycopg.connect(DSN) as conn:
        first = import_contract(conn, store, _contract(key, 40))
        conn.commit()
        second = import_contract(conn, store, _contract(key, 50))
        conn.commit()
        raw_n = conn.execute(
            "SELECT count(*) FROM intelligence.raw_records WHERE external_key = %s",
            (key,),
        ).fetchone()[0]
        ev_n = conn.execute(
            """
            SELECT count(*) FROM intelligence.evidence ev
            JOIN intelligence.raw_records r ON r.id = ev.raw_record_id
            WHERE r.external_key = %s
            """,
            (key,),
        ).fetchone()[0]
        old_still = conn.execute(
            "SELECT count(*) FROM intelligence.evidence WHERE raw_record_id = %s",
            (first.raw_record_id,),
        ).fetchone()[0]
    assert first.raw_record_id != second.raw_record_id
    assert raw_n == 2
    assert ev_n == 2
    assert old_still == 1


def test_unknown_predicate_rejected(tmp_path: Path):
    key = f"demo-{uuid.uuid4()}"
    contract = _contract(key)
    contract["assertions"][0]["predicate"] = "capacity.made_up.phase.planned"
    store = LocalObjectStore(tmp_path)
    with psycopg.connect(DSN) as conn:
        with pytest.raises(ValueError, match="unknown predicate"):
            import_contract(conn, store, contract)
        conn.rollback()
