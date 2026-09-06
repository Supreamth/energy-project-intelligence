"""Product reads canonical values only."""

from __future__ import annotations

import uuid


def list_projects(conn, project_type: str | None = None) -> list[dict]:
    if project_type:
        rows = conn.execute(
            """
            SELECT entity_id, name_en, name_th, project_type
            FROM intelligence.projects
            WHERE project_type = %s
            ORDER BY coalesce(name_en, name_th)
            """,
            (project_type,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT entity_id, name_en, name_th, project_type
            FROM intelligence.projects
            ORDER BY coalesce(name_en, name_th)
            """
        ).fetchall()
    return [
        {
            "id": str(row[0]),
            "name": row[1] or row[2],
            "name_en": row[1],
            "name_th": row[2],
            "project_type": row[3],
        }
        for row in rows
    ]


def get_project(conn, project_id) -> dict:
    project_id = uuid.UUID(str(project_id))
    row = conn.execute(
        """
        SELECT entity_id, name_en, name_th, project_type
        FROM intelligence.projects WHERE entity_id = %s
        """,
        (project_id,),
    ).fetchone()
    if row is None:
        raise ValueError("project not found")
    sites = conn.execute(
        """
        SELECT entity_id, label FROM intelligence.sites
        WHERE project_id = %s ORDER BY label
        """,
        (project_id,),
    ).fetchall()
    phases = conn.execute(
        """
        SELECT ph.entity_id, ph.label, ph.phase_key, s.label
        FROM intelligence.phases ph
        JOIN intelligence.sites s ON s.entity_id = ph.site_id
        WHERE s.project_id = %s
        ORDER BY ph.phase_key
        """,
        (project_id,),
    ).fetchall()
    subject_ids = [project_id] + [s[0] for s in sites] + [p[0] for p in phases]
    canonical = conn.execute(
        """
        SELECT cs.field_key, cs.evidence_id, ev.value_json, ev.excerpt, ev.predicate, cs.reason
        FROM intelligence.canonical_selections cs
        JOIN intelligence.evidence ev ON ev.id = cs.evidence_id
        WHERE cs.superseded_at IS NULL
          AND cs.publication_class = 'internal'
          AND cs.subject_entity_id = ANY(%s)
        """,
        (subject_ids,),
    ).fetchall()
    capacity = []
    field_keys = []
    canonical_ids = set()
    for field_key, evidence_id, value_json, excerpt, predicate, reason in canonical:
        field_keys.append(predicate)
        canonical_ids.add(evidence_id)
        parts = field_key.split(".")
        capacity.append(
            {
                "field_key": field_key,
                "metric": parts[1] if len(parts) > 1 else field_key,
                "scope": value_json.get("scope") if isinstance(value_json, dict) else None,
                "capacity_status": value_json.get("capacity_status") if isinstance(value_json, dict) else None,
                "value": value_json.get("value") if isinstance(value_json, dict) else value_json,
                "unit": value_json.get("unit") if isinstance(value_json, dict) else None,
                "evidence_id": str(evidence_id),
                "excerpt": excerpt,
                "reason": reason,
            }
        )
    conflicts = []
    if field_keys:
        conf_rows = conn.execute(
            """
            SELECT ev.id, ev.value_json, ev.excerpt, ev.predicate
            FROM intelligence.evidence ev
            WHERE ev.subject_entity_id = ANY(%s)
              AND ev.review_status = 'accepted'
              AND ev.predicate = ANY(%s)
              AND NOT (ev.id = ANY(%s))
            """,
            (subject_ids, field_keys, list(canonical_ids) or [uuid.UUID(int=0)]),
        ).fetchall()
        for evidence_id, value_json, excerpt, predicate in conf_rows:
            conflicts.append(
                {
                    "evidence_id": str(evidence_id),
                    "predicate": predicate,
                    "value": value_json.get("value") if isinstance(value_json, dict) else value_json,
                    "excerpt": excerpt,
                }
            )
    return {
        "id": str(row[0]),
        "name": row[1] or row[2],
        "name_en": row[1],
        "name_th": row[2],
        "project_type": row[3],
        "sites": [{"id": str(s[0]), "label": s[1]} for s in sites],
        "phases": [{"id": str(p[0]), "label": p[1], "phase_key": p[2], "site": p[3]} for p in phases],
        "capacity": capacity,
        "conflicts": conflicts,
    }
