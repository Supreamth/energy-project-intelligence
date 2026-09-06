"""Extract solar generation licenses from an ERC RadGrid CSV snapshot."""

from __future__ import annotations

import csv
import io
import json
import uuid
from dataclasses import dataclass

EXTRACTOR_VERSION = "erc-csv-solar-0.1"


@dataclass
class ExtractResult:
    projects_created: int
    evidence_inserted: int
    rows_seen: int
    solar_kept: int


def extract_solar_licenses(conn, store, *, raw_record_id) -> ExtractResult:
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
    text = payload.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return ExtractResult(0, 0, 0, 0)
    header = rows[0]
    idx = {name.strip(): i for i, name in enumerate(header)}
    required = [
        "ชื่อผู้รับใบอนุญาต",
        "ชื่อสถานประกอบกิจการ",
        "จังหวัด",
        "เลขทะเบียนใบอนุญาต",
        "ชนิดเชื้อเพลิงหลัก/แหล่งพลังงานต้นกำลัง",
        "ขนาดกำลังการผลิต (MW)",
        "วันที่เริ่มประกอบกิจการ (COD)",
        "วันที่ออกใบอนุญาต",
    ]
    for col in required:
        if col not in idx:
            raise ValueError(f"missing column: {col}")

    projects_created = 0
    evidence_inserted = 0
    solar_kept = 0
    for line_no, row in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in row):
            continue
        fuel = _cell(row, idx, "ชนิดเชื้อเพลิงหลัก/แหล่งพลังงานต้นกำลัง")
        if not _is_solar(fuel):
            continue
        mw = _parse_mw(_cell(row, idx, "ขนาดกำลังการผลิต (MW)"))
        if mw is None or mw == 0:
            continue
        license_no = _cell(row, idx, "เลขทะเบียนใบอนุญาต")
        if not license_no:
            continue
        solar_kept += 1
        licensee = _cell(row, idx, "ชื่อผู้รับใบอนุญาต") or "ไม่ทราบชื่อผู้รับใบอนุญาต"
        facility = _cell(row, idx, "ชื่อสถานประกอบกิจการ") or licensee
        province = _cell(row, idx, "จังหวัด")
        issued = _cell(row, idx, "วันที่ออกใบอนุญาต")
        cod = _cell(row, idx, "วันที่เริ่มประกอบกิจการ (COD)")
        project_id, created = _project_for_license(
            conn,
            license_no=license_no,
            facility=facility,
            licensee=licensee,
            province=province,
            raw_record_id=raw_record_id,
        )
        if created:
            projects_created += 1
        license_value = {
            "license_kind": "ERC",
            "license_no": license_no,
            "licensee": licensee,
            "facility": facility,
            "province": province or None,
            "fuel": fuel,
            "issued_th": issued or None,
            "cod_th": cod or None,
            "capacity_mw_reported": mw,
        }
        evidence_inserted += _insert_evidence(
            conn,
            raw_record_id=raw_record_id,
            extraction_key=f"license:{license_no}",
            subject_entity_id=project_id,
            predicate="regulatory.erc.generation",
            value=license_value,
            excerpt=f"{license_no} · {facility} · {mw} MW",
            locator={"csv_row": line_no, "column": "เลขทะเบียนใบอนุญาต"},
        )
        if cod:
            evidence_inserted += _insert_evidence(
                conn,
                raw_record_id=raw_record_id,
                extraction_key=f"capacity:{license_no}",
                subject_entity_id=project_id,
                predicate="capacity.solar_ac.project.operating",
                value={
                    "value": mw,
                    "unit": "MW",
                    "scope": "project",
                    "capacity_status": "operating",
                },
                excerpt=f"{mw} MW COD {cod}",
                locator={"csv_row": line_no, "column": "ขนาดกำลังการผลิต (MW)"},
            )
    return ExtractResult(
        projects_created=projects_created,
        evidence_inserted=evidence_inserted,
        rows_seen=max(0, len(rows) - 1),
        solar_kept=solar_kept,
    )


def _cell(row: list[str], idx: dict[str, int], name: str) -> str:
    if idx[name] >= len(row):
        return ""
    return (row[idx[name]] or "").strip()


def _is_solar(fuel: str) -> bool:
    return "แสงอาทิตย์" in fuel or "Solar" in fuel


def _parse_mw(raw: str) -> float | None:
    text = raw.replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _project_for_license(conn, *, license_no, facility, licensee, province, raw_record_id):
    existing = conn.execute(
        "SELECT entity_id FROM intelligence.entity_aliases WHERE alias = %s LIMIT 1",
        (license_no,),
    ).fetchone()
    if existing:
        return existing[0], False
    org_id = _org(conn, licensee)
    project_id = uuid.uuid4()
    site_id = uuid.uuid4()
    conn.execute("INSERT INTO intelligence.entities(id, kind) VALUES (%s, 'project')", (project_id,))
    conn.execute(
        """
        INSERT INTO intelligence.projects(entity_id, name_th, name_en, project_type)
        VALUES (%s, %s, NULL, 'solar_farm')
        """,
        (project_id, facility),
    )
    conn.execute(
        "INSERT INTO intelligence.entity_aliases(id, entity_id, alias, language, raw_record_id) VALUES (%s,%s,%s,'th',%s)",
        (uuid.uuid4(), project_id, license_no, raw_record_id),
    )
    conn.execute("INSERT INTO intelligence.entities(id, kind) VALUES (%s, 'site')", (site_id,))
    label = facility if not province else f"{facility} · {province}"
    conn.execute(
        "INSERT INTO intelligence.sites(entity_id, project_id, label, point, location_method) VALUES (%s,%s,%s,NULL,NULL)",
        (site_id, project_id, label),
    )
    _ = org_id
    return project_id, True


def _org(conn, legal_name: str):
    row = conn.execute(
        "SELECT entity_id FROM intelligence.organizations WHERE legal_name = %s LIMIT 1",
        (legal_name,),
    ).fetchone()
    if row:
        return row[0]
    org_id = uuid.uuid4()
    conn.execute("INSERT INTO intelligence.entities(id, kind) VALUES (%s, 'organization')", (org_id,))
    conn.execute(
        "INSERT INTO intelligence.organizations(entity_id, legal_name, country_code) VALUES (%s,%s,'TH')",
        (org_id, legal_name),
    )
    return org_id


def _insert_evidence(conn, *, raw_record_id, extraction_key, subject_entity_id, predicate, value, excerpt, locator) -> int:
    cur = conn.execute(
        """
        INSERT INTO intelligence.evidence(
          id, raw_record_id, extraction_key, subject_entity_id, predicate, value_json,
          excerpt, locator, extractor_version, review_status
        ) VALUES (
          %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s, 'pending'
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
            predicate,
            json.dumps(value, ensure_ascii=False),
            excerpt,
            json.dumps(locator, ensure_ascii=False),
            EXTRACTOR_VERSION,
        ),
    )
    return 1 if cur.fetchone() else 0
