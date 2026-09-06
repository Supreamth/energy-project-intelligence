#!/usr/bin/env python3
"""Local origin for Energy Project Intelligence docs with HTTP Basic Auth."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent
AUTH_FILE = Path(os.environ.get("ENERISE_AUTH_FILE", "/opt/data/home/.enerise/auth.json"))
HOST = os.environ.get("ENERISE_BIND", "127.0.0.1")
PORT = int(os.environ.get("ENERISE_PORT", "8091"))
REALM = "Energy Project Intelligence"
HIDDEN = {".", ".."}
DENIED_NAMES = {"serve.py", "auth.json"}


def load_auth() -> dict:
    data = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    if not data.get("username") or not data.get("salt_hex") or not data.get("hash_hex"):
        raise RuntimeError(f"invalid auth file: {AUTH_FILE}")
    return data


AUTH = load_auth()


def verify(username: str, password: str) -> bool:
    if not hmac.compare_digest(username.encode("utf-8"), AUTH["username"].encode("utf-8")):
        return False
    salt = bytes.fromhex(AUTH["salt_hex"])
    expected = bytes.fromhex(AUTH["hash_hex"])
    iterations = int(AUTH.get("iterations", 200_000))
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        sys_stderr = super().log_message
        # Never log Authorization headers; default log is method/path/status only.
        sys_stderr(fmt, *args)

    def _unauthorized(self) -> None:
        self.send_response(401)
        self.send_header("WWW-Authenticate", f'Basic realm="{REALM}", charset="UTF-8"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        body = b"Authentication required\n"
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _forbidden(self) -> None:
        self.send_error(403, "Forbidden")

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
        name = rel.name
        if name.startswith(".") or name in DENIED_NAMES or name in HIDDEN:
            return str(ROOT / "__denied__")
        return str(rel)

    def do_HEAD(self) -> None:
        if not self._authorized():
            self._unauthorized()
            return
        if Path(self.translate_path(unquote(self.path))).name == "__denied__":
            self._forbidden()
            return
        super().do_HEAD()

    def do_GET(self) -> None:
        if not self._authorized():
            self._unauthorized()
            return
        if Path(self.translate_path(unquote(self.path))).name == "__denied__":
            self._forbidden()
            return
        super().do_GET()

    def do_POST(self) -> None:
        self.send_error(405, "Method Not Allowed")


class ReusableServer(ThreadingHTTPServer):
    allow_reuse_address = True


def main() -> None:
    server = ReusableServer((HOST, PORT), Handler)
    print(f"enerise origin http://{HOST}:{PORT}/ (basic auth, root={ROOT})", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
