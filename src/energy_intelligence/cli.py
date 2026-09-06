"""CLI for manual contract import."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg

from energy_intelligence.ingest import import_contract
from energy_intelligence.storage import LocalObjectStore

DEFAULT_DSN = "postgresql://hermes@127.0.0.1:55432/intelligence"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(prog="epi")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_import = sub.add_parser("import", help="Import a schema v0.2 JSON contract")
    p_import.add_argument("path")
    args = parser.parse_args(argv)
    if args.cmd == "import":
        return _import_path(Path(args.path))
    return 2


def _import_path(path: Path) -> int:
    contract = json.loads(path.read_text(encoding="utf-8"))
    store = LocalObjectStore(os.environ.get("OBJECT_STORE_DIR", "var/objects"))
    dsn = os.environ.get("EPI_DSN", DEFAULT_DSN)
    with psycopg.connect(dsn) as conn:
        result = import_contract(conn, store, contract)
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


if __name__ == "__main__":
    raise SystemExit(main())
