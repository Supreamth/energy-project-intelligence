from __future__ import annotations

import uuid
from pathlib import Path

import psycopg
import pytest

from energy_intelligence.ingest import import_contract
from energy_intelligence.review import accept_evidence, select_canonical
from energy_intelligence.storage import LocalObjectStore

DSN = "postgresql://hermes@127.0.0.1:55432/intelligence"


def _contract(key: str, mw: int) -> dict:
    return {
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
                "value": {"value": mw, "unit": "MW", "scope": "phase", "capacity_status": "planned"},
                "excerpt": f"Phase A planned IT load {mw} MW",
                "locator": {"json_path": "$.phase_a.it_load"},
                "review_status": "pending",
            }
        ],
    }


def _phase(conn) -> uuid.UUID:
    project_id, site_id, phase_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    conn.execute("INSERT INTO intelligence.entities(id, kind) VALUES (%s, 'project')", (project_id,))
    conn.execute(
        "INSERT INTO intelligence.projects(entity_id, name_en, project_type) VALUES (%s, 'Demo', 'data_center')",
        (project_id,),
    )
    conn.execute("INSERT INTO intelligence.entities(id, kind) VALUES (%s, 'site')", (site_id,))
    conn.execute(
        "INSERT INTO intelligence.sites(entity_id, project_id, label) VALUES (%s, %s, 'A')",
        (site_id, project_id),
    )
    conn.execute("INSERT INTO intelligence.entities(id, kind) VALUES (%s, 'phase')", (phase_id,))
    conn.execute(
        "INSERT INTO intelligence.phases(entity_id, site_id, phase_key, label) VALUES (%s, %s, 'A', 'Phase A')",
        (phase_id, site_id),
    )
    return phase_id


def test_pending_evidence_cannot_be_canonical(tmp_path: Path):
    key = f"rev-{uuid.uuid4()}"
    store = LocalObjectStore(tmp_path)
    with psycopg.connect(DSN) as conn:
        phase_id = _phase(conn)
        imported = import_contract(conn, store, _contract(key, 40))
        conn.execute(
            "UPDATE intelligence.evidence SET subject_entity_id = %s WHERE raw_record_id = %s",
            (phase_id, imported.raw_record_id),
        )
        ev_id = conn.execute(
            "SELECT id FROM intelligence.evidence WHERE raw_record_id = %s",
            (imported.raw_record_id,),
        ).fetchone()[0]
        with pytest.raises(ValueError, match="accepted"):
            select_canonical(
                conn,
                evidence_id=ev_id,
                field_key="capacity.dc_it_load.phase.planned",
                actor="tester",
                reason="should fail",
            )
        conn.rollback()


def test_conflicting_loads_coexist_and_one_canonical(tmp_path: Path):
    key = f"rev-{uuid.uuid4()}"
    store = LocalObjectStore(tmp_path)
    with psycopg.connect(DSN) as conn:
        phase_id = _phase(conn)
        a = import_contract(conn, store, _contract(key, 40))
        b = import_contract(conn, store, _contract(key, 50))
        conn.execute(
            "UPDATE intelligence.evidence SET subject_entity_id = %s WHERE raw_record_id IN (%s, %s)",
            (phase_id, a.raw_record_id, b.raw_record_id),
        )
        ids = [
            row[0]
            for row in conn.execute(
                """
                SELECT ev.id FROM intelligence.evidence ev
                JOIN intelligence.raw_records r ON r.id = ev.raw_record_id
                WHERE r.external_key = %s
                ORDER BY ev.value_json->>'value'
                """,
                (key,),
            )
        ]
        forty, fifty = ids
        accept_evidence(conn, evidence_id=forty, actor="tester", reason="matches owner PDF")
        accept_evidence(conn, evidence_id=fifty, actor="tester", reason="keep conflict visible")
        select_canonical(
            conn,
            evidence_id=forty,
            field_key="capacity.dc_it_load.phase.planned",
            actor="tester",
            reason="prefer owner disclosure 40 MW",
        )
        ev_n = conn.execute(
            "SELECT count(*) FROM intelligence.evidence WHERE subject_entity_id = %s",
            (phase_id,),
        ).fetchone()[0]
        current = conn.execute(
            """
            SELECT evidence_id FROM intelligence.canonical_selections
            WHERE subject_entity_id = %s AND superseded_at IS NULL
            """,
            (phase_id,),
        ).fetchone()[0]
        conn.commit()
    assert ev_n == 2
    assert current == forty
