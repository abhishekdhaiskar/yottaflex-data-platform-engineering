"""Idempotent, version-aware publish into fact_order + fact_order_history.

Shared by `ingest` and `replay`, so both paths apply EXACTLY the same rules.

Rules (per valid record, keyed by order_id + source_updated_at):
  * version already in history, same hash      -> UNCHANGED (safe re-run, no-op)
  * version already in history, different hash -> CONFLICT   (caller quarantines it)
  * new version, order unseen                  -> INSERTED
  * new version, newer than current            -> UPDATED    (current row replaced, old kept in history)
  * new version, older than current            -> LATE       (history only; current NOT overwritten)
"""

from dataclasses import dataclass
from typing import Any

INSERTED, UPDATED, LATE, UNCHANGED, CONFLICT = "INSERTED", "UPDATED", "LATE", "UNCHANGED", "CONFLICT"


@dataclass
class Item:
    ref: Any  # source line number (ingest) or quarantine_id (replay)
    raw: dict
    rec: Any  # ValidRecord


def _chunks(seq, n):
    n = max(1, n)
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def _write_history(conn, rows):
    conn.executemany(
        "INSERT INTO fact_order_history (order_id, source_updated_at, customer_id, order_ts, amount_cents,"
        " currency, status, record_hash, run_id, source_file, loaded_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )


def _write_current(conn, rows):
    # The WHERE guard makes the upsert safe even if two writers race: older never beats newer.
    conn.executemany(
        "INSERT INTO fact_order (order_id, customer_id, order_ts, amount_cents, currency, status,"
        " source_updated_at, record_hash, run_id, source_file, loaded_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)"
        " ON CONFLICT(order_id) DO UPDATE SET customer_id=excluded.customer_id, order_ts=excluded.order_ts,"
        " amount_cents=excluded.amount_cents, currency=excluded.currency, status=excluded.status,"
        " source_updated_at=excluded.source_updated_at, record_hash=excluded.record_hash,"
        " run_id=excluded.run_id, source_file=excluded.source_file, loaded_at=excluded.loaded_at"
        " WHERE excluded.source_updated_at > fact_order.source_updated_at",
        rows,
    )


def load_orders(conn, items, run_id, source_file, loaded_at, chunk_size=5000):
    """Returns list of (Item, outcome). Does NOT commit - caller owns the transaction."""
    items = sorted(items, key=lambda it: (it.rec.order_id, it.rec.updated_at))
    ids = sorted({it.rec.order_id for it in items})

    # Prefetch existing state in bulk (1 query per 500 ids instead of 1 query per row)
    cur_ver, hist = {}, {}
    for part in _chunks(ids, 500):
        marks = ",".join("?" * len(part))
        for r in conn.execute(f"SELECT order_id, source_updated_at FROM fact_order WHERE order_id IN ({marks})", part):
            cur_ver[r[0]] = r[1]
        for r in conn.execute(
            f"SELECT order_id, source_updated_at, record_hash FROM fact_order_history WHERE order_id IN ({marks})", part
        ):
            hist[(r[0], r[1])] = r[2]

    results, hist_rows, cur_rows = [], [], {}
    for it in items:
        r = it.rec
        key = (r.order_id, r.updated_at)
        if key in hist:
            results.append((it, UNCHANGED if hist[key] == r.record_hash else CONFLICT))
            continue
        hist[key] = r.record_hash
        row = (
            r.order_id,
            r.customer_id,
            r.order_ts,
            r.amount_cents,
            r.currency,
            r.status,
            r.updated_at,
            r.record_hash,
            run_id,
            source_file,
            loaded_at,
        )
        hist_rows.append(
            (
                r.order_id,
                r.updated_at,
                r.customer_id,
                r.order_ts,
                r.amount_cents,
                r.currency,
                r.status,
                r.record_hash,
                run_id,
                source_file,
                loaded_at,
            )
        )
        cv = cur_ver.get(r.order_id)
        if cv is None:
            outcome = INSERTED
        elif r.updated_at > cv:
            outcome = UPDATED
        else:
            outcome = LATE
        if outcome in (INSERTED, UPDATED):
            cur_ver[r.order_id] = r.updated_at
            cur_rows[r.order_id] = row  # sorted ascending => last write is newest
        results.append((it, outcome))

    for part in _chunks(hist_rows, chunk_size):
        _write_history(conn, part)
    for part in _chunks(list(cur_rows.values()), chunk_size):
        _write_current(conn, part)
    return results
