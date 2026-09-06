from __future__ import annotations

from pathlib import Path

import psycopg

from energy_intelligence.erc_csv import extract_solar_licenses
from energy_intelligence.ingest import import_snapshot
from energy_intelligence.storage import LocalObjectStore

DSN = "postgresql://hermes@127.0.0.1:55432/intelligence"


def test_extract_solar_only_skips_zero_and_biomass(tmp_path: Path):
    key = tmp_path.name
    csv_text = (
        "\ufeff"
        '"ชื่อผู้รับใบอนุญาต","ชื่อสถานประกอบกิจการ","จังหวัด","สำนักงานประจำเขต","เลขทะเบียนใบอนุญาต","วันที่ออกใบอนุญาต","ชนิดเชื้อเพลิงหลัก/แหล่งพลังงานต้นกำลัง","ชนิดเชื้อเพลิงเสริม","ขนาดกำลังการผลิต (MW)","ขนาดกำลังการผลิต (kVA)","ขนาดพิกัดแรงดัน (kV)","ปริมาณความต้องการพลังไฟฟ้าสูงสุด (MW)","วันที่เริ่มประกอบกิจการ (COD)"\r\n'
        f'"บริษัท เอ จำกัด","ฟาร์มเอ","นครราชสีมา","เขตที่ 03","กกพ TEST-{key}-0001","1 มกราคม 2568","พลังแสงอาทิตย์ (Solar Photovoltaic Power)"," ","10.000","10,000.00"," ","10.000","15 มกราคม 2568"\r\n'
        f'"บริษัท บี จำกัด","ฟาร์มบี","ชลบุรี","เขตที่ 04","กกพ TEST-{key}-0002","1 มกราคม 2568","พลังแสงอาทิตย์ (Solar Photovoltaic Power)"," ","5.500","5,500.00"," ","5.500"," "\r\n'
        f'"บริษัท ซี จำกัด","ฟาร์มซี","ระยอง","เขตที่ 04","กกพ TEST-{key}-0003","1 มกราคม 2568","พลังแสงอาทิตย์ (Solar Photovoltaic Power)"," ","0.000","0.00"," ","0.000"," "\r\n'
        f'"บริษัท ดี จำกัด","โรงชีวมวลดี","ขอนแก่น","เขตที่ 02","กกพ TEST-{key}-0004","1 มกราคม 2568","ชีวมวล (Biomass)"," ","20.000","20,000.00"," ","20.000","1 กุมภาพันธ์ 2560"\r\n'
    ).encode("utf-8")
    store = LocalObjectStore(tmp_path)
    aliases = [f"กกพ TEST-{key}-0001", f"กกพ TEST-{key}-0002", f"กกพ TEST-{key}-0003", f"กกพ TEST-{key}-0004"]
    with psycopg.connect(DSN) as conn:
        snap = import_snapshot(
            conn,
            store,
            source_code="erc_licensees",
            external_key=f"test-radgrid-{key}",
            payload=csv_text,
            content_type="text/csv",
            extractor_version="test",
            source_url="upload://erc_licensees/test.csv",
        )
        conn.commit()
        result = extract_solar_licenses(conn, store, raw_record_id=snap.raw_record_id)
        conn.commit()
        again = extract_solar_licenses(conn, store, raw_record_id=snap.raw_record_id)
        conn.commit()
        projects = conn.execute(
            """
            SELECT count(*) FROM intelligence.projects p
            JOIN intelligence.entity_aliases a ON a.entity_id = p.entity_id
            WHERE a.alias = ANY(%s)
            """,
            (aliases,),
        ).fetchone()[0]
        ev = list(
            conn.execute(
                """
                SELECT predicate, value_json, review_status FROM intelligence.evidence
                WHERE raw_record_id = %s ORDER BY extraction_key
                """,
                (snap.raw_record_id,),
            )
        )
        sites = conn.execute(
            """
            SELECT s.point IS NULL FROM intelligence.sites s
            JOIN intelligence.projects p ON p.entity_id = s.project_id
            JOIN intelligence.entity_aliases a ON a.entity_id = p.entity_id
            WHERE a.alias = %s
            """,
            (aliases[0],),
        ).fetchone()
    assert result.projects_created == 2
    assert result.evidence_inserted == 3
    assert again.evidence_inserted == 0
    assert projects == 2
    predicates = [row[0] for row in ev]
    assert predicates.count("regulatory.erc.generation") == 2
    assert predicates.count("capacity.solar_ac.project.operating") == 1
    assert all(row[2] == "pending" for row in ev)
    cap = next(row[1] for row in ev if row[0].startswith("capacity."))
    assert cap["value"] == 10
    assert cap["unit"] == "MW"
    assert cap["scope"] == "project"
    assert cap["capacity_status"] == "operating"
    assert sites[0] is True
