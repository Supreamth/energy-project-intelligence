"""Docs + review UI origin with HTTP Basic Auth."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse
import re

import psycopg

from energy_intelligence.catalog import save_manual_upload, upsert_sources
from energy_intelligence.catalog_html import render_sources
from energy_intelligence.product_html import render_detail, render_list
from energy_intelligence.review import (
    accept_evidence,
    attach_demo_phase,
    reject_evidence,
    select_canonical,
)
from energy_intelligence.storage import LocalObjectStore

ROOT = Path(os.environ.get("ENERISE_DOCS", "/opt/data/docs/energy-project-intelligence"))
REVIEW_HTML = Path(__file__).with_name("review.html")
AUTH_FILE = Path(os.environ.get("ENERISE_AUTH_FILE", "/opt/data/home/.enerise/auth.json"))
HOST = os.environ.get("ENERISE_BIND", "127.0.0.1")
PORT = int(os.environ.get("ENERISE_PORT", "8091"))
DSN = os.environ.get("EPI_DSN", "postgresql://hermes@127.0.0.1:55432/intelligence")
OBJECT_STORE_DIR = os.environ.get("OBJECT_STORE_DIR", "/opt/data/workspace/energy-project-intelligence/var/objects")
MAX_UPLOAD = 32 * 1024 * 1024
REALM = "Energy Project Intelligence"
DENIED_NAMES = {"serve.py", "auth.json"}


def parse_uploaded_file(content_type: str, body: bytes) -> tuple[str, bytes, str]:
    match = re.search(r"boundary=([^;]+)", content_type or "")
    if not match:
        raise ValueError("multipart boundary missing")
    boundary = match.group(1).strip().strip('"').encode()
    for part in body.split(b"--" + boundary):
        part = part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        header_blob, sep, content = part.partition(b"\r\n\r\n")
        if not sep:
            continue
        headers = header_blob.decode("utf-8", "replace")
        if 'name="file"' not in headers and "name=file" not in headers:
            continue
        filename = "upload.bin"
        found = re.search(r'filename="([^"]*)"', headers)
        if found and found.group(1):
            filename = found.group(1)
        ctype = "application/octet-stream"
        found_type = re.search(r"Content-Type:\s*([^\r\n]+)", headers, re.I)
        if found_type:
            ctype = found_type.group(1).strip()
        if content.endswith(b"\r\n"):
            content = content[:-2]
        if content.endswith(b"--"):
            content = content[:-2].rstrip(b"\r\n")
        return filename, content, ctype
    raise ValueError("file field missing")


def load_auth() -> dict:
    data = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    return data


AUTH = load_auth()


def verify(username: str, password: str) -> bool:
    if not hmac.compare_digest(username.encode("utf-8"), AUTH["username"].encode("utf-8")):
        return False
    salt = bytes.fromhex(AUTH["salt_hex"])
    expected = bytes.fromhex(AUTH["hash_hex"])
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(AUTH.get("iterations", 200_000)))
    return hmac.compare_digest(actual, expected)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _unauthorized(self) -> None:
        self.send_response(401)
        self.send_header("WWW-Authenticate", f'Basic realm="{REALM}", charset="UTF-8"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        body = b"Authentication required\n"
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
            username, password = decoded.split(":", 1)
        except Exception:
            return False
        return verify(username, password)

    def translate_path(self, path: str) -> str:
        translated = super().translate_path(path)
        rel = Path(translated).resolve()
        try:
            rel.relative_to(ROOT)
        except ValueError:
            return str(ROOT / "__denied__")
        if rel.name.startswith(".") or rel.name in DENIED_NAMES:
            return str(ROOT / "__denied__")
        return str(rel)

    def do_HEAD(self) -> None:
        if not self._authorized():
            self._unauthorized()
            return
        parsed = urlparse(self.path)
        if parsed.path in ("/review", "/review/"):
            data = REVIEW_HTML.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            return
        super().do_HEAD()

    def do_GET(self) -> None:
        if not self._authorized():
            self._unauthorized()
            return
        parsed = urlparse(self.path)
        if parsed.path in ("/review", "/review/"):
            data = REVIEW_HTML.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if parsed.path == "/review/api/evidence":
            self._json(200, _list_evidence())
            return
        if parsed.path in ("/sources", "/sources/"):
            notice = (parse_qs(parsed.query).get("notice") or [None])[0]
            self._html(render_sources(notice=notice))
            return
        if parsed.path in ("/projects", "/projects/"):
            ptype = (parse_qs(parsed.query).get("type") or [None])[0]
            with psycopg.connect(DSN) as conn:
                data = render_list(conn, ptype)
            self._html(data)
            return
        match = re.fullmatch(r"/projects/([0-9a-fA-F-]{36})", parsed.path)
        if match:
            with psycopg.connect(DSN) as conn:
                try:
                    data = render_detail(conn, match.group(1))
                except ValueError:
                    self.send_error(404, "project not found")
                    return
            self._html(data)
            return
        if Path(self.translate_path(unquote(self.path))).name == "__denied__":
            self.send_error(403, "Forbidden")
            return
        super().do_GET()

    def do_POST(self) -> None:
        if not self._authorized():
            self._unauthorized()
            return
        parsed = urlparse(self.path)
        upload = re.fullmatch(r"/sources/([A-Za-z0-9_]+)/upload", parsed.path)
        if upload:
            self._handle_upload(upload.group(1))
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid json"})
            return
        try:
            result = _handle_post(parsed.path, payload)
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
            return
        except Exception as exc:
            self._json(500, {"error": str(exc)})
            return
        self._json(200, result)

    def _handle_upload(self, source_code: str) -> None:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > MAX_UPLOAD:
            self._redirect_notice("ไฟล์ใหญ่เกิน 32MB", source_code)
            return
        body = self.rfile.read(length) if length else b""
        try:
            filename, payload, content_type = parse_uploaded_file(self.headers.get("Content-Type", ""), body)
            store = LocalObjectStore(OBJECT_STORE_DIR)
            with psycopg.connect(DSN) as conn:
                result = save_manual_upload(
                    conn,
                    store,
                    source_code=source_code,
                    filename=filename,
                    payload=payload,
                    content_type=content_type,
                )
                conn.commit()
        except ValueError as exc:
            self._redirect_notice(str(exc), source_code)
            return
        notice = (
            f"อัปโหลด {filename} เข้า {source_code} แล้ว "
            f"raw={result.raw_record_id} created={result.raw_created}"
        )
        self._redirect_notice(notice, source_code)

    def _redirect_notice(self, notice: str, source_code: str) -> None:
        loc = f"/sources?notice={quote(notice)}#{source_code}"
        self.send_response(303)
        self.send_header("Location", loc)
        self.end_headers()

    def _html(self, data: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status: int, payload: dict | list) -> None:
        data = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _list_evidence() -> list[dict]:
    with psycopg.connect(DSN) as conn:
        rows = conn.execute(
            """
            SELECT ev.id, ev.predicate, ev.value_json, ev.review_status, ev.excerpt,
                   ev.subject_entity_id, r.external_key, p.name_th, p.project_type
            FROM intelligence.evidence ev
            JOIN intelligence.raw_records r ON r.id = ev.raw_record_id
            LEFT JOIN intelligence.projects p ON p.entity_id = ev.subject_entity_id
            ORDER BY CASE ev.review_status WHEN 'pending' THEN 0 ELSE 1 END, ev.recorded_at DESC
            LIMIT 400
            """
        ).fetchall()
    out = []
    for row in rows:
        out.append(
            {
                "id": str(row[0]),
                "predicate": row[1],
                "value_json": row[2],
                "review_status": row[3],
                "excerpt": row[4],
                "subject_entity_id": str(row[5]) if row[5] else None,
                "external_key": row[6],
                "project_name": row[7],
                "project_type": row[8],
            }
        )
    return out


def _handle_post(path: str, payload: dict) -> dict:
    evidence_id = uuid.UUID(payload["id"])
    reason = payload.get("reason") or path
    actor = "reviewer"
    with psycopg.connect(DSN) as conn:
        if path.endswith("/attach"):
            phase_id = attach_demo_phase(conn, evidence_id=evidence_id)
            conn.commit()
            return {"ok": True, "phase_id": str(phase_id)}
        if path.endswith("/accept"):
            accept_evidence(conn, evidence_id=evidence_id, actor=actor, reason=reason)
            conn.commit()
            return {"ok": True}
        if path.endswith("/reject"):
            reject_evidence(conn, evidence_id=evidence_id, actor=actor, reason=reason)
            conn.commit()
            return {"ok": True}
        if path.endswith("/canonical"):
            field_key = payload.get("field_key")
            if not field_key:
                raise ValueError("field_key required")
            select_canonical(
                conn,
                evidence_id=evidence_id,
                field_key=field_key,
                actor=actor,
                reason=reason,
            )
            conn.commit()
            return {"ok": True}
    raise ValueError("unknown action")


class ReusableServer(ThreadingHTTPServer):
    allow_reuse_address = True


def main() -> None:
    with psycopg.connect(DSN) as conn:
        n = upsert_sources(conn)
        conn.commit()
        print(f"catalog upserted {n} sources", flush=True)
    server = ReusableServer((HOST, PORT), Handler)
    print(f"docs+review http://{HOST}:{PORT}/ sources=/sources review=/review", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
