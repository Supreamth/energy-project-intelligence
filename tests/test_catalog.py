from __future__ import annotations

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
