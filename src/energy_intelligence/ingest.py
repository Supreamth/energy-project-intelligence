"""Manual ingestion for schema v0.2 contracts."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from energy_intelligence.storage import LocalObjectStore

DEMO_SOURCE = {
    "code": "demo_manual",
    "name": "Demo manual import",
    "base_url": "https://example.invalid/demo",
    "access_method": "manual",
    "rights_status": "internal_only",
}


@dataclass
class ImportResult:
    raw_record_id: uuid.UUID
    run_id: uuid.UUID
    raw_created: bool
    evidence_inserted: int


def import_contract(conn, store: LocalObjectStore, contract: dict) -> ImportResult:
    if contract.get("schema_version") != "0.2":
        raise ValueError("schema_version must be 0.2")
    source_code = contract["source_code"]
    external_key = contract["external_key"]
    extractor_version = contract["extractor_version"]
    assertions = contract.get("assertions") or []
    _reject_zero_capacity(assertions)
    _require_predicates(conn, assertions)

    payload = json.dumps(contract, sort_keys=True, ensure_ascii=False).encode("utf-8")
    content_type = "application/json"
    stored = store.put(source_code, payload, content_type)
    source_id = _ensure_source(conn, source_code)
    run_id = uuid.uuid4()
    conn.execute(
        """
        INSERT INTO intelligence.ingestion_runs(
          id, source_id, idempotency_key, connector_version, status
        ) VALUES (%s, %s, %s, %s, 'running')
        """,
        (run_id, source_id, str(run_id), extractor_version),
    )
    raw_id, created = _upsert_raw(
        conn,
        source_id=source_id,
        external_key=external_key,
        sha256=stored["sha256"],
        uri=stored["uri"],
        content_type=content_type,
    )
    conn.execute(
        """
        INSERT INTO intelligence.fetch_events(
          id, source_id, run_id, raw_record_id, http_status
        ) VALUES (%s, %s, %s, %s, 200)
        """,
        (uuid.uuid4(), source_id, run_id, raw_id),
    )
    inserted = 0
    for assertion in assertions:
        cur = conn.execute(
            """
            INSERT INTO intelligence.evidence(
              id, raw_record_id, extraction_key, predicate, value_json,
              excerpt, locator, extractor_version, confidence, review_status
            ) VALUES (
              %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s, %s, 'pending'
            )
            ON CONFLICT (raw_record_id, extractor_version, extraction_key)
            DO NOTHING
            RETURNING id
            """,
            (
                uuid.uuid4(),
                raw_id,
                assertion["extraction_key"],
                assertion["predicate"],
                json.dumps(assertion["value"], ensure_ascii=False),
                assertion.get("excerpt"),
                json.dumps(assertion["locator"], ensure_ascii=False),
                extractor_version,
                assertion.get("confidence"),
            ),
        )
        if cur.fetchone():
            inserted += 1
    conn.execute(
        """
        UPDATE intelligence.ingestion_runs
        SET status = 'succeeded', ended_at = now(), fetched_count = 1
        WHERE id = %s
        """,
        (run_id,),
    )
    return ImportResult(
        raw_record_id=raw_id,
        run_id=run_id,
        raw_created=created,
        evidence_inserted=inserted,
    )


def _reject_zero_capacity(assertions: list[dict]) -> None:
    for assertion in assertions:
        if not str(assertion.get("predicate", "")).startswith("capacity."):
            continue
        value = assertion.get("value") or {}
        if value.get("value") == 0:
            raise ValueError("capacity value 0 is forbidden; omit the fact when unknown")


def _require_predicates(conn, assertions: list[dict]) -> None:
    for assertion in assertions:
        predicate = assertion["predicate"]
        row = conn.execute(
            """
            SELECT 1 FROM intelligence.predicate_registry
            WHERE registry_version = '0.2.0' AND predicate = %s AND enabled
            """,
            (predicate,),
        ).fetchone()
        if not row:
            raise ValueError(f"unknown predicate: {predicate}")


def _ensure_source(conn, source_code: str) -> uuid.UUID:
    row = conn.execute(
        "SELECT id FROM intelligence.sources WHERE code = %s",
        (source_code,),
    ).fetchone()
    if row:
        return row[0]
    source_id = uuid.uuid4()
    meta = DEMO_SOURCE if source_code == "demo_manual" else {
        "code": source_code,
        "name": source_code,
        "base_url": "https://example.invalid",
        "access_method": "manual",
        "rights_status": "internal_only",
    }
    conn.execute(
        """
        INSERT INTO intelligence.sources(
          id, code, name, base_url, access_method, rights_status, enabled
        ) VALUES (%s, %s, %s, %s, %s, %s, true)
        """,
        (
            source_id,
            meta["code"],
            meta["name"],
            meta["base_url"],
            meta["access_method"],
            meta["rights_status"],
        ),
    )
    return source_id


def _upsert_raw(conn, *, source_id, external_key, sha256, uri, content_type, source_url=None):
    raw_id = uuid.uuid4()
    row = conn.execute(
        """
        INSERT INTO intelligence.raw_records(
          id, source_id, external_key, payload_sha256, payload_uri, content_type, source_url
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id, external_key, payload_sha256)
        DO NOTHING
        RETURNING id
        """,
        (raw_id, source_id, external_key, sha256, uri, content_type, source_url),
    ).fetchone()
    if row:
        return row[0], True
    existing = conn.execute(
        """
        SELECT id FROM intelligence.raw_records
        WHERE source_id = %s AND external_key = %s AND payload_sha256 = %s
        """,
        (source_id, external_key, sha256),
    ).fetchone()
    return existing[0], False


def import_snapshot(
    conn,
    store: LocalObjectStore,
    *,
    source_code: str,
    external_key: str,
    payload: bytes,
    content_type: str,
    extractor_version: str,
    source_url: str | None = None,
) -> ImportResult:
    stored = store.put(source_code, payload, content_type)
    source_id = _ensure_source(conn, source_code)
    run_id = uuid.uuid4()
    conn.execute(
        """
        INSERT INTO intelligence.ingestion_runs(
          id, source_id, idempotency_key, connector_version, status
        ) VALUES (%s, %s, %s, %s, 'running')
        """,
        (run_id, source_id, str(run_id), extractor_version),
    )
    raw_id, created = _upsert_raw(
        conn,
        source_id=source_id,
        external_key=external_key,
        sha256=stored["sha256"],
        uri=stored["uri"],
        content_type=content_type,
        source_url=source_url,
    )
    conn.execute(
        """
        INSERT INTO intelligence.fetch_events(
          id, source_id, run_id, raw_record_id, http_status
        ) VALUES (%s, %s, %s, %s, 200)
        """,
        (uuid.uuid4(), source_id, run_id, raw_id),
    )
    conn.execute(
        """
        UPDATE intelligence.ingestion_runs
        SET status = 'succeeded', ended_at = now(), fetched_count = 1
        WHERE id = %s
        """,
        (run_id,),
    )
    return ImportResult(
        raw_record_id=raw_id,
        run_id=run_id,
        raw_created=created,
        evidence_inserted=0,
    )


def record_fetch_failure(
    conn,
    *,
    source_code: str,
    error_class: str,
    error_summary: dict | None = None,
    extractor_version: str = "erc-hub-html-0.1",
) -> uuid.UUID:
    source_id = _ensure_source(conn, source_code)
    run_id = uuid.uuid4()
    event_id = uuid.uuid4()
    conn.execute(
        """
        INSERT INTO intelligence.ingestion_runs(
          id, source_id, idempotency_key, connector_version, status,
          fetched_count, error_count, error_summary, ended_at
        ) VALUES (%s, %s, %s, %s, 'failed', 0, 1, %s::jsonb, now())
        """,
        (run_id, source_id, str(run_id), extractor_version, json.dumps(error_summary or {})),
    )
    conn.execute(
        """
        INSERT INTO intelligence.fetch_events(
          id, source_id, run_id, raw_record_id, error_class, error_summary
        ) VALUES (%s, %s, %s, NULL, %s, %s::jsonb)
        """,
        (event_id, source_id, run_id, error_class, json.dumps(error_summary or {})),
    )
    return event_id
