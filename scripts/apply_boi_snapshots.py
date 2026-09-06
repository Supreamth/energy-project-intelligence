from pathlib import Path

import psycopg

from energy_intelligence.boi_pdf import extract_boi_solar
from energy_intelligence.catalog import upsert_sources
from energy_intelligence.coverage import coverage_report
from energy_intelligence.ingest import import_snapshot, record_fetch_failure
from energy_intelligence.storage import LocalObjectStore

DSN = "postgresql://hermes@127.0.0.1:55432/intelligence"
STORE = LocalObjectStore("var/objects")

FILES = [
    (
        Path("/tmp/boi-kn38.pdf"),
        "press-KN38NO153K63",
        "https://www.boi.go.th/upload/content/KN38NO153K63_5d9bf603d4a57.pdf",
    ),
    (
        Path("/tmp/boi-dec2559.pdf"),
        "labor-demand-dec-2559",
        "https://www.boi.go.th/upload/content/company/"
        "%E0%B8%A3%E0%B8%B2%E0%B8%A2%E0%B8%8A%E0%B8%B7%E0%B9%88%E0%B8%AD%E0%B8%9A%E0%B8%A3%E0%B8%B4%E0%B8%A9%E0%B8%B1%E0%B8%97%E0%B8%97%E0%B8%B5%E0%B9%88%E0%B8%A1%E0%B8%B5%E0%B8%84%E0%B8%A7%E0%B8%B2%E0%B8%A1%E0%B8%95%E0%B9%89%E0%B8%AD%E0%B8%87%E0%B8%81%E0%B8%B2%E0%B8%A3%E0%B9%81%E0%B8%A3%E0%B8%87%E0%B8%87%E0%B8%B2%E0%B8%99%20%20%E0%B9%80%E0%B8%94%E0%B8%B7%E0%B8%AD%E0%B8%99%E0%B8%98%E0%B8%B1%E0%B8%99%E0%B8%A7%E0%B8%B2%E0%B8%84%E0%B8%A1%202559_83962.pdf",
    ),
]

with psycopg.connect(DSN) as conn:
    upsert_sources(conn)
    record_fetch_failure(
        conn,
        source_code="boi_promoted",
        error_class="other",
        error_summary={
            "url": "https://www.boi.go.th/index.php?page=form_promoted_companies",
            "bytes": 212,
            "note": "Incapsula challenge, no Excel table",
        },
    )
    for path, key, url in FILES:
        snap = import_snapshot(
            conn,
            STORE,
            source_code="boi_promoted",
            external_key=key,
            payload=path.read_bytes(),
            content_type="application/pdf",
            extractor_version="boi-pdf-solar-0.1",
            source_url=url,
        )
        extracted = extract_boi_solar(conn, STORE, raw_record_id=snap.raw_record_id)
        print(key, "raw_created", snap.raw_created, "id", snap.raw_record_id, extracted)
    conn.commit()
    boi = conn.execute(
        """
        SELECT count(*), count(subject_entity_id)
        FROM intelligence.evidence
        WHERE predicate='regulatory.boi.promotion'
        """
    ).fetchone()
    print("evidence", boi)
    slot = next(
        s
        for s in coverage_report(conn)["types"]["solar_farm"]["slots"]
        if s["key"] == "canonical.regulatory.boi.promotion"
    )
    print("canonical boi", slot)
