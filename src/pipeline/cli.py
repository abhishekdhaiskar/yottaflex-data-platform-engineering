"""Command line interface:  python -m qpipe <command> ..."""

import argparse
import json
import logging
import sys
from pathlib import Path

from . import db, generator, ingest, labels, reconcile, reference, replay
from .config import ConfigError, load_settings


def _setup_logging(log_file):
    handlers = [logging.StreamHandler(sys.stderr)]
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    logging.basicConfig(
        level=logging.INFO, handlers=handlers, force=True, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="qpipe", description=__doc__)
    p.add_argument("--config", help="TOML config (default: config/pipeline.toml if it exists)")
    p.add_argument("--db", help="SQLite file (overrides config db_path)")
    p.add_argument("--log-file", help="log file (overrides config log_file)")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="create synthetic input files + separate labels")
    g.add_argument("--orders", type=int, default=200)
    g.add_argument("--seed", type=int, default=42)
    g.add_argument("--out", default="data/sample")
    g.add_argument("--labels-dir", default="data/labels")

    c = sub.add_parser("load-customers", help="load reference data (dim_customer)")
    c.add_argument("--file", required=True)

    i = sub.add_parser("ingest", help="ingest an orders CSV")
    i.add_argument("--file", required=True)
    i.add_argument("--force", action="store_true", help="re-run a file that already succeeded")
    i.add_argument("--chunk-size", type=int, help="rows per batch (overrides config)")

    r = sub.add_parser("replay", help="replay PENDING quarantine rows after a fix")
    r.add_argument("--error-code")
    r.add_argument("--source-run-id")
    r.add_argument("--source-file")
    r.add_argument("--id", action="append", dest="ids", help="quarantine_id (repeatable)")
    r.add_argument("--corrections", help="CSV: quarantine_id,field,new_value")
    r.add_argument("--limit", type=int)
    r.add_argument("--dry-run", action="store_true")

    q = sub.add_parser("reconcile", help="run checks and write a markdown report")
    q.add_argument("--out", default="reports/reconciliation.md")

    v = sub.add_parser("verify-labels", help="compare outcome with expected-answer labels")
    v.add_argument("labels", nargs="+")

    sub.add_parser("runs", help="list pipeline runs")

    a = p.parse_args(argv)
    try:
        cfg = load_settings(a.config)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
    _setup_logging(a.log_file or cfg.log_file)

    if a.cmd == "generate":
        print(json.dumps(generator.generate(a.out, a.labels_dir, a.orders, a.seed)))
        return 0

    conn = db.connect(a.db or cfg.db_path)
    if a.cmd == "load-customers":
        res = reference.load_customers(conn, a.file)
    elif a.cmd == "ingest":
        res = ingest.ingest_file(
            conn, a.file, force=a.force, chunk_size=a.chunk_size or cfg.chunk_size, rules=cfg.rules
        )
    elif a.cmd == "replay":
        res = replay.replay(
            conn,
            a.error_code,
            a.source_run_id,
            a.source_file,
            a.ids,
            a.corrections,
            a.limit,
            a.dry_run,
            chunk_size=cfg.chunk_size,
            rules=cfg.rules,
        )
    elif a.cmd == "reconcile":
        report = reconcile.build_report(conn)
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(report)
        print(report)
        return 0 if all(ok for _, ok, _ in reconcile.run_checks(conn)) else 1
    elif a.cmd == "verify-labels":
        mism = labels.verify_labels(conn, a.labels)
        print(
            "label check:",
            "OK - pipeline behaviour matches all expected labels" if not mism else f"{len(mism)} MISMATCHES",
        )
        for m in mism[:20]:
            print(" ", m)
        return 1 if mism else 0
    elif a.cmd == "runs":
        for r in conn.execute(
            "SELECT run_id, run_type, source_file, status, rows_read, rows_quarantined, error_message"
            " FROM pipeline_run ORDER BY started_at"
        ):
            print(" | ".join(str(x) for x in tuple(r)))
        return 0

    print(json.dumps(res.asdict(), indent=2))
    return 1 if res.status == "FAILED" else 0


if __name__ == "__main__":
    sys.exit(main())
