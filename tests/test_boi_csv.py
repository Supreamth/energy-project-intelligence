from __future__ import annotations

from pathlib import Path
import uuid

import psycopg

from energy_intelligence.boi_csv import extract_boi_csv
from energy_intelligence.ingest import import_snapshot
from energy_intelligence.storage import LocalObjectStore

DSN = "postgresql://hermes@127.0.0.1:55432/intelligence"


def test_extract_boi_csv_pending_links_org_and_skips_points(tmp_path: Path):
    key = uuid.uuid4().hex
    legal = f"บริษัท บีโอไอ เทส {key} จำกัด"
    csv_text = (
        "\ufeffCompany Name,Products,Address,Tambon,District,Province,ZIP Code,Telephone,Fax,COM_ID,HP_ID\r\n"
        f'"{legal}",ไฟฟ้าจากพลังงานแสงอาทิตย์,อาคารสำนักงานใหญ่,แขวงบางนาใต้,เขตบางนา,กรุงเทพมหานคร,10260,,,0105554012069,HP{key}A\r\n'
        f'"{legal}",ไฟฟ้าจากพลังงานแสงอาทิตย์ที่ติดตั้งบนหลังคา,อาคารสำนักงานใหญ่,แขวงบางนาใต้,เขตบางนา,กรุงเทพมหานคร,10260,,,0105554012069,HP{key}B\r\n'
        f'"บริษัท อื่น {key} จำกัด",ผลิตชิ้นส่วนยานยนต์,ถนนสุขุมวิท,แขวงคลองเตย,เขตคลองเตย,กรุงเทพมหานคร,10110,,,0105550000001,HP{key}C\r\n'
    ).encode("utf-8")
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
            conn, store, source_code="boi_promoted", external_key=f"csv-{key}",
            payload=csv_text, content_type="text/csv", extractor_version="test",
        )
        conn.commit()
        n = extract_boi_csv(conn, store, raw_record_id=snap.raw_record_id)
        conn.commit()
        again = extract_boi_csv(conn, store, raw_record_id=snap.raw_record_id)
        conn.commit()
        ev = conn.execute(
            """
            SELECT predicate, review_status, subject_entity_id, value_json->>'hp_id',
                   value_json->>'province'
            FROM intelligence.evidence
            WHERE raw_record_id=%s
            ORDER BY extraction_key
            """,
            (snap.raw_record_id,),
        ).fetchall()
        points = conn.execute(
            "SELECT count(*) FROM intelligence.sites WHERE point IS NOT NULL AND label ILIKE %s",
            (f"%{key}%",),
        ).fetchone()[0]
    assert n.solar_kept == 2
    assert n.evidence_inserted == 2
    assert n.orgs_linked == 2
    assert again.evidence_inserted == 0
    assert len(ev) == 2
    assert {row[3] for row in ev} == {f"HP{key}A", f"HP{key}B"}
    assert all(row[0] == "regulatory.boi.promotion" for row in ev)
    assert all(row[1] == "pending" for row in ev)
    assert all(row[2] == org_id for row in ev)
    assert all(row[4] == "กรุงเทพมหานคร" for row in ev)
    assert points == 0
