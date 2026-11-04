import csv
import hashlib
from pathlib import Path

from qpipe import db, generator, ingest, labels, reconcile, reference, replay


def _digest(d):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(d).glob("*.csv"))}


def test_generator_is_deterministic(tmp_path):
    generator.generate(tmp_path / "a", tmp_path / "la", 300, seed=7)
    generator.generate(tmp_path / "b", tmp_path / "lb", 300, seed=7)
    assert _digest(tmp_path / "a") == _digest(tmp_path / "b")
    generator.generate(tmp_path / "c", tmp_path / "lc", 300, seed=8)
    assert _digest(tmp_path / "a") != _digest(tmp_path / "c")


def test_full_pipeline_matches_labels_and_reconciles(tmp_path):
    d, lab = tmp_path / "in", tmp_path / "labels"
    generator.generate(d, lab, 1000, seed=42)
    conn = db.connect(tmp_path / "w.db")
    assert reference.load_customers(conn, d / "customers.csv").status == "SUCCESS"
    r1 = ingest.ingest_file(conn, d / "orders_batch_01.csv")
    r2 = ingest.ingest_file(conn, d / "orders_batch_02.csv")
    label_files = [lab / "labels_batch_01.csv", lab / "labels_batch_02.csv"]
    assert labels.verify_labels(conn, label_files) == []

    # label totals agree with metrics
    def count(f, v):
        with open(f, newline="") as fh:
            return sum(1 for r in csv.DictReader(fh) if r["expected"] == v)

    assert r1.rows_dup_dropped == count(label_files[0], "DUP_DROPPED")
    assert r2.rows_late == count(label_files[1], "VALID_LATE")

    reference.load_customers(conn, d / "customers_late.csv")
    replay.replay(conn, error_code="UNKNOWN_CUSTOMER")
    replay.replay(conn, corrections_path=d / "corrections.csv")
    assert all(ok for _, ok, _ in reconcile.run_checks(conn)), reconcile.run_checks(conn)

    # whole pipeline replayed again => nothing changes (idempotent)
    snap = [tuple(r) for r in conn.execute("SELECT * FROM fact_order ORDER BY order_id")]
    assert ingest.ingest_file(conn, d / "orders_batch_01.csv").status == "SKIPPED"
    assert ingest.ingest_file(conn, d / "orders_batch_02.csv", force=True).rows_inserted == 0
    assert [tuple(r) for r in conn.execute("SELECT * FROM fact_order ORDER BY order_id")] == snap


def test_reconciliation_detects_corruption(tmp_path):
    d = tmp_path / "in"
    generator.generate(d, tmp_path / "l", 100, seed=1)
    conn = db.connect(tmp_path / "w.db")
    reference.load_customers(conn, d / "customers.csv")
    ingest.ingest_file(conn, d / "orders_batch_01.csv")
    assert all(ok for _, ok, _ in reconcile.run_checks(conn))
    conn.execute("DELETE FROM fact_order_history WHERE rowid IN (SELECT rowid FROM fact_order_history LIMIT 1)")
    conn.commit()
    assert not all(ok for _, ok, _ in reconcile.run_checks(conn))


def test_reconcile_report_renders(tmp_path):
    conn = db.connect(tmp_path / "w.db")
    assert "# Reconciliation report" in reconcile.build_report(conn)
