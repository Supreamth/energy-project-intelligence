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


def known_source_codes() -> set[str]:
    return {row["code"] for row in load_sources()}


def save_manual_upload(conn, store, *, source_code: str, filename: str, payload: bytes, content_type: str):
    from energy_intelligence.ingest import import_snapshot

    if source_code not in known_source_codes():
        raise ValueError(f"unknown source: {source_code}")
    if not payload:
        raise ValueError("empty file")
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in (filename or "upload.bin"))[:180]
    return import_snapshot(
        conn,
        store,
        source_code=source_code,
        external_key=f"upload:{safe}",
        payload=payload,
        content_type=content_type or "application/octet-stream",
        extractor_version="manual-upload-0.1",
        source_url=f"upload://{source_code}/{safe}",
    )
