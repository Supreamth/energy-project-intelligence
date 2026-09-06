import psycopg

from energy_intelligence.catalog import upsert_sources
from energy_intelligence.coverage import coverage_report
from energy_intelligence.operators import apply_operator_research

with psycopg.connect("postgresql://hermes@127.0.0.1:55432/intelligence") as conn:
    upsert_sources(conn)
    print("apply", apply_operator_research(conn))
    conn.commit()
    report = coverage_report(conn)
    solar = report["types"]["solar_farm"]
    print("solar n", solar["n"], "required", solar["required_score"])
    for slot in solar["slots"]:
        if slot["key"] in {"site.point", "organization.website", "project_parties"}:
            print(f"  {slot['pct']:6.1f}% {slot['present']:4d}/{slot['n']} {slot['key']}")
