"""Private local object store for raw payloads. Not a public bucket."""

from __future__ import annotations

import hashlib
from pathlib import Path


class LocalObjectStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, source_code: str, data: bytes, content_type: str) -> dict[str, str]:
        digest = hashlib.sha256(data).hexdigest()
        dest = self.root / source_code / digest
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            dest.write_bytes(data)
        return {
            "sha256": digest,
            "uri": f"object://raw/{source_code}/{digest}",
            "path": str(dest),
            "content_type": content_type,
        }

    def get(self, source_code: str, sha256: str) -> bytes:
        return (self.root / source_code / sha256).read_bytes()
