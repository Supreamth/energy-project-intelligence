"""Attach operator websites and published plant coordinates.

Never geocode headquarters. A point is written only when name_contains
matches exactly one solar project for that licensee in that province.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parents[2] / "catalog" / "operators.json"


def load_operator_catalog(path: Path | None = None) -> list[dict]:
    return json.loads((path or CATALOG_PATH).read_text(encoding="utf-8"))


def apply_operator_research(conn, *, catalog: list[dict] | None = None, store=None) -> dict:
    catalog = catalog if catalog is not None else load_operator_catalog()
    websites = 0
    points = 0
    skipped_ambiguous = 0
    for row in catalog:
        legal = row.get("legal_name") or ""
        org = conn.execute(
            "SELECT entity_id FROM intelligence.organizations WHERE legal_name = %s LIMIT 1",
            (legal,),
        ).fetchone()
        if org is None:
            continue
        org_id = org[0]
        website = (row.get("website") or "").strip()
        if website:
            exists = conn.execute(
                """
                SELECT 1 FROM intelligence.entity_aliases
                WHERE entity_id = %s AND alias = %s
                """,
                (org_id, website),
            ).fetchone()
            if not exists:
                conn.execute(
                    """
                    INSERT INTO intelligence.entity_aliases(id, entity_id, alias, language)
                    VALUES (%s, %s, %s, 'url')
                    """,
                    (uuid.uuid4(), org_id, website),
                )
                websites += 1
        for site in row.get("sites") or []:
            needle = site.get("name_contains") or ""
            province = site.get("province") or ""
            lat = site.get("lat")
            lon = site.get("lon")
            if not needle or lat is None or lon is None:
                continue
            matches = conn.execute(
                """
                SELECT s.entity_id
                FROM intelligence.projects p
                JOIN intelligence.sites s ON s.project_id = p.entity_id
                WHERE p.project_type = 'solar_farm'
                  AND p.name_th ILIKE %s
                  AND (
                    %s = ''
                    OR s.province_code = %s
                    OR EXISTS (
                      SELECT 1 FROM intelligence.evidence evp
                      WHERE evp.subject_entity_id = p.entity_id
                        AND evp.predicate = 'regulatory.erc.generation'
                        AND evp.value_json->>'province' = %s
                    )
                  )
                  AND s.point IS NULL
                  AND (
                    EXISTS (
                      SELECT 1 FROM intelligence.project_parties pp
                      WHERE pp.project_id = p.entity_id AND pp.organization_id = %s
                    )
                    OR EXISTS (
                      SELECT 1 FROM intelligence.evidence ev
                      WHERE ev.subject_entity_id = p.entity_id
                        AND ev.predicate = 'regulatory.erc.generation'
                        AND ev.value_json->>'licensee' = %s
                    )
                  )
                """,
                (f"%{needle}%", province, province, province, org_id, legal),
            ).fetchall()
            if len(matches) != 1:
                skipped_ambiguous += 1
                continue
            conn.execute(
                """
                UPDATE intelligence.sites
                SET point = ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                    location_method = %s,
                    location_accuracy_m = %s
                WHERE entity_id = %s
                """,
                (
                    float(lon),
                    float(lat),
                    site.get("location_method") or "operator_publication",
                    site.get("accuracy_m"),
                    matches[0][0],
                ),
            )
            points += 1
    return {
        "websites": websites,
        "points": points,
        "skipped_ambiguous": skipped_ambiguous,
        "operators": len(catalog),
    }
