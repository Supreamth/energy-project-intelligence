from __future__ import annotations

from pathlib import Path
import uuid

import psycopg

from energy_intelligence.erc_csv import enrich_from_erc_evidence, extract_solar_licenses
from energy_intelligence.ingest import import_snapshot
from energy_intelligence.storage import LocalObjectStore

DSN = "postgresql://hermes@127.0.0.1:55432/intelligence"


def test_enrich_links_licensee_and_province_without_coordinates(tmp_path: Path):
    key = uuid.uuid4().hex
    csv_text = (
        "\ufeff"
        '"ชื่อผู้รับใบอนุญาต","ชื่อสถานประกอบกิจการ","จังหวัด","สำนักงานประจำเขต","เลขทะเบียนใบอนุญาต","วันที่ออกใบอนุญาต","ชนิดเชื้อเพลิงหลัก/แหล่งพลังงานต้นกำลัง","ชนิดเชื้อเพลิงเสริม","ขนาดกำลังการผลิต (MW)","ขนาดกำลังการผลิต (kVA)","ขนาดพิกัดแรงดัน (kV)","ปริมาณความต้องการพลังไฟฟ้าสูงสุด (MW)","วันที่เริ่มประกอบกิจการ (COD)"\r\n'
        f'"บริษัท เอ จำกัด","ฟาร์มเอ","นครราชสีมา","เขตที่ 03","กกพ ENR-{key}-0001","1 มกราคม 2568","พลังแสงอาทิตย์ (Solar Photovoltaic Power)"," ","10.000","10,000.00"," ","10.000","15 มกราคม 2568"\r\n'
    ).encode("utf-8")
    store = LocalObjectStore(tmp_path)
    with psycopg.connect(DSN) as conn:
        snap = import_snapshot(
            conn, store, source_code="erc_licensees", external_key=f"enr-{key}",
            payload=csv_text, content_type="text/csv", extractor_version="test",
        )
        conn.commit()
        extract_solar_licenses(conn, store, raw_record_id=snap.raw_record_id)
        conn.commit()
        n = enrich_from_erc_evidence(conn, raw_record_id=snap.raw_record_id)
        conn.commit()
        again = enrich_from_erc_evidence(conn, raw_record_id=snap.raw_record_id)
        conn.commit()
        parties = conn.execute(
            """
            SELECT o.legal_name, s.province_code, s.point IS NULL
            FROM intelligence.projects p
            JOIN intelligence.entity_aliases a ON a.entity_id = p.entity_id
            JOIN intelligence.project_parties pp ON pp.project_id = p.entity_id
            JOIN intelligence.organizations o ON o.entity_id = pp.organization_id
            JOIN intelligence.sites s ON s.project_id = p.entity_id
            WHERE a.alias = %s
            """,
            (f"กกพ ENR-{key}-0001",),
        ).fetchone()
    assert n["parties"] == 1
    assert n["provinces"] == 1
    assert again["parties"] == 0
    assert parties[0] == "บริษัท เอ จำกัด"
    assert parties[1] == "นครราชสีมา"
    assert parties[2] is True
