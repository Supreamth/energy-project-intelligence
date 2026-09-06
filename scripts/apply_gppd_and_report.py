from pathlib import Path

import psycopg

from energy_intelligence.catalog import upsert_sources
from energy_intelligence.coverage import coverage_report
from energy_intelligence.gppd import apply_gppd_coordinates
from energy_intelligence.ingest import record_fetch_failure
from energy_intelligence.storage import LocalObjectStore

csv_bytes = Path("/tmp/gppd.csv").read_bytes()
store = LocalObjectStore("var/objects")
with psycopg.connect("postgresql://hermes@127.0.0.1:55432/intelligence") as conn:
    upsert_sources(conn)
    print("gppd", apply_gppd_coordinates(conn, store, csv_bytes))
    record_fetch_failure(
        conn,
        source_code="boi_promoted",
        error_class="other",
        error_summary={
            "url": "https://www.boi.go.th/index.php?language=en&page=form_promoted_companies",
            "bytes": 212,
            "note": "bot wall, no company table",
        },
    )
    conn.commit()
    report = coverage_report(conn)
    for kind, data in report["types"].items():
        print("TYPE", kind, "n", data["n"], "required", data["required_score"])
        for slot in data["slots"]:
            print(f"  {slot['pct']:6.1f}% {slot['present']:4d}/{slot['n']} {slot['key']}")
