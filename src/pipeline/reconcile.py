"""Reconciliation / validation report. Every check returns (name, passed, detail)."""

from .db import iso, utc_now


def _one(conn, sql, *a):
    return conn.execute(sql, a).fetchone()[0]


def run_checks(conn):
    checks = []

    def add(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    # 1. Per-run source -> target reconciliation
    bad = []
    for r in conn.execute("SELECT * FROM pipeline_run WHERE status='SUCCESS' AND run_type IN ('ingest','replay')"):
        loaded = _one(conn, "SELECT COUNT(*) FROM fact_order_history WHERE run_id=?", r["run_id"])
        if (
            r["run_type"] == "ingest"
            and r["rows_read"] != r["rows_valid"] + r["rows_dup_dropped"] + r["rows_quarantined"]
        ):
            bad.append(f"{r['run_id']}: read != valid+dup+quarantined")
        if r["run_type"] == "replay" and r["rows_read"] != r["rows_valid"] + r["rows_quarantined"]:
            bad.append(f"{r['run_id']}: selected != resolved+still_pending")
        if r["rows_valid"] != r["rows_inserted"] + r["rows_updated"] + r["rows_late"] + r["rows_unchanged"]:
            bad.append(f"{r['run_id']}: valid != ins+upd+late+unchanged")
        if loaded != r["rows_inserted"] + r["rows_updated"] + r["rows_late"]:
            bad.append(f"{r['run_id']}: history rows {loaded} != ins+upd+late")
    add(
        "run counts reconcile (read = valid + dup_dropped + quarantined; history rows = inserted+updated+late)",
        not bad,
        "; ".join(bad) or "all successful runs balance",
    )

    # 2. Keys / integrity
    n_cur = _one(conn, "SELECT COUNT(*) FROM fact_order")
    n_ids = _one(conn, "SELECT COUNT(DISTINCT order_id) FROM fact_order_history")
    add(
        "every order in history has exactly one current row",
        n_cur == n_ids,
        f"fact_order={n_cur}, distinct history ids={n_ids}",
    )
    orphans = _one(
        conn,
        "SELECT COUNT(*) FROM fact_order f LEFT JOIN dim_customer c USING(customer_id) WHERE c.customer_id IS NULL",
    )
    add("referential integrity: no fact_order without dim_customer", orphans == 0, f"orphans={orphans}")
    stale = _one(
        conn,
        "SELECT COUNT(*) FROM fact_order f WHERE f.source_updated_at <> "
        "(SELECT MAX(h.source_updated_at) FROM fact_order_history h WHERE h.order_id=f.order_id)",
    )
    add("current row is always the latest version in history", stale == 0, f"stale current rows={stale}")
    drift = _one(
        conn,
        "SELECT COUNT(*) FROM fact_order f JOIN fact_order_history h ON h.order_id=f.order_id "
        "AND h.source_updated_at=f.source_updated_at WHERE h.record_hash <> f.record_hash",
    )
    add("current row content equals its history version (hash)", drift == 0, f"mismatches={drift}")

    # 3. Quarantine traceability
    untraceable = _one(
        conn,
        "SELECT COUNT(*) FROM quarantine WHERE source_file='' OR source_line<=0 OR error_codes='[]' OR raw_record=''",
    )
    add(
        "every quarantine row has source file, line, raw record and error reason",
        untraceable == 0,
        f"untraceable={untraceable}",
    )
    resolved_without = _one(conn, "SELECT COUNT(*) FROM quarantine WHERE status='RESOLVED' AND resolved_run_id IS NULL")
    add("every RESOLVED quarantine row points to its replay run", resolved_without == 0, f"missing={resolved_without}")
    return checks


def build_report(conn) -> str:
    checks = run_checks(conn)
    L = [
        "# Reconciliation report",
        f"_Generated {iso(utc_now())}_",
        "",
        "## Checks",
        "",
        "| Result | Check | Detail |",
        "|---|---|---|",
    ]
    for name, ok, detail in checks:
        L.append(f"| {'PASS' if ok else '**FAIL**'} | {name} | {detail} |")

    L += [
        "",
        "## Runs",
        "",
        "| run_id | type | file | status | read | valid | ins | upd | late | unchanged | dup | quarantined |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in conn.execute("SELECT * FROM pipeline_run ORDER BY started_at, run_id"):
        L.append(
            f"| {r['run_id']} | {r['run_type']} | {r['source_file'] or ''} | {r['status']} | {r['rows_read']} | "
            f"{r['rows_valid']} | {r['rows_inserted']} | {r['rows_updated']} | {r['rows_late']} | "
            f"{r['rows_unchanged']} | {r['rows_dup_dropped']} | {r['rows_quarantined']} |"
        )

    L += ["", "## Target summary", ""]
    L.append(f"- fact_order rows: {_one(conn, 'SELECT COUNT(*) FROM fact_order')}")
    L.append(f"- fact_order_history rows: {_one(conn, 'SELECT COUNT(*) FROM fact_order_history')}")
    L += ["", "| status | orders | total_amount (major units, all currencies) |", "|---|---|---|"]
    for r in conn.execute(
        "SELECT status, COUNT(*) n, SUM(amount_cents) s FROM fact_order GROUP BY status ORDER BY status"
    ):
        L.append(f"| {r['status']} | {r['n']} | {r['s'] / 100:.2f} |")

    L += ["", "## Quarantine by error code and status", "", "| error_code | status | rows |", "|---|---|---|"]
    for r in conn.execute(
        "SELECT j.value code, q.status, COUNT(*) n FROM quarantine q, json_each(q.error_codes) j "
        "GROUP BY j.value, q.status ORDER BY j.value, q.status"
    ):
        L.append(f"| {r['code']} | {r['status']} | {r['n']} |")
    return "\n".join(L) + "\n"
