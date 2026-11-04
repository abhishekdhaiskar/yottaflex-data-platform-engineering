"""Identifier + hashing helpers (single place for naming conventions)."""

import hashlib
import uuid
from datetime import datetime


def file_sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def make_quarantine_id(sha256: str, line: int) -> str:
    """Deterministic: same file content + same line => same id (re-ingest never duplicates rejects)."""
    return "q_" + hashlib.sha1(f"{sha256}:{line}".encode()).hexdigest()[:16]


def new_run_id(prefix: str, now: datetime) -> str:
    """Unique per execution by design: <type>_<UTC timestamp>_<6 hex>."""
    return f"{prefix}_{now:%Y%m%dT%H%M%SZ}_{uuid.uuid4().hex[:6]}"
