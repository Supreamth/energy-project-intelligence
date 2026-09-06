from __future__ import annotations

from pathlib import Path
import uuid

import psycopg

from energy_intelligence.boi_pdf import extract_boi_solar
from energy_intelligence.ingest import import_snapshot
from energy_intelligence.storage import LocalObjectStore

DSN = "postgresql://hermes@127.0.0.1:55432/intelligence"

TEXT = """สำนักงานคณะกรรมการส่งเสริมการลงทุน (บีโอไอ)
6 พี.ซี.ดี.วาย คอร์ปอเรชั่น จำกัด (จ.นครราชสีมา) ผลิตไฟฟ้าจากพลังงานแสงอาทิตย์ ไทย
P.C.D.Y. CORPORATION 888/1 หมู่ 3 ต.โคกกรวด ที่ติดตั้งบนหลังคา
COMPANY LIMITED อ.เมือง จ.นครราชสีมา (7.1.1.2)
7 ท็อปเวลล์ อิลาสติกส์ จำกัด (จ.สมุทรปราการ) ศูนย์กลางธุรกิจระหว่างประเทศ ไทย
"""


def test_extract_boi_solar_skips_non_solar_and_links_unique_org(tmp_path: Path):
    key = uuid.uuid4().hex
    legal = f"บริษัท พี.ซี.ดี.วาย คอร์ปอเรชั่น {key} จำกัด"
    text = (
        "สำนักงานคณะกรรมการส่งเสริมการลงทุน (บีโอไอ)\n"
        f"6 พี.ซี.ดี.วาย คอร์ปอเรชั่น {key} จำกัด (จ.นครราชสีมา) ผลิตไฟฟ้าจากพลังงานแสงอาทิตย์ ไทย\n"
        "P.C.D.Y. CORPORATION 888/1 หมู่ 3 ต.โคกกรวด ที่ติดตั้งบนหลังคา\n"
        "COMPANY LIMITED อ.เมือง จ.นครราชสีมา (7.1.1.2)\n"
        "7 ท็อปเวลล์ อิลาสติกส์ จำกัด (จ.สมุทรปราการ) ศูนย์กลางธุรกิจระหว่างประเทศ ไทย\n"
    )
    store = LocalObjectStore(tmp_path)
    with psycopg.connect(DSN) as conn:
        org_id = uuid.uuid4()
        conn.execute("INSERT INTO intelligence.entities(id, kind) VALUES (%s,'organization')", (org_id,))
        conn.execute(
            "INSERT INTO intelligence.organizations(entity_id, legal_name, country_code) VALUES (%s,%s,'TH')",
            (org_id, legal),
        )
        conn.commit()
        snap = import_snapshot(
            conn, store, source_code="boi_promoted", external_key=f"boi-{key}",
            payload=text.encode("utf-8"), content_type="text/plain", extractor_version="test",
        )
        conn.commit()
        n = extract_boi_solar(conn, store, raw_record_id=snap.raw_record_id)
        conn.commit()
        again = extract_boi_solar(conn, store, raw_record_id=snap.raw_record_id)
        conn.commit()
        ev = conn.execute(
            """
            SELECT predicate, review_status, subject_entity_id, value_json
            FROM intelligence.evidence WHERE raw_record_id=%s
            """,
            (snap.raw_record_id,),
        ).fetchall()
    assert n.solar_kept == 1
    assert n.evidence_inserted == 1
    assert again.evidence_inserted == 0
    assert len(ev) == 1
    assert ev[0][0] == "regulatory.boi.promotion"
    assert ev[0][1] == "pending"
    assert ev[0][2] == org_id
    assert ev[0][3]["activity_code"] == "7.1.1.2"
    assert "แสงอาทิตย์" in (ev[0][3].get("product") or ev[0][3].get("activity") or "")
