import json

from conftest import HEADER, good, q
from qpipe import ingest, loader


def run(conn, p, **kw):
    return ingest.ingest_file(conn, p, **kw)


def test_happy_path(conn, write):
    r = run(conn, write([good("ORD-00000001"), good("ORD-00000002", cust="CUST-000002")]))
    assert (r.status, r.rows_read, r.rows_valid, r.rows_inserted, r.rows_quarantined) == ("SUCCESS", 2, 2, 2, 0)
    assert q(conn, "SELECT COUNT(*) FROM fact_order") == [(2,)]
    assert q(conn, "SELECT amount_cents FROM fact_order WHERE order_id='ORD-00000001'") == [(1000,)]


def test_empty_batch_header_only(conn, write):
    r = run(conn, write([]))
    assert r.status == "SUCCESS" and r.rows_read == 0


def test_zero_byte_file_fails(conn, write):
    r = run(conn, write([], header=None))
    assert r.status == "FAILED" and "empty file" in r.error_message


def test_schema_change_missing_column_fails_cleanly(conn, write):
    h = [c if c != "amount" else "total_amount" for c in HEADER]
    r = run(conn, write([good()], header=h))
    assert r.status == "FAILED" and "amount" in r.error_message
    assert q(conn, "SELECT COUNT(*) FROM fact_order") == [(0,)]
    assert q(conn, "SELECT status FROM pipeline_run WHERE run_id=?", r.run_id) == [("FAILED",)]


def test_extra_column_is_warning_not_failure(conn, write):
    r = run(conn, write([good() + ["x"]], header=HEADER + ["channel"]))
    assert r.status == "SUCCESS" and r.rows_inserted == 1 and "channel" in r.warnings[0]


def test_malformed_row_quarantined_with_context(conn, write):
    p = write([good(), good("ORD-00000002")[:4]])
    r = run(conn, p)
    assert r.rows_inserted == 1 and r.rows_quarantined == 1
    row = q(conn, "SELECT source_file, source_line, error_codes, raw_record FROM quarantine")[0]
    assert row[0] == p.name and row[1] == 3 and json.loads(row[2]) == ["MALFORMED_ROW"]
    assert json.loads(row[3])["_malformed"] is True


def test_nulls_and_invalid_reference_quarantined(conn, write):
    r = run(conn, write([good("ORD-00000001", status=""), good("ORD-00000002", cust="CUST-777777")]))
    assert r.rows_quarantined == 2 and r.rows_inserted == 0
    codes = {json.loads(x[0])[0] for x in q(conn, "SELECT error_codes FROM quarantine")}
    assert codes == {"MISSING_REQUIRED", "UNKNOWN_CUSTOMER"}


def test_exact_duplicate_dropped_and_counted(conn, write):
    r = run(conn, write([good(), good()]))
    assert (r.rows_read, r.rows_inserted, r.rows_dup_dropped, r.rows_quarantined) == (2, 1, 1, 0)


def test_conflicting_duplicate_quarantined(conn, write):
    r = run(conn, write([good(amount="10.00"), good(amount="99.00")]))
    assert r.rows_inserted == 1 and r.rows_quarantined == 1
    assert q(conn, "SELECT amount_cents FROM fact_order") == [(1000,)]  # first wins
    assert "DUPLICATE_CONFLICT" in q(conn, "SELECT error_codes FROM quarantine")[0][0]


def test_conflict_against_already_loaded_version(conn, write):
    run(conn, write([good(amount="10.00")]))
    r = run(conn, write([good(amount="55.00")]))
    assert r.rows_quarantined == 1 and q(conn, "SELECT amount_cents FROM fact_order") == [(1000,)]


def test_rerun_same_file_is_skipped(conn, write):
    p = write([good()])
    run(conn, p)
    r = run(conn, p)
    assert r.status == "SKIPPED"
    assert q(conn, "SELECT COUNT(*) FROM fact_order_history") == [(1,)]


def test_forced_rerun_creates_no_duplicates(conn, write):
    p = write([good(), good("ORD-00000002", status="")])
    run(conn, p)
    r = run(conn, p, force=True)
    assert r.status == "SUCCESS" and r.rows_unchanged == 1 and r.rows_inserted == 0
    assert q(conn, "SELECT COUNT(*) FROM fact_order") == [(1,)]
    assert q(conn, "SELECT COUNT(*) FROM fact_order_history") == [(1,)]
    assert q(conn, "SELECT COUNT(*) FROM quarantine") == [(1,)]  # reject row not duplicated


def test_update_keeps_history(conn, write):
    run(conn, write([good(status="CREATED", upd="2026-03-02T10:00:00Z")]))
    r = run(conn, write([good(status="SHIPPED", upd="2026-03-05T10:00:00Z")]))
    assert r.rows_updated == 1
    assert q(conn, "SELECT status FROM fact_order") == [("SHIPPED",)]
    assert q(conn, "SELECT status FROM fact_order_history ORDER BY source_updated_at") == [("CREATED",), ("SHIPPED",)]


def test_late_arriving_older_version_does_not_overwrite(conn, write):
    run(conn, write([good(status="SHIPPED", upd="2026-03-05T10:00:00Z")]))
    r = run(conn, write([good(status="CREATED", upd="2026-03-02T10:00:00Z")]))
    assert r.rows_late == 1 and r.rows_updated == 0
    assert q(conn, "SELECT status FROM fact_order") == [("SHIPPED",)]
    assert q(conn, "SELECT COUNT(*) FROM fact_order_history") == [(2,)]  # still preserved


def test_out_of_order_inside_one_file(conn, write):
    r = run(
        conn,
        write([good(status="SHIPPED", upd="2026-03-05T10:00:00Z"), good(status="CREATED", upd="2026-03-02T10:00:00Z")]),
    )
    assert q(conn, "SELECT status FROM fact_order") == [("SHIPPED",)]
    assert r.rows_inserted == 1 and r.rows_updated == 1  # processed in version order


def test_partial_failure_rolls_back_and_retry_works(conn, write, monkeypatch):
    p = write([good("ORD-00000001"), good("ORD-00000002"), good("ORD-00000003", status="")])
    real = loader._write_current

    def boom(*a, **k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(loader, "_write_current", boom)
    r = run(conn, p)
    assert r.status == "FAILED" and "disk full" in r.error_message
    for t in ("fact_order", "fact_order_history", "quarantine"):
        assert q(conn, f"SELECT COUNT(*) FROM {t}") == [(0,)]  # nothing half-written
    monkeypatch.setattr(loader, "_write_current", real)
    r2 = run(conn, p)  # FAILED runs don't block a retry
    assert r2.status == "SUCCESS" and r2.rows_inserted == 2 and r2.rows_quarantined == 1


def test_chunking_gives_same_result(conn, write):
    rows = [good(f"ORD-{i:08d}") for i in range(1, 51)]
    r = run(conn, write(rows), chunk_size=7)
    assert r.rows_inserted == 50


def test_count_identity_always_holds(conn, write):
    rows = [good("ORD-00000001"), good("ORD-00000001"), good("ORD-00000002", amount="x"), good("ORD-00000003")[:3]]
    r = run(conn, write(rows))
    assert r.rows_read == r.rows_valid + r.rows_dup_dropped + r.rows_quarantined
