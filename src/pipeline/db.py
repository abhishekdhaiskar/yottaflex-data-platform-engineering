"""SQLite storage layer: schema + connection helper (stdlib only, zero setup)."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS dim_customer (
    customer_id   TEXT PRIMARY KEY,
    customer_name TEXT NOT NULL,
    country_code  TEXT NOT NULL,
    run_id        TEXT NOT NULL,
    source_file   TEXT NOT NULL
);

-- Current state of each order (1 row per order_id)
CREATE TABLE IF NOT EXISTS fact_order (
    order_id          TEXT PRIMARY KEY,
    customer_id       TEXT NOT NULL REFERENCES dim_customer(customer_id),
    order_ts          TEXT NOT NULL,
    amount_cents      INTEGER NOT NULL CHECK (amount_cents > 0),
    currency          TEXT NOT NULL,
    status            TEXT NOT NULL,
    source_updated_at TEXT NOT NULL,   -- version of the record (from source)
    record_hash       TEXT NOT NULL,
    run_id            TEXT NOT NULL,
    source_file       TEXT NOT NULL,
    loaded_at         TEXT NOT NULL
);

-- Append-only history: every accepted version of every order is kept
CREATE TABLE IF NOT EXISTS fact_order_history (
    order_id          TEXT NOT NULL,
    source_updated_at TEXT NOT NULL,
    customer_id       TEXT NOT NULL,
    order_ts          TEXT NOT NULL,
    amount_cents      INTEGER NOT NULL,
    currency          TEXT NOT NULL,
    status            TEXT NOT NULL,
    record_hash       TEXT NOT NULL,
    run_id            TEXT NOT NULL,
    source_file       TEXT NOT NULL,
    loaded_at         TEXT NOT NULL,
    PRIMARY KEY (order_id, source_updated_at)
);

-- Rejected records: raw payload + why + where it came from
CREATE TABLE IF NOT EXISTS quarantine (
    quarantine_id   TEXT PRIMARY KEY,      -- deterministic: sha1(file_sha256:line)
    run_id          TEXT NOT NULL,         -- run that rejected it
    source_file     TEXT NOT NULL,
    source_line     INTEGER NOT NULL,
    raw_record      TEXT NOT NULL,         -- JSON, never modified after insert
    error_codes     TEXT NOT NULL,         -- JSON list: ORIGINAL rejection reason (immutable)
    error_messages  TEXT NOT NULL,         -- JSON list (immutable)
    last_error_codes    TEXT,              -- JSON list: reason of the latest failed replay attempt
    last_error_messages TEXT,
    status          TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','RESOLVED')),
    attempts        INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    last_attempt_at TEXT,
    resolved_run_id TEXT,
    corrections     TEXT                   -- JSON of operator corrections applied
);

CREATE TABLE IF NOT EXISTS pipeline_run (
    run_id           TEXT PRIMARY KEY,
    run_type         TEXT NOT NULL,        -- ingest | replay | customers
    source_file      TEXT,
    file_sha256      TEXT,
    status           TEXT NOT NULL,        -- RUNNING | SUCCESS | FAILED | SKIPPED
    started_at       TEXT NOT NULL,
    ended_at         TEXT,
    rows_read        INTEGER DEFAULT 0,
    rows_valid       INTEGER DEFAULT 0,
    rows_inserted    INTEGER DEFAULT 0,
    rows_updated     INTEGER DEFAULT 0,
    rows_late        INTEGER DEFAULT 0,
    rows_unchanged   INTEGER DEFAULT 0,
    rows_dup_dropped INTEGER DEFAULT 0,
    rows_quarantined INTEGER DEFAULT 0,
    error_message    TEXT,
    warnings         TEXT
);
CREATE INDEX IF NOT EXISTS ix_quarantine_status ON quarantine(status);
CREATE INDEX IF NOT EXISTS ix_run_sha ON pipeline_run(file_sha256, status);
"""


def connect(db_path="data/warehouse.db") -> sqlite3.Connection:
    db_path = str(db_path)
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def iso(dt: datetime) -> str:
    """ISO-8601 UTC, second precision, e.g. 2026-03-01T10:00:00Z"""
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_now() -> datetime:
    return datetime.now(UTC)
