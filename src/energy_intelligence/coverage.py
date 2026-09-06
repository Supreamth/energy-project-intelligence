"""Data readiness vs schema v0.2 slots. Missing is allowed; invented values are not."""

from __future__ import annotations

SOLAR_SLOTS = [
    ("project.name", "ชื่อโครงการ", "projects.name_th/name_en", "required"),
    ("site", "มีไซต์อย่างน้อยหนึ่ง", "sites", "required"),
    ("site.point", "พิกัดไซต์", "sites.point", "desired"),
    ("site.boundary", "ขอบเขตไซต์", "sites.boundary", "desired"),
    ("site.province_code", "รหัสจังหวัด", "sites.province_code", "desired"),
    ("phase", "เฟส", "phases", "optional"),
    ("project_parties", "บริษัทที่ผูกกับโครงการ", "project_parties", "required"),
    ("organization.website", "เว็บผู้ประกอบการ", "entity_aliases language=url", "desired"),
    ("alias.license", "เลขใบอนุญาตเป็น alias", "entity_aliases", "required"),
    ("canonical.regulatory.erc.generation", "canonical ใบอนุญาต กกพ.", "canonical_selections", "required"),
    ("canonical.regulatory.boi.promotion", "canonical BOI", "canonical_selections", "desired"),
    ("canonical.capacity.solar_ac.project.operating", "canonical solar AC เดินเครื่อง", "canonical_selections", "desired"),
    ("canonical.capacity.solar_dc.project.operating", "canonical solar DC เดินเครื่อง", "canonical_selections", "desired"),
    ("capacity_facts", "แถว capacity_facts", "capacity_facts", "desired"),
    ("milestone_facts", "เหตุการณ์ COD/ไมล์สโตน", "milestone_facts", "desired"),
    ("status_observations", "สถานะ regulatory ในตารางข้อสังเกต", "status_observations", "desired"),
]

DC_SLOTS = [
    ("project.name", "ชื่อโครงการ", "projects.name_th/name_en", "required"),
    ("site", "มีไซต์อย่างน้อยหนึ่ง", "sites", "required"),
    ("site.point", "พิกัดไซต์", "sites.point", "desired"),
    ("phase", "เฟส", "phases", "required"),
    ("project_parties", "บริษัทที่ผูกกับโครงการ", "project_parties", "required"),
    ("canonical.capacity.dc_it_load.phase.planned", "canonical IT load ตามแผน", "canonical_selections", "required"),
    ("canonical.regulatory.erc.generation", "canonical ใบอนุญาต กกพ.", "canonical_selections", "optional"),
    ("capacity_facts", "แถว capacity_facts", "capacity_facts", "desired"),
]


def coverage_report(conn) -> dict:
    return {
        "schema_version": "0.2",
        "types": {
            "solar_farm": _type_coverage(conn, "solar_farm", SOLAR_SLOTS),
            "data_center": _type_coverage(conn, "data_center", DC_SLOTS),
        },
        "registry_predicates": _predicates(conn),
        "notes": [
            "ช่อง desired ที่ว่างไม่ได้แปลว่าผิด — แปลว่าแหล่งยังไม่มีหลักฐาน",
            "ห้ามเติมพิกัดจากที่อยู่สำนักงานใหญ่",
            "capacity 0 ห้ามเป็น fact",
            "schema ยังไม่มี predicate solar planned จึงไม่นับ planned เป็นช่องที่เติมได้ใน v0.2.0",
        ],
    }


def _type_coverage(conn, project_type: str, slots: list[tuple[str, str, str, str]]) -> dict:
    n = conn.execute(
        "SELECT count(*) FROM intelligence.projects WHERE project_type = %s",
        (project_type,),
    ).fetchone()[0]
    filled = []
    for key, label, source, priority in slots:
        present = _count_present(conn, project_type, key) if n else 0
        filled.append(
            {
                "key": key,
                "label": label,
                "schema_object": source,
                "priority": priority,
                "present": present,
                "n": n,
                "pct": round(100.0 * present / n, 1) if n else 0.0,
            }
        )
    required = [s for s in filled if s["priority"] == "required"]
    score = round(sum(s["pct"] for s in required) / len(required), 1) if required and n else 0.0
    return {"n": n, "required_score": score, "slots": filled}


