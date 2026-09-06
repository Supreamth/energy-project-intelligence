"""Attach GPPD coordinates only on exact normalized name matches."""

from __future__ import annotations

import csv
import io
import re
import uuid

from energy_intelligence.ingest import import_snapshot


def normalize_name(value: str) -> str:
    text = (value or "").casefold()
    text = text.replace("solar power plant", " ")
    text = text.replace("solar farm", " ")
    text = re.sub(r"[^\wก-๙]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def apply_gppd_coordinates(conn, store, csv_bytes: bytes) -> dict:
    snap = import_snapshot(
        conn,
        store,
        source_code="wri_gppd",
        external_key="gppd-global-csv",
        payload=csv_bytes,
        content_type="text/csv",
        extractor_version="gppd-name-match-0.1",
        source_url="https://github.com/wri/global-power-plant-database",
    )
    rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8"))))
    plants = [
        r
        for r in rows
        if r.get("country_long") == "Thailand" and (r.get("primary_fuel") or "").lower() == "solar"
    ]
    projects = conn.execute(
        "SELECT entity_id, name_th, name_en FROM intelligence.projects WHERE project_type = 'solar_farm'"
    ).fetchall()
    by_name: dict[str, list] = {}
    for entity_id, name_th, name_en in projects:
        for raw in (name_th, name_en):
            key = normalize_name(raw or "")
            if key:
                by_name.setdefault(key, []).append(entity_id)
    matched = 0
    skipped_ambiguous = 0
    no_geo = 0
    for plant in plants:
        key = normalize_name(plant.get("name") or "")
        if not key or key not in by_name:
            continue
        ids = list(dict.fromkeys(by_name[key]))
        if len(ids) != 1:
            skipped_ambiguous += 1
            continue
        try:
            lat = float(plant["latitude"])
            lon = float(plant["longitude"])
        except (TypeError, ValueError, KeyError):
            no_geo += 1
            continue
        site = conn.execute(
            """
            SELECT entity_id FROM intelligence.sites
            WHERE project_id = %s AND point IS NULL
            ORDER BY label LIMIT 1
            """,
            (ids[0],),
        ).fetchone()
        if not site:
            continue
        conn.execute(
            """
            UPDATE intelligence.sites
            SET point = ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                location_method = 'gppd_exact_name'
            WHERE entity_id = %s
            """,
            (lon, lat, site[0]),
        )
        matched += 1
    return {
        "raw_created": snap.raw_created,
        "thailand_solar_rows": len(plants),
        "matched_points": matched,
        "skipped_ambiguous": skipped_ambiguous,
        "no_geo": no_geo,
    }
