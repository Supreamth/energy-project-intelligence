from __future__ import annotations

from pathlib import Path
import uuid

import psycopg

from energy_intelligence.ingest import import_snapshot
from energy_intelligence.operators import apply_operator_research
from energy_intelligence.storage import LocalObjectStore

DSN = "postgresql://hermes@127.0.0.1:55432/intelligence"


def test_operator_research_sets_website_not_hq_point(tmp_path: Path):
    key = uuid.uuid4().hex
    legal = f"บริษัท ทดสอบผู้ประกอบการ {key} จำกัด"
    store = LocalObjectStore(tmp_path)
    catalog = [
        {
            "legal_name": legal,
            "website": "https://example.invalid/operator",
            "hq_note": "Bangkok office is not a plant",
            "sites": [],
        }
    ]
    with psycopg.connect(DSN) as conn:
        org_id = uuid.uuid4()
        conn.execute("INSERT INTO intelligence.entities(id, kind) VALUES (%s,'organization')", (org_id,))
        conn.execute(
            "INSERT INTO intelligence.organizations(entity_id, legal_name, country_code) VALUES (%s,%s,'TH')",
            (org_id, legal),
        )
        conn.commit()
        n = apply_operator_research(conn, catalog=catalog, store=store)
        conn.commit()
        alias = conn.execute(
            "SELECT alias, language FROM intelligence.entity_aliases WHERE entity_id=%s",
            (org_id,),
        ).fetchone()
    assert n["websites"] == 1
    assert n["points"] == 0
    assert alias[0] == "https://example.invalid/operator"
    assert alias[1] == "url"


def test_operator_research_attaches_point_only_on_unique_host_name(tmp_path: Path):
    key = uuid.uuid4().hex
    legal = f"บริษัท คันไซ เทส {key} จำกัด"
    csv_text = (
        "\ufeff"
        '"ชื่อผู้รับใบอนุญาต","ชื่อสถานประกอบกิจการ","จังหวัด","สำนักงานประจำเขต","เลขทะเบียนใบอนุญาต","วันที่ออกใบอนุญาต","ชนิดเชื้อเพลิงหลัก/แหล่งพลังงานต้นกำลัง","ชนิดเชื้อเพลิงเสริม","ขนาดกำลังการผลิต (MW)","ขนาดกำลังการผลิต (kVA)","ขนาดพิกัดแรงดัน (kV)","ปริมาณความต้องการพลังไฟฟ้าสูงสุด (MW)","วันที่เริ่มประกอบกิจการ (COD)"\r\n'
        f'"{legal}","ติดตั้งบนหลังคาบริษัท คาวาซากิ มอเตอร์ เอ็นเตอร์ไพรส์","ระยอง","เขตที่ 03","กกพ OP-{key}-0001","1 มกราคม 2568","พลังแสงอาทิตย์ (Solar Photovoltaic Power)"," ","7.075","7,075.00"," ","7.075","15 ธันวาคม 2565"\r\n'
        f'"{legal}","ติดตั้งบนหลังคาบริษัท อื่นที่ไม่ตรง","ระยอง","เขตที่ 03","กกพ OP-{key}-0002","1 มกราคม 2568","พลังแสงอาทิตย์ (Solar Photovoltaic Power)"," ","1.000","1,000.00"," ","1.000","15 ธันวาคม 2565"\r\n'
    ).encode("utf-8")
    store = LocalObjectStore(tmp_path)
    from energy_intelligence.erc_csv import extract_solar_licenses

    catalog = [
        {
            "legal_name": legal,
            "website": "https://www.kest.co.th/",
            "sites": [
                {
                    "name_contains": "คาวาซากิ มอเตอร์",
                    "province": "ระยอง",
                    "lat": 12.998333,
                    "lon": 101.178056,
                    "location_method": "jcm_pdd",
                    "source_url": "https://www.jcm.go.jp/th-jp/projects/138",
                    "accuracy_m": 200,
                }
            ],
        }
    ]
    with psycopg.connect(DSN) as conn:
        snap = import_snapshot(
            conn, store, source_code="erc_licensees", external_key=f"op-{key}",
            payload=csv_text, content_type="text/csv", extractor_version="test",
        )
        conn.commit()
        extract_solar_licenses(conn, store, raw_record_id=snap.raw_record_id)
        conn.commit()
        n = apply_operator_research(conn, catalog=catalog, store=store)
        conn.commit()
        hit = conn.execute(
            """
            SELECT ST_Y(s.point), ST_X(s.point), s.location_method
            FROM intelligence.projects p
            JOIN intelligence.sites s ON s.project_id = p.entity_id
            JOIN intelligence.entity_aliases a ON a.entity_id = p.entity_id
            WHERE a.alias = %s
            """,
            (f"กกพ OP-{key}-0001",),
        ).fetchone()
        miss = conn.execute(
            """
            SELECT s.point IS NULL
            FROM intelligence.projects p
            JOIN intelligence.sites s ON s.project_id = p.entity_id
            JOIN intelligence.entity_aliases a ON a.entity_id = p.entity_id
            WHERE a.alias = %s
            """,
            (f"กกพ OP-{key}-0002",),
        ).fetchone()
    assert n["points"] == 1
    assert abs(hit[0] - 12.998333) < 1e-5
    assert hit[2] == "jcm_pdd"
    assert miss[0] is True
