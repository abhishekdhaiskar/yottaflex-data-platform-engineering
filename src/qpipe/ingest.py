"""Ingest: read CSV -> schema check -> validate -> dedupe -> publish -> quarantine rejects.

One ingest = ONE transaction. Any crash rolls back everything, the run is marked FAILED,
and the same command can simply be retried.
"""

import csv
import json
import logging
import os
from dataclasses import dataclass

from . import loader
from .config import DEFAULT_RULES, DEFAULT_SETTINGS, Rules
from .db import iso, utc_now
from .ids import file_sha256, make_quarantine_id, new_run_id
from .runs import RunResult, finish_run, start_run
from .validation import DUPLICATE_CONFLICT, MALFORMED_ROW, REQUIRED, validate_record

log = logging.getLogger("qpipe")


class SchemaError(Exception):
    """Structural problem with the file (no header / missing required column)."""


@dataclass
class Reject:
    ref: int  # source line number
    raw: dict
    errors: list  # [(error_code, message)]


def conflict_error(scope: str) -> tuple:
    return (DUPLICATE_CONFLICT, f"same order_id+updated_at as {scope} with different content")


def read_orders(path):
    """Returns (header, extra_columns, [(line_no, fields)]). Raises SchemaError on structural problems."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            raise SchemaError("empty file: no header row") from None
        header = [h.strip().lower() for h in header]
        missing = [c for c in REQUIRED if c not in header]
        if missing:
            raise SchemaError(f"schema mismatch: missing required columns {missing}; got {header}")
        extra = [h for h in header if h not in REQUIRED]
        rows = [
            (reader.line_num, fields) for fields in reader if fields and any(x.strip() for x in fields)
        ]  # blank lines ignored
    return header, extra, rows


def get_known_customers(conn) -> set:
    return {r[0] for r in conn.execute("SELECT customer_id FROM dim_customer")}


def classify_rows(rows, header, customers, rules: Rules):
    """Split raw rows into (items to publish, rejects, exact_duplicates_dropped). Pure: no DB access."""
    items, rejects, seen, dup_dropped = [], [], {}, 0
    for line, fields in rows:
        if len(fields) != len(header):
            rejects.append(
                Reject(
                    line,
                    {"_malformed": True, "fields": fields},
                    [(MALFORMED_ROW, f"expected {len(header)} fields, got {len(fields)}")],
                )
            )
            continue
        raw = dict(zip(header, fields, strict=False))
        rec, errs = validate_record(raw, customers, rules)
        if errs:
            rejects.append(Reject(line, raw, errs))
            continue
        key = (rec.order_id, rec.updated_at)
        if key in seen:
            if seen[key] == rec.record_hash:
                dup_dropped += 1  # exact duplicate: dropped but counted
            else:
                rejects.append(Reject(line, raw, [conflict_error("an earlier row in this file")]))
            continue
        seen[key] = rec.record_hash
        items.append(loader.Item(line, raw, rec))
    return items, rejects, dup_dropped


def write_rejects(conn, rejects, run_id, source_file, sha, now) -> None:
    rows = [
        (
            make_quarantine_id(sha, rj.ref),
            run_id,
            source_file,
            rj.ref,
            json.dumps(rj.raw, sort_keys=True),
            json.dumps([e[0] for e in rj.errors]),
            json.dumps([e[1] for e in rj.errors]),
            iso(now),
        )
        for rj in rejects
    ]
    # OR IGNORE => forced re-ingest keeps existing (maybe RESOLVED) quarantine rows untouched
    conn.executemany(
        "INSERT OR IGNORE INTO quarantine (quarantine_id, run_id, source_file, source_line, raw_record,"
        " error_codes, error_messages, created_at) VALUES (?,?,?,?,?,?,?,?)",
        rows,
    )


def _skip_if_already_ingested(conn, res, sha, now) -> bool:
    prior = conn.execute(
        "SELECT run_id FROM pipeline_run WHERE file_sha256=? AND run_type='ingest' AND status='SUCCESS'", (sha,)
    ).fetchone()
    if not prior:
        return False
    res.status = "SKIPPED"
    res.error_message = f"identical file already ingested by run {prior[0]} (use --force to re-run)"
    return True


def ingest_file(
    conn, path, force=False, chunk_size=DEFAULT_SETTINGS.chunk_size, now=None, rules: Rules = DEFAULT_RULES
) -> RunResult:
    now = now or utc_now()
    source_file = os.path.basename(str(path))
    sha = file_sha256(path)
    res = RunResult(new_run_id("ingest", now), "ingest", source_file)

    start_run(conn, res.run_id, "ingest", now, source_file, sha)
    if not force and _skip_if_already_ingested(conn, res, sha, now):
        finish_run(conn, res, utc_now())
        return res
    try:
        header, extra, rows = read_orders(path)
        if extra:
            res.warnings.append(f"unexpected extra columns ignored: {extra}")
            log.warning("run_id=%s %s", res.run_id, res.warnings[-1])
        res.rows_read = len(rows)

        items, rejects, res.rows_dup_dropped = classify_rows(rows, header, get_known_customers(conn), rules)
        for it, outcome in loader.load_orders(conn, items, res.run_id, source_file, iso(now), chunk_size):
            if outcome == loader.CONFLICT:
                rejects.append(Reject(it.ref, it.raw, [conflict_error("an already-loaded version")]))
            else:
                res.record_outcome(outcome)
        res.rows_quarantined = len(rejects)
        if res.rows_read != res.rows_valid + res.rows_dup_dropped + res.rows_quarantined:
            raise RuntimeError("count identity broken: read != valid + dup_dropped + quarantined")
        write_rejects(conn, rejects, res.run_id, source_file, sha, now)
        conn.commit()  # single commit => atomic batch
        res.status = "SUCCESS"
    except Exception as exc:  # noqa: BLE001 - recorded + exit code 1
        conn.rollback()
        res.fail(exc)
    finish_run(conn, res, utc_now())
    return res
