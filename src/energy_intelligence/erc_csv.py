"""Extract solar generation licenses from an ERC RadGrid CSV snapshot."""

from __future__ import annotations

import csv
import io
import json
import re
import uuid
from dataclasses import dataclass
from datetime import date

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


def accept_extracted_solar(conn, *, raw_record_id, actor: str, reason: str) -> int:
    from energy_intelligence.review import accept_evidence, select_canonical

    rows = conn.execute(
        """
        SELECT id, predicate FROM intelligence.evidence
        WHERE raw_record_id = %s AND review_status = 'pending' AND subject_entity_id IS NOT NULL
        ORDER BY extraction_key
        """,
        (raw_record_id,),
    ).fetchall()
    n = 0
    for evidence_id, predicate in rows:
        accept_evidence(conn, evidence_id=evidence_id, actor=actor, reason=reason)
        select_canonical(
            conn,
            evidence_id=evidence_id,
            field_key=predicate,
            actor=actor,
            reason=reason,
        )
        n += 1
    return n


def enrich_from_erc_evidence(conn, *, raw_record_id) -> dict:
    rows = conn.execute(
        """
        SELECT ev.id, ev.subject_entity_id, ev.value_json
        FROM intelligence.evidence ev
        WHERE ev.raw_record_id = %s
          AND ev.predicate = 'regulatory.erc.generation'
          AND ev.subject_entity_id IS NOT NULL
        """,
        (raw_record_id,),
    ).fetchall()
    parties = 0
    provinces = 0
    for evidence_id, project_id, value in rows:
        licensee = (value or {}).get("licensee") or ""
        province = (value or {}).get("province") or ""
        if licensee:
            org_id = _org(conn, licensee)
            existing = conn.execute(
                """
                SELECT 1 FROM intelligence.project_parties
                WHERE project_id = %s AND organization_id = %s AND role = 'licensee'
                """,
                (project_id, org_id),
            ).fetchone()
            if not existing:
                conn.execute(
                    """
                    INSERT INTO intelligence.project_parties(
                      id, project_id, organization_id, role, evidence_id
                    ) VALUES (%s, %s, %s, 'licensee', %s)
                    """,
                    (uuid.uuid4(), project_id, org_id, evidence_id),
                )
                parties += 1
        if province:
            cur = conn.execute(
                """
                UPDATE intelligence.sites
                SET province_code = %s
                WHERE project_id = %s
                  AND (province_code IS NULL OR btrim(province_code) = '')
                """,
                (province, project_id),
            )
            if cur.rowcount:
                provinces += cur.rowcount
    return {"parties": parties, "provinces": provinces}


TH_MONTHS = {
    "มกราคม": 1,
    "กุมภาพันธ์": 2,
    "มีนาคม": 3,
    "เมษายน": 4,
    "พฤษภาคม": 5,
    "มิถุนายน": 6,
    "กรกฎาคม": 7,
    "สิงหาคม": 8,
    "กันยายน": 9,
    "ตุลาคม": 10,
    "พฤศจิกายน": 11,
    "ธันวาคม": 12,
}


def parse_thai_date(raw: str | None) -> date | None:
    text = (raw or "").strip()
    if not text:
        return None
    match = re.match(r"(\d{1,2})\s+(\S+)\s+(\d{4})$", text)
    if not match:
        return None
    day = int(match.group(1))
    month = TH_MONTHS.get(match.group(2))
    year = int(match.group(3))
    if month is None:
        return None
    if year >= 2400:
        year -= 543
    try:
        return date(year, month, day)
    except ValueError:
        return None


def materialize_schema_facts(conn, *, raw_record_id) -> dict:
    cap_n = 0
    mile_n = 0
    status_n = 0
    rows = conn.execute(
        """
        SELECT cs.evidence_id, cs.subject_entity_id, cs.field_key, ev.value_json
        FROM intelligence.canonical_selections cs
        JOIN intelligence.evidence ev ON ev.id = cs.evidence_id
        WHERE ev.raw_record_id = %s AND cs.superseded_at IS NULL
        """,
        (raw_record_id,),
    ).fetchall()
    for evidence_id, subject_id, field_key, value in rows:
        value = value or {}
        if field_key == "capacity.solar_ac.project.operating":
            mw = value.get("value")
            if isinstance(mw, (int, float)) and mw > 0:
                exists = conn.execute(
                    "SELECT 1 FROM intelligence.capacity_facts WHERE evidence_id = %s",
                    (evidence_id,),
                ).fetchone()
                if not exists:
                    conn.execute(
                        """
                        INSERT INTO intelligence.capacity_facts(
                          id, subject_entity_id, metric, value_mw, scope, capacity_status, evidence_id
                        ) VALUES (%s,%s,'solar_ac',%s,'project','operating',%s)
                        """,
                        (uuid.uuid4(), subject_id, mw, evidence_id),
                    )
                    cap_n += 1
        if field_key == "regulatory.erc.generation":
            exists = conn.execute(
                "SELECT 1 FROM intelligence.status_observations WHERE evidence_id = %s",
                (evidence_id,),
            ).fetchone()
            if not exists:
                conn.execute(
                    """
                    INSERT INTO intelligence.status_observations(
                      id, subject_entity_id, dimension, status_code, license_kind,
                      license_external_key, observed_at, evidence_id
                    ) VALUES (%s,%s,'regulatory','approved','erc_generation',%s, now(), %s)
                    """,
                    (uuid.uuid4(), subject_id, value.get("license_no"), evidence_id),
                )
                status_n += 1
            cod = parse_thai_date(value.get("cod_th"))
            if cod:
                exists_m = conn.execute(
                    """
                    SELECT 1 FROM intelligence.milestone_facts
                    WHERE evidence_id = %s AND milestone = 'cod'
                    """,
                    (evidence_id,),
                ).fetchone()
                if not exists_m:
                    conn.execute(
                        """
                        INSERT INTO intelligence.milestone_facts(
                          id, subject_entity_id, milestone, date_from, date_precision, certainty, evidence_id
                        ) VALUES (%s,%s,'cod',%s,'day','reported_actual',%s)
                        """,
                        (uuid.uuid4(), subject_id, cod, evidence_id),
                    )
                    mile_n += 1
    return {"capacity_facts": cap_n, "milestones": mile_n, "status_observations": status_n}


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
