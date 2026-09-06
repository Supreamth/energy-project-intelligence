"""Extract solar promotions from a BOI promoted-companies CSV snapshot."""

from __future__ import annotations

import csv
import io
import json
import uuid
from dataclasses import dataclass

EXTRACTOR_VERSION = "boi-csv-solar-0.1"


@dataclass
class ExtractResult:
    evidence_inserted: int
    solar_kept: int
    orgs_linked: int
    rows_seen: int


def extract_boi_csv(conn, store, *, raw_record_id) -> ExtractResult:
    raw = conn.execute(
        """
        SELECT r.payload_sha256, s.code
        FROM intelligence.raw_records r
        JOIN intelligence.sources s ON s.id = r.source_id
        WHERE r.id = %s
        """,
        (raw_record_id,),
    ).fetchone()
    if raw is None:
        raise ValueError("raw record not found")
    sha256, source_code = raw
    payload = store.get(source_code, sha256)
    rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))
    inserted = 0
    kept = 0
    linked = 0
    for line_no, row in enumerate(rows, start=2):
        company = (row.get("Company Name") or "").strip()
        product = (row.get("Products") or "").strip()
        hp_id = (row.get("HP_ID") or "").strip()
        if not company or not hp_id:
            continue
        if "แสงอาทิตย์" not in product:
            continue
        kept += 1
        org_id = _org_exact(conn, company)
        value = {
            "license_kind": "BOI",
            "company": company,
            "product": product,
            "com_id": (row.get("COM_ID") or "").strip() or None,
            "hp_id": hp_id,
            "contact_address": (row.get("Address") or "").strip() or None,
            "tambon": (row.get("Tambon") or "").strip() or None,
            "district": (row.get("District") or "").strip() or None,
            "province": (row.get("Province") or "").strip() or None,
            "zip": (row.get("ZIP Code") or "").strip() or None,
            "address_role": "contact_not_site",
        }
        n = _insert_evidence(
            conn,
            raw_record_id=raw_record_id,
            extraction_key=f"hp:{hp_id}",
            subject_entity_id=org_id,
            value=value,
            excerpt=f"{hp_id} · {company} · {product}",
            locator={"csv_row": line_no, "column": "HP_ID"},
        )
        inserted += n
        if n and org_id:
            linked += 1
    return ExtractResult(
        evidence_inserted=inserted,
        solar_kept=kept,
        orgs_linked=linked,
        rows_seen=len(rows),
    )


def _org_exact(conn, legal_name: str):
    row = conn.execute(
        "SELECT entity_id FROM intelligence.organizations WHERE legal_name = %s",
        (legal_name,),
    ).fetchall()
    if len(row) == 1:
        return row[0][0]
    return None


def _insert_evidence(conn, *, raw_record_id, extraction_key, subject_entity_id, value, excerpt, locator) -> int:
    cur = conn.execute(
        """
        INSERT INTO intelligence.evidence(
          id, raw_record_id, extraction_key, subject_entity_id, predicate, value_json,
          excerpt, locator, extractor_version, review_status
        ) VALUES (
          %s, %s, %s, %s, 'regulatory.boi.promotion', %s::jsonb, %s, %s::jsonb, %s, 'pending'
        )
        ON CONFLICT (raw_record_id, extractor_version, extraction_key)
        DO NOTHING
        RETURNING id
        """,
        (
            uuid.uuid4(),
            raw_record_id,
            extraction_key,
            subject_entity_id,
            json.dumps(value, ensure_ascii=False),
            excerpt,
            json.dumps(locator, ensure_ascii=False),
            EXTRACTOR_VERSION,
        ),
    )
    return 1 if cur.fetchone() else 0
