from __future__ import annotations

from datetime import date
from pathlib import Path
import uuid

import psycopg

from energy_intelligence.erc_csv import extract_solar_licenses, materialize_schema_facts, parse_thai_date
from energy_intelligence.ingest import import_snapshot
from energy_intelligence.review import accept_evidence, select_canonical
from energy_intelligence.storage import LocalObjectStore

DSN = "postgresql://hermes@127.0.0.1:55432/intelligence"


def test_parse_thai_date():
    assert parse_thai_date("15 มกราคม 2568") == date(2025, 1, 15)
    assert parse_thai_date(" ") is None


def test_materialize_capacity_and_cod_milestone(tmp_path: Path):
    key = uuid.uuid4().hex
    csv_text = (
        "\ufeff"
        '"ชื่อผู้รับใบอนุญาต","ชื่อสถานประกอบกิจการ","จังหวัด","สำนักงานประจำเขต","เลขทะเบียนใบอนุญาต","วันที่ออกใบอนุญาต","ชนิดเชื้อเพลิงหลัก/แหล่งพลังงานต้นกำลัง","ชนิดเชื้อเพลิงเสริม","ขนาดกำลังการผลิต (MW)","ขนาดกำลังการผลิต (kVA)","ขนาดพิกัดแรงดัน (kV)","ปริมาณความต้องการพลังไฟฟ้าสูงสุด (MW)","วันที่เริ่มประกอบกิจการ (COD)"\r\n'
        f'"บริษัท เอ จำกัด","ฟาร์มเอ","นครราชสีมา","เขตที่ 03","กกพ MAT-{key}-0001","1 มกราคม 2568","พลังแสงอาทิตย์ (Solar Photovoltaic Power)"," ","10.000","10,000.00"," ","10.000","15 มกราคม 2568"\r\n'
    ).encode("utf-8")
    store = LocalObjectStore(tmp_path)
    with psycopg.connect(DSN) as conn:
        snap = import_snapshot(
            conn, store, source_code="erc_licensees", external_key=f"mat-{key}",
            payload=csv_text, content_type="text/csv", extractor_version="test",
        )
        conn.commit()
        extract_solar_licenses(conn, store, raw_record_id=snap.raw_record_id)
        conn.commit()
        for eid, pred in conn.execute(
            "SELECT id, predicate FROM intelligence.evidence WHERE raw_record_id=%s",
            (snap.raw_record_id,),
        ):
            accept_evidence(conn, evidence_id=eid, actor="t", reason="t")
            select_canonical(conn, evidence_id=eid, field_key=pred, actor="t", reason="t")
        conn.commit()
        n = materialize_schema_facts(conn, raw_record_id=snap.raw_record_id)
        conn.commit()
        caps = conn.execute(
            """
            SELECT count(*) FROM intelligence.capacity_facts f
            JOIN intelligence.entity_aliases a ON a.entity_id = f.subject_entity_id
            WHERE a.alias = %s
            """,
            (f"กกพ MAT-{key}-0001",),
        ).fetchone()[0]
        miles = conn.execute(
            """
            SELECT f.date_from FROM intelligence.milestone_facts f
            JOIN intelligence.entity_aliases a ON a.entity_id = f.subject_entity_id
            WHERE a.alias = %s
            """,
            (f"กกพ MAT-{key}-0001",),
        ).fetchone()
        st = conn.execute(
            """
            SELECT count(*) FROM intelligence.status_observations f
            JOIN intelligence.entity_aliases a ON a.entity_id = f.subject_entity_id
            WHERE a.alias = %s
            """,
            (f"กกพ MAT-{key}-0001",),
        ).fetchone()[0]
    assert n["capacity_facts"] == 1
    assert caps == 1
    assert miles[0] == date(2025, 1, 15)
    assert st == 1
