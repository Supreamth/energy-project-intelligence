from __future__ import annotations

from pathlib import Path
import uuid

import psycopg

from energy_intelligence.ingest import import_snapshot, record_fetch_failure
from energy_intelligence.storage import LocalObjectStore

DSN = "postgresql://hermes@127.0.0.1:55432/intelligence"
HTML = "<html><title>ERC licensees hub</title><body>registry generation</body></html>".encode("utf-8")


def test_html_snapshot_idempotent(tmp_path: Path):
    store = LocalObjectStore(tmp_path)
    key = f"public-hub-test-{uuid.uuid4()}"
    with psycopg.connect(DSN) as conn:
        first = import_snapshot(
            conn,
            store,
            source_code="erc_licensees",
            external_key=key,
            payload=HTML,
            content_type="text/html; charset=utf-8",
            source_url="https://www.erc.or.th/th/licensees/",
            extractor_version="erc-hub-html-0.1",
        )
        conn.commit()
        second = import_snapshot(
            conn,
            store,
            source_code="erc_licensees",
            external_key=key,
            payload=HTML,
            content_type="text/html; charset=utf-8",
            source_url="https://www.erc.or.th/th/licensees/",
            extractor_version="erc-hub-html-0.1",
        )
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
    assert first.raw_created is True
    assert second.raw_created is False
    assert raw_n == 1
    assert fetch_n == 2


def test_record_timeout_without_raw():
    with psycopg.connect(DSN) as conn:
        event_id = record_fetch_failure(
            conn,
            source_code="erc_licensees",
            error_class="timeout",
            error_summary={"url": "http://app04.erc.or.th/ELicense/Licenser/05_Reporting/504_ListLicensing_Columns_New.aspx?LicenseType=1"},
        )
        conn.commit()
        raw_id = conn.execute(
            "SELECT raw_record_id FROM intelligence.fetch_events WHERE id = %s",
            (event_id,),
        ).fetchone()[0]
    assert raw_id is None
