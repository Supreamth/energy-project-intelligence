"""CLI for manual contract import and raw snapshots."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg

from energy_intelligence.ingest import import_contract, import_snapshot, record_fetch_failure
from energy_intelligence.storage import LocalObjectStore

DEFAULT_DSN = "postgresql://hermes@127.0.0.1:55432/intelligence"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(prog="epi")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_import = sub.add_parser("import", help="Import a schema v0.2 JSON contract")
    p_import.add_argument("path")
    p_snap = sub.add_parser("snapshot", help="Import raw bytes from a public page")
    p_snap.add_argument("path")
    p_snap.add_argument("--source", required=True)
    p_snap.add_argument("--key", required=True)
    p_snap.add_argument("--url")
    p_snap.add_argument("--content-type", default="text/html; charset=utf-8")
    p_snap.add_argument("--extractor", default="erc-hub-html-0.1")
    p_fail = sub.add_parser("fetch-fail", help="Record a failed fetch without raw")
    p_fail.add_argument("--source", required=True)
    p_fail.add_argument("--error-class", required=True)
    p_fail.add_argument("--url", required=True)
    args = parser.parse_args(argv)
    if args.cmd == "import":
        return _import_path(Path(args.path))
    if args.cmd == "snapshot":
        return _snapshot(args)
    if args.cmd == "fetch-fail":
        return _fetch_fail(args)
    return 2


def _store() -> LocalObjectStore:
    return LocalObjectStore(os.environ.get("OBJECT_STORE_DIR", "var/objects"))


def _dsn() -> str:
    return os.environ.get("EPI_DSN", DEFAULT_DSN)


def _import_path(path: Path) -> int:
    contract = json.loads(path.read_text(encoding="utf-8"))
    with psycopg.connect(_dsn()) as conn:
        result = import_contract(conn, _store(), contract)
        conn.commit()
    print(
        json.dumps(
            {
                "raw_record_id": str(result.raw_record_id),
                "run_id": str(result.run_id),
                "raw_created": result.raw_created,
                "evidence_inserted": result.evidence_inserted,
            }
        )
    )
    return 0


def _snapshot(args) -> int:
    payload = Path(args.path).read_bytes()
    with psycopg.connect(_dsn()) as conn:
        result = import_snapshot(
            conn,
            _store(),
            source_code=args.source,
            external_key=args.key,
            payload=payload,
            content_type=args.content_type,
            extractor_version=args.extractor,
            source_url=args.url,
        )
        conn.commit()
    print(
        json.dumps(
            {
                "raw_record_id": str(result.raw_record_id),
                "run_id": str(result.run_id),
                "raw_created": result.raw_created,
                "bytes": len(payload),
            }
        )
    )
    return 0


def _fetch_fail(args) -> int:
    with psycopg.connect(_dsn()) as conn:
        event_id = record_fetch_failure(
            conn,
            source_code=args.source,
            error_class=args.error_class,
            error_summary={"url": args.url},
        )
        conn.commit()
    print(json.dumps({"fetch_event_id": str(event_id), "raw_record_id": None}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
