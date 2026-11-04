"""Reference data (dim_customer). Strict: the file is small and trusted, so any bad row fails the load."""

import csv
import os

from .db import utc_now
from .ids import file_sha256, new_run_id
from .runs import RunResult, finish_run, start_run

UPSERT_CUSTOMER = (
    "INSERT INTO dim_customer (customer_id, customer_name, country_code, run_id, source_file) VALUES (?,?,?,?,?)"
    " ON CONFLICT(customer_id) DO UPDATE SET customer_name=excluded.customer_name,"
    " country_code=excluded.country_code, run_id=excluded.run_id, source_file=excluded.source_file"
)


def _parse_customers(path, run_id, source_file):
    out, seen = [], set()
    with open(path, newline="", encoding="utf-8-sig") as f:
        for line, r in enumerate(csv.DictReader(f), start=2):
            cid = (r.get("customer_id") or "").strip()
            name = (r.get("customer_name") or "").strip()
            country = (r.get("country_code") or "").strip().upper()
            if not cid or not name or len(country) != 2:
                raise ValueError(f"line {line}: invalid customer row {dict(r)}")
            if cid in seen:
                raise ValueError(f"line {line}: duplicate customer_id {cid}")
            seen.add(cid)
            out.append((cid, name, country, run_id, source_file))
    return out


def load_customers(conn, path, now=None) -> RunResult:
    now = now or utc_now()
    source_file = os.path.basename(str(path))
    res = RunResult(new_run_id("customers", now), "customers", source_file)
    start_run(conn, res.run_id, "customers", now, source_file, file_sha256(path))
    try:
        rows = _parse_customers(path, res.run_id, source_file)
        conn.executemany(UPSERT_CUSTOMER, rows)
        conn.commit()
        res.rows_read = res.rows_valid = res.rows_inserted = len(rows)
        res.status = "SUCCESS"
    except Exception as exc:  # noqa: BLE001 - recorded, reported via status + exit code
        conn.rollback()
        res.fail(exc)
    finish_run(conn, res, utc_now())
    return res
