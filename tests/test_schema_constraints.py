from __future__ import annotations

import os
import uuid

import psycopg
import pytest

from energy_intelligence.storage import LocalObjectStore

DSN = os.environ.get("EPI_DSN", "postgresql://hermes@127.0.0.1:55432/intelligence")


def db():
    return psycopg.connect(DSN)


@pytest.fixture
def conn():
    with db() as c:
        c.autocommit = False
        yield c
        c.rollback()


def uid() -> uuid.UUID:
    return uuid.uuid4()


def test_postgis_available():
    with db() as c:
        v = c.execute("SELECT PostGIS_Version()").fetchone()[0]
        assert "3." in v or v


def test_zero_capacity_rejected(conn):
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            """
            INSERT INTO intelligence.capacity_facts
              (id, subject_entity_id, metric, value_mw, scope, capacity_status, evidence_id)
            VALUES (%s, %s, 'dc_it_load', 0, 'phase', 'planned', %s)
            """,
            (uid(), uid(), uid()),
        )


def test_wrong_entity_kind_rejected(conn):
    eid = uid()
    conn.execute(
        "INSERT INTO intelligence.entities(id, kind) VALUES (%s, 'project')",
        (eid,),
    )
    with pytest.raises(Exception):
        conn.execute(
            """
            INSERT INTO intelligence.organizations(entity_id, legal_name, country_code)
            VALUES (%s, 'X', 'TH')
            """,
            (eid,),
        )


def test_fetch_failure_without_raw(conn):
    source_id, run_id, event_id = uid(), uid(), uid()
    conn.execute(
        """
        INSERT INTO intelligence.sources(id, code, name, base_url, access_method)
        VALUES (%s, %s, 'demo', 'https://example.invalid', 'manual')
        """,
        (source_id, f"src-{source_id}"),
    )
    conn.execute(
        """
        INSERT INTO intelligence.ingestion_runs(
          id, source_id, idempotency_key, connector_version, status
        ) VALUES (%s, %s, %s, 'manual-0.2.0', 'failed')
        """,
        (run_id, source_id, f"run-{run_id}"),
    )
    conn.execute(
        """
        INSERT INTO intelligence.fetch_events(
          id, source_id, run_id, raw_record_id, http_status, error_class
        ) VALUES (%s, %s, %s, NULL, 404, 'http_4xx')
        """,
        (event_id, source_id, run_id),
    )
    n = conn.execute(
        "SELECT count(*) FROM intelligence.fetch_events WHERE id = %s AND raw_record_id IS NULL",
        (event_id,),
    ).fetchone()[0]
    assert n == 1


def test_ingestion_cannot_write_canonical():
    with db() as c:
        c.autocommit = True
        c.execute("SET ROLE epi_ingestion")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute(
                """
                INSERT INTO intelligence.canonical_selections(
                  id, subject_entity_id, field_key, evidence_id, selected_by, reason
                ) VALUES (%s, %s, 'capacity.dc_it_load.phase.planned', %s, 'ing', 'no')
                """,
                (uid(), uid(), uid()),
            )
        c.execute("RESET ROLE")


def test_object_store_roundtrip(tmp_path):
    store = LocalObjectStore(tmp_path)
    meta = store.put("demo_manual", b'{"ok":true}', "application/json")
    assert len(meta["sha256"]) == 64
    assert store.get("demo_manual", meta["sha256"]) == b'{"ok":true}'
