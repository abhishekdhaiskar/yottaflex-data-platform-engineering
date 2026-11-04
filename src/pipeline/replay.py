"""Controlled replay of quarantined records.

Only rows in quarantine with status PENDING (and matching the operator's filters) are touched.
Successfully loaded data is never re-read. Raw payloads are immutable: operator corrections are
applied on top at replay time and stored alongside, so the audit trail stays intact.

Two ways to fix a record (or combine them):
  1. Fix the CAUSE (e.g. load the missing customer) -> replay with no corrections.
  2. Provide a corrections CSV: quarantine_id,field,new_value
"""

import csv
import json
import logging

from . import loader
from .config import DEFAULT_RULES, DEFAULT_SETTINGS, Rules
from .db import iso, utc_now
from .ids import new_run_id
from .ingest import conflict_error, get_known_customers
from .runs import RunResult, finish_run, start_run
from .validation import MALFORMED_ROW, validate_record

log = logging.getLogger("qpipe")


def read_corrections(path):
    out = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            out.setdefault(r["quarantine_id"].strip(), {})[r["field"].strip().lower()] = r["new_value"]
    return out


def select_pending(conn, error_code=None, source_run_id=None, source_file=None, ids=None, limit=None):
    sql, args = "SELECT * FROM quarantine WHERE status='PENDING'", []
    if error_code:
        sql += " AND error_codes LIKE ?"
        args.append(f'%"{error_code}"%')
    if source_run_id:
        sql += " AND run_id=?"
        args.append(source_run_id)
    if source_file:
        sql += " AND source_file=?"
        args.append(source_file)
    if ids:
        sql += f" AND quarantine_id IN ({','.join('?' * len(ids))})"
        args += list(ids)
    sql += " ORDER BY source_file, source_line"
    if limit:
        sql += " LIMIT ?"
        args.append(int(limit))
    return conn.execute(sql, args).fetchall()


def replay(
    conn,
    error_code=None,
    source_run_id=None,
    source_file=None,
    ids=None,
    corrections_path=None,
    limit=None,
    dry_run=False,
    chunk_size=DEFAULT_SETTINGS.chunk_size,
    now=None,
    rules: Rules = DEFAULT_RULES,
) -> RunResult:
    now = now or utc_now()
    res = RunResult(new_run_id("replay", now), "replay", source_file)
    corrections = read_corrections(corrections_path) if corrections_path else {}
    pending = select_pending(conn, error_code, source_run_id, source_file, ids, limit)
    res.rows_read = len(pending)
    pending_ids = {p["quarantine_id"] for p in pending}
    for qid in corrections:
        if qid not in pending_ids:
            res.warnings.append(f"correction for {qid} ignored: not a selected PENDING quarantine row")

    customers = get_known_customers(conn)
    items, still_bad, applied = [], {}, {}
    for q in pending:
        raw = json.loads(q["raw_record"])
        base = {} if raw.get("_malformed") else dict(raw)
        fix = corrections.get(q["quarantine_id"], {})
        base.update(fix)
        applied[q["quarantine_id"]] = fix
        if raw.get("_malformed") and not fix:
            still_bad[q["quarantine_id"]] = [(MALFORMED_ROW, "malformed row: provide corrections for every field")]
            continue
        rec, errs = validate_record(base, customers, rules)
        if errs:
            still_bad[q["quarantine_id"]] = errs
        else:
            items.append(loader.Item(q["quarantine_id"], base, rec))

    if dry_run:
        res.status = "DRY_RUN"
        res.rows_valid, res.rows_quarantined = len(items), len(still_bad)
        log.info("replay DRY RUN: selected=%d would_load=%d would_remain=%d", len(pending), len(items), len(still_bad))
        return res  # nothing written, not even a run row

    start_run(conn, res.run_id, "replay", now, source_file)
    try:
        resolved = []
        for it, outcome in loader.load_orders(conn, items, res.run_id, "replay", iso(now), chunk_size):
            if outcome == loader.CONFLICT:
                still_bad[it.ref] = [conflict_error("an already-loaded version")]
            else:
                res.record_outcome(outcome)
                resolved.append(it.ref)
        for qid in resolved:
            conn.execute(
                "UPDATE quarantine SET status='RESOLVED', attempts=attempts+1, last_attempt_at=?,"
                " resolved_run_id=?, corrections=? WHERE quarantine_id=?",
                (iso(now), res.run_id, json.dumps(applied[qid]) if applied[qid] else None, qid),
            )
        for qid, errs in still_bad.items():
            conn.execute(
                "UPDATE quarantine SET attempts=attempts+1, last_attempt_at=?, last_error_codes=?, last_error_messages=?"
                " WHERE quarantine_id=?",
                (iso(now), json.dumps([e[0] for e in errs]), json.dumps([e[1] for e in errs]), qid),
            )
        res.rows_quarantined = len(still_bad)  # still pending after this attempt
        if res.rows_read != res.rows_valid + res.rows_quarantined:
            raise RuntimeError("count identity broken: selected != resolved + still_pending")
        conn.commit()
        res.status = "SUCCESS"
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        res.fail(exc)
    finish_run(conn, res, utc_now())
    return res
