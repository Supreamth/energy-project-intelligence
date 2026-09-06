from __future__ import annotations

from pathlib import Path
import uuid

import psycopg

from energy_intelligence.erc_csv import accept_extracted_solar, extract_solar_licenses
from energy_intelligence.ingest import import_snapshot
from energy_intelligence.storage import LocalObjectStore

DSN = "postgresql://hermes@127.0.0.1:55432/intelligence"


def test_accept_extracted_solar_sets_canonical(tmp_path: Path):
    key = uuid.uuid4().hex
    csv_text = (
        "\ufeff"
        '"ชื่อผู้รับใบอนุญาต","ชื่อสถานประกอบกิจการ","จังหวัด","สำนักงานประจำเขต","เลขทะเบียนใบอนุญาต","วันที่ออกใบอนุญาต","ชนิดเชื้อเพลิงหลัก/แหล่งพลังงานต้นกำลัง","ชนิดเชื้อเพลิงเสริม","ขนาดกำลังการผลิต (MW)","ขนาดกำลังการผลิต (kVA)","ขนาดพิกัดแรงดัน (kV)","ปริมาณความต้องการพลังไฟฟ้าสูงสุด (MW)","วันที่เริ่มประกอบกิจการ (COD)"\r\n'
        f'"บริษัท เอ จำกัด","ฟาร์มเอ","นครราชสีมา","เขตที่ 03","กกพ ACC-{key}-0001","1 มกราคม 2568","พลังแสงอาทิตย์ (Solar Photovoltaic Power)"," ","10.000","10,000.00"," ","10.000","15 มกราคม 2568"\r\n'
    ).encode("utf-8")
    store = LocalObjectStore(tmp_path)
    with psycopg.connect(DSN) as conn:
        snap = import_snapshot(
            conn,
            store,
            source_code="erc_licensees",
            external_key=f"acc-{key}",
            payload=csv_text,
            content_type="text/csv",
            extractor_version="test",
        )
        conn.commit()
        extract_solar_licenses(conn, store, raw_record_id=snap.raw_record_id)
        conn.commit()
        accepted = accept_extracted_solar(conn, raw_record_id=snap.raw_record_id, actor="t", reason="file")
        conn.commit()
        statuses = [r[0] for r in conn.execute(
            "SELECT review_status FROM intelligence.evidence WHERE raw_record_id = %s",
            (snap.raw_record_id,),
        )]
        can_n = conn.execute(
            """
            SELECT count(*) FROM intelligence.canonical_selections cs
            JOIN intelligence.evidence ev ON ev.id = cs.evidence_id
            WHERE ev.raw_record_id = %s AND cs.superseded_at IS NULL
            """,
            (snap.raw_record_id,),
        ).fetchone()[0]
    assert accepted == 2
    assert statuses == ["accepted", "accepted"]
    assert can_n == 2
