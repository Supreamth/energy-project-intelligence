from __future__ import annotations

import uuid
from pathlib import Path

import psycopg
import pytest

from energy_intelligence.ingest import import_contract
from energy_intelligence.product import get_project, list_projects
from energy_intelligence.product_html import render_detail
from energy_intelligence.review import accept_evidence, select_canonical
from energy_intelligence.storage import LocalObjectStore

DSN = "postgresql://hermes@127.0.0.1:55432/intelligence"


def _setup(conn, store, key: str):
    project_id, site_id, phase_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    conn.execute("INSERT INTO intelligence.entities(id, kind) VALUES (%s, 'project')", (project_id,))
    conn.execute(
        "INSERT INTO intelligence.projects(entity_id, name_en, project_type) VALUES (%s, %s, 'data_center')",
        (project_id, f"Campus {key[:8]}"),
    )
    conn.execute("INSERT INTO intelligence.entities(id, kind) VALUES (%s, 'site')", (site_id,))
    conn.execute(
        "INSERT INTO intelligence.sites(entity_id, project_id, label) VALUES (%s, %s, 'Main')",
        (site_id, project_id),
    )
    conn.execute("INSERT INTO intelligence.entities(id, kind) VALUES (%s, 'phase')", (phase_id,))
    conn.execute(
        "INSERT INTO intelligence.phases(entity_id, site_id, phase_key, label) VALUES (%s, %s, 'A', 'Phase A')",
        (phase_id, site_id),
    )
    def contract(mw):
        return {
            "schema_version": "0.2",
            "source_code": "demo_manual",
            "external_key": key,
            "extractor_version": "manual-0.2.0",
            "fetched_at": "2026-09-06T09:00:00Z",
            "payload": {"uri": "inline", "sha256": "pending", "content_type": "application/json"},
            "assertions": [{
                "extraction_key": "phase-a-it-load",
                "subject_external_key": f"{key}:phase-a",
                "predicate": "capacity.dc_it_load.phase.planned",
                "value": {"value": mw, "unit": "MW", "scope": "phase", "capacity_status": "planned"},
                "excerpt": f"{mw} MW",
                "locator": {"json_path": "$.it"},
                "review_status": "pending",
            }],
        }
    a = import_contract(conn, store, contract(40))
    b = import_contract(conn, store, contract(50))
    conn.execute(
        "UPDATE intelligence.evidence SET subject_entity_id = %s WHERE raw_record_id IN (%s, %s)",
        (phase_id, a.raw_record_id, b.raw_record_id),
    )
    rows = list(conn.execute(
        """
        SELECT ev.id, ev.value_json->>'value' FROM intelligence.evidence ev
        WHERE ev.subject_entity_id = %s ORDER BY ev.value_json->>'value'
        """,
        (phase_id,),
    ))
    forty = rows[0][0]
    fifty = rows[1][0]
    accept_evidence(conn, evidence_id=forty, actor="t", reason="owner")
    accept_evidence(conn, evidence_id=fifty, actor="t", reason="alt")
    select_canonical(
        conn,
        evidence_id=forty,
        field_key="capacity.dc_it_load.phase.planned",
        actor="t",
        reason="prefer 40",
    )
    return project_id, forty, fifty


def test_product_lists_only_projects_and_canonical_capacity(tmp_path: Path):
    store = LocalObjectStore(tmp_path)
    key = f"prod-{uuid.uuid4()}"
    with psycopg.connect(DSN) as conn:
        project_id, forty, fifty = _setup(conn, store, key)
        conn.commit()
        listed = list_projects(conn, project_type="data_center")
        detail = get_project(conn, project_id)
    ids = {row["id"] for row in listed}
    assert str(project_id) in ids
    assert detail["name"] == f"Campus {key[:8]}"
    assert detail["project_type"] == "data_center"
    cap = detail["capacity"][0]
    assert cap["value"] == 40
    assert cap["scope"] == "phase"
    assert cap["metric"] == "dc_it_load"
    assert cap["evidence_id"] == str(forty)
    assert str(fifty) in {c["evidence_id"] for c in detail["conflicts"]}
    assert detail["sites"][0]["coordinates"] is None
    with psycopg.connect(DSN) as conn:
        html = render_detail(conn, project_id).decode()
    assert "openstreetmap.org" not in html
    assert "ไม่ทราบพิกัด" in html


def test_site_coordinates_only_when_point_exists(tmp_path: Path):
    store = LocalObjectStore(tmp_path)
    key = f"geo-{uuid.uuid4()}"
    with psycopg.connect(DSN) as conn:
        project_id, _, _ = _setup(conn, store, key)
        conn.execute(
            """
            UPDATE intelligence.sites
            SET point = ST_SetSRID(ST_MakePoint(100.5018, 13.7563), 4326),
                location_method = 'source_excerpt'
            WHERE project_id = %s
            """,
            (project_id,),
        )
        conn.commit()
        detail = get_project(conn, project_id)
    coords = detail["sites"][0]["coordinates"]
    assert coords is not None
    assert round(coords["lon"], 4) == 100.5018
    assert round(coords["lat"], 4) == 13.7563
    with psycopg.connect(DSN) as conn:
        html = render_detail(conn, project_id).decode()
    assert "openstreetmap.org" in html
    assert "ไม่ทราบพิกัด" not in html
