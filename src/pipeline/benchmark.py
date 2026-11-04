"""Simple performance measurement + one optimisation comparison.

  python -m qpipe.benchmark --orders 100000

1. Optimised pipeline (bulk prefetch of existing versions + set lookup for customers +
   executemany + ONE transaction) on N orders  -> rows/sec per stage.
2. Baseline on a smaller N: per-row SELECTs and a commit per row (the naive approach).
"""

import argparse
import tempfile
import time
from pathlib import Path

from . import db, generator, ingest, reference, validation


def naive_ingest(conn, path, limit):
    """Deliberately naive: customer lookup via SQL per row, per-row insert, commit per row."""
    header, _, rows = ingest.read_orders(path)
    n = 0
    for _line, fields in rows[:limit]:
        raw = dict(zip(header, fields, strict=False))
        known = {
            c[0]
            for c in conn.execute("SELECT customer_id FROM dim_customer WHERE customer_id=?", (raw.get("customer_id"),))
        }
        rec, errs = validation.validate_record(raw, known)
        if errs:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO fact_order VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                rec.order_id,
                rec.customer_id,
                rec.order_ts,
                rec.amount_cents,
                rec.currency,
                rec.status,
                rec.updated_at,
                rec.record_hash,
                "naive",
                path.name,
                "now",
            ),
        )
        conn.commit()
        n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orders", type=int, default=100_000)
    ap.add_argument("--baseline-rows", type=int, default=3000)
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        t = time.perf_counter()
        generator.generate(tmp / "in", tmp / "labels", a.orders, seed=42)
        print(f"generate {a.orders:,} orders: {time.perf_counter() - t:.2f}s")

        conn = db.connect(tmp / "opt.db")
        reference.load_customers(conn, tmp / "in" / "customers.csv")
        f = tmp / "in" / "orders_batch_01.csv"
        t = time.perf_counter()
        r = ingest.ingest_file(conn, f)
        dt = time.perf_counter() - t
        print(
            f"OPTIMISED ingest: {r.rows_read:,} rows in {dt:.2f}s = {r.rows_read / dt:,.0f} rows/s "
            f"(valid={r.rows_valid:,} quarantined={r.rows_quarantined:,} dup_dropped={r.rows_dup_dropped:,})"
        )

        t = time.perf_counter()
        r2 = ingest.ingest_file(conn, tmp / "in" / "orders_batch_02.csv")
        dt2 = time.perf_counter() - t
        print(
            f"OPTIMISED batch_02 (updates/late): {r2.rows_read:,} rows in {dt2:.2f}s = {r2.rows_read / dt2:,.0f} rows/s"
        )

        conn2 = db.connect(tmp / "naive.db")
        reference.load_customers(conn2, tmp / "in" / "customers.csv")
        t = time.perf_counter()
        n = naive_ingest(conn2, f, a.baseline_rows)
        dtn = time.perf_counter() - t
        print(f"NAIVE baseline: {n:,} rows in {dtn:.2f}s = {n / dtn:,.0f} rows/s (per-row SELECT + commit per row)")
        print(f"speed-up optimised vs naive: ~{(r.rows_read / dt) / (n / dtn):.0f}x")


if __name__ == "__main__":
    main()