def _count_present(conn, project_type: str, key: str) -> int:
    if key == "project.name":
        sql = """
        SELECT count(*) FROM intelligence.projects
        WHERE project_type = %s AND (NULLIF(btrim(name_th),'') IS NOT NULL OR NULLIF(btrim(name_en),'') IS NOT NULL)
        """
        return conn.execute(sql, (project_type,)).fetchone()[0]
    if key == "site":
        sql = """
        SELECT count(DISTINCT p.entity_id) FROM intelligence.projects p
        JOIN intelligence.sites s ON s.project_id = p.entity_id
        WHERE p.project_type = %s
        """
        return conn.execute(sql, (project_type,)).fetchone()[0]
    if key == "site.point":
        sql = """
        SELECT count(DISTINCT p.entity_id) FROM intelligence.projects p
        JOIN intelligence.sites s ON s.project_id = p.entity_id
        WHERE p.project_type = %s AND s.point IS NOT NULL
        """
        return conn.execute(sql, (project_type,)).fetchone()[0]
    if key == "site.boundary":
        sql = """
        SELECT count(DISTINCT p.entity_id) FROM intelligence.projects p
        JOIN intelligence.sites s ON s.project_id = p.entity_id
        WHERE p.project_type = %s AND s.boundary IS NOT NULL
        """
        return conn.execute(sql, (project_type,)).fetchone()[0]
    if key == "site.province_code":
        sql = """
        SELECT count(DISTINCT p.entity_id) FROM intelligence.projects p
        JOIN intelligence.sites s ON s.project_id = p.entity_id
        WHERE p.project_type = %s AND NULLIF(btrim(s.province_code),'') IS NOT NULL
        """
        return conn.execute(sql, (project_type,)).fetchone()[0]
    if key == "phase":
        sql = """
        SELECT count(DISTINCT p.entity_id) FROM intelligence.projects p
        JOIN intelligence.sites s ON s.project_id = p.entity_id
        JOIN intelligence.phases ph ON ph.site_id = s.entity_id
        WHERE p.project_type = %s
        """
        return conn.execute(sql, (project_type,)).fetchone()[0]
    if key == "project_parties":
        sql = """
        SELECT count(DISTINCT p.entity_id) FROM intelligence.projects p
        JOIN intelligence.project_parties pp ON pp.project_id = p.entity_id
        WHERE p.project_type = %s
        """
        return conn.execute(sql, (project_type,)).fetchone()[0]
    if key == "organization.website":
        sql = """
        SELECT count(DISTINCT p.entity_id) FROM intelligence.projects p
        JOIN intelligence.project_parties pp ON pp.project_id = p.entity_id
        JOIN intelligence.entity_aliases a ON a.entity_id = pp.organization_id
        WHERE p.project_type = %s AND a.language = 'url'
        """
        return conn.execute(sql, (project_type,)).fetchone()[0]
    if key == "alias.license":
        sql = """
        SELECT count(DISTINCT p.entity_id) FROM intelligence.projects p
        JOIN intelligence.entity_aliases a ON a.entity_id = p.entity_id
        WHERE p.project_type = %s
        """
        return conn.execute(sql, (project_type,)).fetchone()[0]
    if key.startswith("canonical."):
        field = key[len("canonical.") :]
        if field == "regulatory.boi.promotion":
            sql = """
            SELECT count(DISTINCT p.entity_id) FROM intelligence.projects p
            WHERE p.project_type = %s AND (
              EXISTS (
                SELECT 1 FROM intelligence.canonical_selections cs
                WHERE cs.subject_entity_id = p.entity_id
                  AND cs.field_key = %s AND cs.superseded_at IS NULL
                  AND cs.publication_class = 'internal'
              )
              OR EXISTS (
                SELECT 1 FROM intelligence.project_parties pp
                JOIN intelligence.canonical_selections cs
                  ON cs.subject_entity_id = pp.organization_id
                 AND cs.field_key = %s AND cs.superseded_at IS NULL
                 AND cs.publication_class = 'internal'
                WHERE pp.project_id = p.entity_id
              )
            )
            """
            return conn.execute(sql, (project_type, field, field)).fetchone()[0]
        sql = """
        SELECT count(DISTINCT p.entity_id) FROM intelligence.projects p
        JOIN intelligence.canonical_selections cs
          ON cs.subject_entity_id = p.entity_id
         AND cs.field_key = %s AND cs.superseded_at IS NULL
         AND cs.publication_class = 'internal'
        WHERE p.project_type = %s
        """
        return conn.execute(sql, (field, project_type)).fetchone()[0]
    if key == "capacity_facts":
        sql = """
        SELECT count(DISTINCT p.entity_id) FROM intelligence.projects p
        JOIN intelligence.capacity_facts f ON f.subject_entity_id = p.entity_id
        WHERE p.project_type = %s
        """
        return conn.execute(sql, (project_type,)).fetchone()[0]
    if key == "milestone_facts":
        sql = """
        SELECT count(DISTINCT p.entity_id) FROM intelligence.projects p
        JOIN intelligence.milestone_facts f ON f.subject_entity_id = p.entity_id
        WHERE p.project_type = %s
        """
        return conn.execute(sql, (project_type,)).fetchone()[0]
    if key == "status_observations":
        sql = """
        SELECT count(DISTINCT p.entity_id) FROM intelligence.projects p
        JOIN intelligence.status_observations f ON f.subject_entity_id = p.entity_id
        WHERE p.project_type = %s
        """
        return conn.execute(sql, (project_type,)).fetchone()[0]
    raise ValueError(key)


def _predicates(conn) -> list[dict]:
    rows = conn.execute(
        """
        SELECT predicate, enabled FROM intelligence.predicate_registry
        WHERE registry_version = '0.2.0' ORDER BY predicate
        """
    ).fetchall()
    return [{"predicate": r[0], "enabled": r[1]} for r in rows]
