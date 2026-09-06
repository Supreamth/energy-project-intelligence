from __future__ import annotations

from pathlib import Path
import uuid

import psycopg

from energy_intelligence.catalog import load_sources, upsert_sources
from energy_intelligence.catalog_html import render_sources

DSN = "postgresql://hermes@127.0.0.1:55432/intelligence"


def test_catalog_includes_erc_manual_first():
    rows = load_sources()
    erc = next(r for r in rows if r["code"] == "erc_licensees")
    assert erc["access_method"] == "web"
    assert erc["connection"]["mode"] == "manual_first"
    assert erc["enabled"] is False
    assert "ไม่สมมติว่ามี bulk API" in erc["connection"]["how"]


def test_sources_page_lists_connection_method():
    html = render_sources().decode()
    assert "https://www.erc.or.th/th/licensees/" in html
    assert "คัดลอกด้วยมือก่อน" in html
    assert "ไม่สมมติว่ามี bulk API" in html
    for row in load_sources():
        assert f'action="/sources/{row["code"]}/upload"' in html
    assert html.count('type="file"') == len(load_sources())
    assert html.count('type="submit"') == len(load_sources())


def test_upsert_sources_into_database():
    rows = load_sources()
    with psycopg.connect(DSN) as conn:
        upsert_sources(conn, rows)
        conn.commit()
        code, method, enabled = conn.execute(
            "SELECT code, access_method, enabled FROM intelligence.sources WHERE code = 'erc_licensees'"
        ).fetchone()
    assert code == "erc_licensees"
    assert method == "web"
    assert enabled is False


def test_manual_upload_known_source_and_reject_unknown(tmp_path: Path):
    from energy_intelligence.catalog import save_manual_upload
    from energy_intelligence.storage import LocalObjectStore

    store = LocalObjectStore(tmp_path)
    key = f"hub-{uuid.uuid4().hex}.html"
    payload = f"erc-hub-demo-{key}".encode()
    with psycopg.connect(DSN) as conn:
        first = save_manual_upload(
            conn, store, source_code="erc_licensees", filename=key, payload=payload, content_type="text/html"
        )
        conn.commit()
        second = save_manual_upload(
            conn, store, source_code="erc_licensees", filename=key, payload=payload, content_type="text/html"
        )
        conn.commit()
        try:
            save_manual_upload(
                conn, store, source_code="not_a_source", filename="x.bin", payload=b"x", content_type="application/octet-stream"
            )
            raised = False
        except ValueError:
            raised = True
            conn.rollback()
    assert first.raw_created is True
    assert second.raw_created is False
    assert raised is True
