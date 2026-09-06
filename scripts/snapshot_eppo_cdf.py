from pathlib import Path

import psycopg

from energy_intelligence.catalog import upsert_sources
from energy_intelligence.ingest import import_snapshot
from energy_intelligence.storage import LocalObjectStore

store = LocalObjectStore("var/objects")
files = [
    (
        Path("/tmp/eppo-spp.html"),
        "cdf-spp-index",
        "https://www2.eppo.go.th/cdf/power_plant_SPP.html",
    ),
    (
        Path("/tmp/eppo-vspp.html"),
        "cdf-vspp-index",
        "https://www2.eppo.go.th/cdf/power_plant_VSPP.html",
    ),
]
with psycopg.connect("postgresql://hermes@127.0.0.1:55432/intelligence") as conn:
    upsert_sources(conn)
    for path, key, url in files:
        snap = import_snapshot(
            conn,
            store,
            source_code="eppo_cdf_spp",
            external_key=key,
            payload=path.read_bytes(),
            content_type="text/html; charset=utf-8",
            extractor_version="eppo-cdf-index-0.1",
            source_url=url,
        )
        print(key, snap.raw_created, snap.raw_record_id)
    conn.commit()
