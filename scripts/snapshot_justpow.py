from pathlib import Path

import psycopg

from energy_intelligence.catalog import upsert_sources
from energy_intelligence.ingest import import_snapshot
from energy_intelligence.storage import LocalObjectStore

store = LocalObjectStore("var/objects")
with psycopg.connect("postgresql://hermes@127.0.0.1:55432/intelligence") as conn:
    upsert_sources(conn)
    page = import_snapshot(
        conn,
        store,
        source_code="justpow_plants",
        external_key="page-dec2567",
        payload=Path("/tmp/jp2.html").read_bytes(),
        content_type="text/html; charset=utf-8",
        extractor_version="justpow-page-0.1",
        source_url="https://justpow.co/database-powerplants-thailand/",
    )
    xlsx = import_snapshot(
        conn,
        store,
        source_code="justpow_plants",
        external_key="xlsx-uptoDEC2567",
        payload=Path("/tmp/justpow-plants.xlsx").read_bytes(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        extractor_version="justpow-xlsx-0.1",
        source_url="https://justpow.co/wp-content/uploads/2024/04/powerplant-database-uptoDEC2567.xlsx",
    )
    conn.commit()
    print("page", page.raw_created, page.raw_record_id)
    print("xlsx", xlsx.raw_created, xlsx.raw_record_id)
