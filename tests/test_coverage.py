from __future__ import annotations

import psycopg

from energy_intelligence.coverage import coverage_report

DSN = "postgresql://hermes@127.0.0.1:55432/intelligence"


def test_coverage_report_has_solar_slots():
    with psycopg.connect(DSN) as conn:
        report = coverage_report(conn)
    solar = report["types"]["solar_farm"]
    assert solar["n"] >= 1
    names = {s["key"] for s in solar["slots"]}
    assert "site.point" in names
    assert "canonical.regulatory.erc.generation" in names
    assert "canonical.capacity.solar_ac.project.operating" in names
    point = next(s for s in solar["slots"] if s["key"] == "site.point")
    assert point["present"] == 0
    erc = next(s for s in solar["slots"] if s["key"] == "canonical.regulatory.erc.generation")
    assert erc["present"] >= 1
    dc = report["types"]["data_center"]
    assert "canonical.capacity.dc_it_load.phase.planned" in {s["key"] for s in dc["slots"]}
