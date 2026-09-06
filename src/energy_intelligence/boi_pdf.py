"""Extract solar promotion rows from a BOI PDF or text snapshot."""

from __future__ import annotations

import io
import json
import re
import uuid
from dataclasses import dataclass

EXTRACTOR_VERSION = "boi-pdf-solar-0.1"

SOLAR_HINTS = ("แสงอาทิตย์", "Electricity Power from Solar", "Solar Rooftop", "7.1.1")


@dataclass
class ExtractResult:
    evidence_inserted: int
    solar_kept: int


def extract_boi_solar(conn, store, *, raw_record_id) -> ExtractResult:
    raw = conn.execute(
        """
        SELECT r.payload_sha256, s.code, r.content_type
        FROM intelligence.raw_records r
        JOIN intelligence.sources s ON s.id = r.source_id
        WHERE r.id = %s
        """,
        (raw_record_id,),
    ).fetchone()
    if raw is None:
        raise ValueError("raw record not found")
    sha256, source_code, content_type = raw
    payload = store.get(source_code, sha256)
    text = _normalize_pdf_text(_to_text(payload, content_type))
    rows = _solar_rows(text)
    inserted = 0
    for i, row in enumerate(rows, start=1):
        subject = _unique_org(conn, row["company"])
        inserted += _insert_evidence(
            conn,
            raw_record_id=raw_record_id,
            extraction_key=f"boi-solar:{row['company']}:{row.get('activity_code') or ''}:{i}",
            subject_entity_id=subject,
            value=row,
            excerpt=row.get("excerpt") or row["company"],
        )
    return ExtractResult(evidence_inserted=inserted, solar_kept=len(rows))


def _to_text(payload: bytes, content_type: str | None) -> str:
    if payload.startswith(b"%PDF") or (content_type or "").startswith("application/pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(payload))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    return payload.decode("utf-8-sig")


def _normalize_pdf_text(text: str) -> str:
    return (
        text.replace("จ ากัด", "จำกัด")
        .replace("จํากัด", "จำกัด")
        .replace("กำร", "การ")
    )


def _solar_rows(text: str) -> list[dict]:
    chunks = re.split(r"(?m)(?=^\s*\d+\s+)", text)
    rows = []
    seen = set()
    for chunk in chunks:
        if not any(h in chunk for h in SOLAR_HINTS):
            continue
        if "Solar Cells" in chunk or "Solar Module" in chunk:
            if "Electricity Power from Solar" not in chunk and "แสงอาทิตย์" not in chunk:
                continue
        company = _company(chunk)
        if not company or not _ok_company(company):
            continue
        code_match = re.search(r"\(7\.1(?:\.\d+)*\)", chunk)
        key = (company, code_match.group(0) if code_match else "", chunk[:80])
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "license_kind": "BOI",
                "company": company,
                "activity_code": code_match.group(0).strip("()") if code_match else None,
                "activity": "regulatory.boi.promotion",
                "product": "ผลิตไฟฟ้าจากพลังงานแสงอาทิตย์"
                if "แสงอาทิตย์" in chunk
                else "Electricity Power from Solar",
                "excerpt": " ".join(chunk.split())[:400],
            }
        )
    if not rows:
        rows.extend(_window_rows(text, seen))
    return rows


def _window_rows(text: str, seen: set) -> list[dict]:
    rows = []
    for match in re.finditer(
        r"ผลิตไฟฟ้าจากพลังงานแสงอาทิตย์|Electricity Power from Solar", text
    ):
        chunk = text[max(0, match.start() - 400) : match.end() + 180]
        if "Solar Cells" in chunk or "Solar Module" in chunk:
            if "Electricity Power from Solar" not in chunk and "แสงอาทิตย์" not in chunk:
                continue
        company = _company(chunk)
        if not company or not _ok_company(company):
            continue
        code_match = re.search(r"\(7\.1(?:\.\d+)*\)", chunk)
        key = (company, code_match.group(0) if code_match else "", chunk[:80])
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "license_kind": "BOI",
                "company": company,
                "activity_code": code_match.group(0).strip("()") if code_match else None,
                "activity": "regulatory.boi.promotion",
                "product": "ผลิตไฟฟ้าจากพลังงานแสงอาทิตย์"
                if "แสงอาทิตย์" in chunk
                else "Electricity Power from Solar",
                "excerpt": " ".join(chunk.split())[:400],
            }
        )
    return rows


def _company(chunk: str) -> str | None:
    match = re.search(r"(บริษัท\s+[^(\n]{2,80}จ[ำํา]?กัด(?:\s*\(มหาชน\))?)", chunk)
    if match:
        return " ".join(match.group(1).split())
    match = re.search(r"([^\n]{2,80}จ[ำํา]?กัด)", chunk)
    if match:
        name = " ".join(match.group(1).split())
        name = re.sub(r"^\d+\s+", "", name)
        name = re.sub(r"^บริษัท\s+", "", name)
        name = "บริษัท " + name
        return name
    return None


def _ok_company(company: str) -> bool:
    core = re.sub(r"\s+", "", _norm_name(company).replace("จำกัด", "").replace("(มหาชน)", ""))
    return len(core) >= 8


def _norm_name(value: str) -> str:
    text = value.replace("จํากัด", "จำกัด").replace("จำกัด (มหาชน)", "จำกัด")
    text = text.replace("บริษัท ", " ")
    text = re.sub(r"^\d+\s+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _unique_org(conn, company: str):
    needle = _norm_name(company)
    rows = conn.execute(
        "SELECT entity_id, legal_name FROM intelligence.organizations"
    ).fetchall()
    hits = [r[0] for r in rows if _norm_name(r[1]) == needle]
    if len(hits) == 1:
        return hits[0]
    return None


def _insert_evidence(conn, *, raw_record_id, extraction_key, subject_entity_id, value, excerpt) -> int:
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
            json.dumps({"extractor": EXTRACTOR_VERSION}, ensure_ascii=False),
            EXTRACTOR_VERSION,
        ),
    )
    return 1 if cur.fetchone() else 0
