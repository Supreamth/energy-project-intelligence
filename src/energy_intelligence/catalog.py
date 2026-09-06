"""Target source catalog. Extra connection notes live in JSON, not extra SQL columns."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[2] / "catalog" / "sources.json"


def load_sources() -> list[dict]:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def upsert_sources(conn, rows: list[dict] | None = None) -> int:
    rows = rows if rows is not None else load_sources()
    n = 0
    for row in rows:
        existing = conn.execute(
            "SELECT id FROM intelligence.sources WHERE code = %s",
            (row["code"],),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE intelligence.sources
                SET name = %s, base_url = %s, access_method = %s,
                    rights_status = %s, schedule = %s, enabled = %s
                WHERE code = %s
                """,
                (
                    row["name_en"],
                    row["base_url"],
                    row["access_method"],
                    row["rights_status"],
                    row.get("schedule"),
                    bool(row.get("enabled")),
                    row["code"],
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO intelligence.sources(
                  id, code, name, base_url, access_method, rights_status, schedule, enabled
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    uuid.uuid4(),
                    row["code"],
                    row["name_en"],
                    row["base_url"],
                    row["access_method"],
                    row["rights_status"],
                    row.get("schedule"),
                    bool(row.get("enabled")),
                ),
            )
        n += 1
    return n
