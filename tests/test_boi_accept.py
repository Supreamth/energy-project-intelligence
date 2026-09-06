from __future__ import annotations

from pathlib import Path
import uuid

import psycopg

from energy_intelligence.boi_csv import accept_boi_csv, extract_boi_csv
from energy_intelligence.ingest import import_snapshot
from energy_intelligence.storage import LocalObjectStore

DSN = "postgresql://hermes@127.0.0.1:55432/intelligence"


def test_accept_boi_csv_sets_org_canonical_without_points(tmp_path: Path):
    key = uuid.uuid4().hex
    legal = f"บริษัท บีโอไอ แอคเซปต์ {key} จำกัด"
    csv_text = (
        "\ufeffCompany Name,Products,Address,Tambon,District,Province,ZIP Code,Telephone,Fax,COM_ID,HP_ID\r\n"
        f'"{legal}",ไฟฟ้าจากพลังงานแสงอาทิตย์,อาคารสำนักงานใหญ่,แขวงบางนาใต้,เขตบางนา,กรุงเทพมหานคร,10260,,,0105554012069,HPACC{key}\r\n'
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
            conn, store, source_code="boi_promoted", external_key=f"acc-boi-{key}",
            payload=csv_text, content_type="text/csv", extractor_version="test",
        )
        conn.commit()
        extract_boi_csv(conn, store, raw_record_id=snap.raw_record_id)
        conn.commit()
        n = accept_boi_csv(
            conn, raw_record_id=snap.raw_record_id, actor="user", reason="test",
        )
        conn.commit()
        status = conn.execute(
            "SELECT review_status FROM intelligence.evidence WHERE raw_record_id=%s",
            (snap.raw_record_id,),
        ).fetchone()[0]
        can = conn.execute(
            """
            SELECT cs.subject_entity_id FROM intelligence.canonical_selections cs
            JOIN intelligence.evidence ev ON ev.id = cs.evidence_id
            WHERE ev.raw_record_id=%s AND cs.superseded_at IS NULL
            """,
            (snap.raw_record_id,),
        ).fetchone()
        pts = conn.execute(
            "SELECT count(*) FROM intelligence.sites WHERE point IS NOT NULL AND label ILIKE %s",
            (f"%{key}%",),
        ).fetchone()[0]
    assert n["accepted"] == 1
    assert n["canonical"] == 1
    assert status == "accepted"
    assert can[0] == org_id
    assert pts == 0
