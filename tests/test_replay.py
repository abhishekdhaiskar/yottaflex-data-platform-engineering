import json

from conftest import good, q
from qpipe import ingest, replay


def setup_quarantine(conn, write):
    p = write(
        [
            good("ORD-00000001"),  # ok
            good("ORD-00000002", cust="CUST-000009"),  # unknown customer (fixable by loading it)
            good("ORD-00000003", amount="12.5O"),  # needs correction
            good("ORD-00000004", status=""),
        ]
    )  # needs correction, stays unfixed
    ingest.ingest_file(conn, p)
    return p


def test_replay_after_reference_data_fix(conn, write, tmp_path):
    setup_quarantine(conn, write)
    conn.execute("INSERT INTO dim_customer VALUES ('CUST-000009','Z','IN','r','c')")
    conn.commit()
    before = q(conn, "SELECT order_id, run_id, loaded_at FROM fact_order WHERE order_id='ORD-00000001'")
    r = replay.replay(conn, error_code="UNKNOWN_CUSTOMER")
    assert (r.rows_read, r.rows_inserted, r.rows_quarantined) == (1, 1, 0)
    assert q(conn, "SELECT order_id FROM fact_order ORDER BY 1") == [("ORD-00000001",), ("ORD-00000002",)]
    assert (
        q(conn, "SELECT order_id, run_id, loaded_at FROM fact_order WHERE order_id='ORD-00000001'") == before
    )  # untouched


def test_replay_only_selects_pending_and_is_idempotent(conn, write):
    setup_quarantine(conn, write)
    conn.execute("INSERT INTO dim_customer VALUES ('CUST-000009','Z','IN','r','c')")
    conn.commit()
    replay.replay(conn, error_code="UNKNOWN_CUSTOMER")
    r2 = replay.replay(conn, error_code="UNKNOWN_CUSTOMER")
    assert r2.rows_read == 0 and q(conn, "SELECT COUNT(*) FROM fact_order") == [(2,)]


def test_corrections_applied_and_audited(conn, write, tmp_path):
    setup_quarantine(conn, write)
    qid = q(conn, "SELECT quarantine_id FROM quarantine WHERE error_codes LIKE '%INVALID_TYPE%'")[0][0]
    c = tmp_path / "fix.csv"
    c.write_text(f"quarantine_id,field,new_value\n{qid},amount,12.50\n")
    r = replay.replay(conn, corrections_path=c)
    assert r.rows_inserted == 1 and r.rows_quarantined == 2  # 2 others still bad
    assert q(conn, "SELECT amount_cents FROM fact_order WHERE order_id='ORD-00000003'") == [(1250,)]
    row = q(conn, "SELECT status, resolved_run_id, corrections, raw_record FROM quarantine WHERE quarantine_id=?", qid)[
        0
    ]
    assert row[0] == "RESOLVED" and row[1] == r.run_id and json.loads(row[2]) == {"amount": "12.50"}
    assert json.loads(row[3])["amount"] == "12.5O"  # raw payload never mutated


def test_failed_replay_keeps_original_reason_and_counts_attempts(conn, write):
    setup_quarantine(conn, write)
    replay.replay(conn, error_code="MISSING_REQUIRED")
    row = q(
        conn,
        "SELECT status, attempts, error_codes, last_error_codes FROM quarantine WHERE error_codes LIKE '%MISSING%'",
    )[0]
    assert row[0] == "PENDING" and row[1] == 1 and "MISSING_REQUIRED" in row[2] and "MISSING_REQUIRED" in row[3]


def test_dry_run_writes_nothing(conn, write):
    setup_quarantine(conn, write)
    n_runs = q(conn, "SELECT COUNT(*) FROM pipeline_run")
    r = replay.replay(conn, dry_run=True)
    assert r.status == "DRY_RUN" and q(conn, "SELECT COUNT(*) FROM pipeline_run") == n_runs
    assert q(conn, "SELECT SUM(attempts) FROM quarantine") == [(0,)]


def test_limit_and_filters(conn, write):
    setup_quarantine(conn, write)
    assert len(replay.select_pending(conn, limit=1)) == 1
    assert len(replay.select_pending(conn, error_code="INVALID_TYPE")) == 1
    assert len(replay.select_pending(conn, source_file="nope.csv")) == 0


def test_malformed_row_needs_full_corrections(conn, write, tmp_path):
    ingest.ingest_file(conn, write([good()[:3]]))
    qid = q(conn, "SELECT quarantine_id FROM quarantine")[0][0]
    assert replay.replay(conn).rows_quarantined == 1
    rows = "".join(
        f"{qid},{f},{v}\n"
        for f, v in zip(
            ["order_id", "customer_id", "order_ts", "amount", "currency", "status", "updated_at"], good(), strict=False
        )
    )
    c = tmp_path / "fix.csv"
    c.write_text("quarantine_id,field,new_value\n" + rows)
    assert replay.replay(conn, corrections_path=c).rows_inserted == 1


def test_replayed_older_version_is_late_not_overwrite(conn, write):
    ingest.ingest_file(
        conn, write([good(cust="CUST-000009", status="CREATED", upd="2026-03-02T10:00:00Z")])
    )  # quarantined
    ingest.ingest_file(conn, write([good(status="SHIPPED", upd="2026-03-05T10:00:00Z")]))  # newer loaded first
    conn.execute("INSERT INTO dim_customer VALUES ('CUST-000009','Z','IN','r','c')")
    conn.commit()
    # replay with customer corrected to an existing one keeps same order; older version => history only
    qid = q(conn, "SELECT quarantine_id FROM quarantine")[0][0]
    conn.commit()
    r = replay.replay(conn, ids=[qid])
    assert r.rows_late == 1 and q(conn, "SELECT status FROM fact_order") == [("SHIPPED",)]
