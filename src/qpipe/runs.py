"""Run tracking: result object + pipeline_run persistence (observability)."""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime

from .db import iso

log = logging.getLogger("qpipe")

COUNTERS = [
    "rows_read",
    "rows_valid",
    "rows_inserted",
    "rows_updated",
    "rows_late",
    "rows_unchanged",
    "rows_dup_dropped",
    "rows_quarantined",
]
OUTCOME_FIELD = {
    "INSERTED": "rows_inserted",
    "UPDATED": "rows_updated",
    "LATE": "rows_late",
    "UNCHANGED": "rows_unchanged",
}


@dataclass
class RunResult:
    run_id: str
    run_type: str  # ingest | replay | customers
    source_file: str | None = None
    status: str = "RUNNING"  # RUNNING | SUCCESS | FAILED | SKIPPED | DRY_RUN
    rows_read: int = 0
    rows_valid: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    rows_late: int = 0
    rows_unchanged: int = 0
    rows_dup_dropped: int = 0
    rows_quarantined: int = 0
    error_message: str | None = None
    warnings: list = field(default_factory=list)

    def record_outcome(self, outcome: str) -> None:
        """Count one accepted record (INSERTED / UPDATED / LATE / UNCHANGED)."""
        self.rows_valid += 1
        name = OUTCOME_FIELD[outcome]
        setattr(self, name, getattr(self, name) + 1)

    def reset_counters(self) -> None:
        """Used on failure: nothing was committed, so report zeros."""
        for c in COUNTERS:
            setattr(self, c, 0)

    def fail(self, exc: Exception) -> None:
        self.status = "FAILED"
        self.error_message = f"{type(exc).__name__}: {exc}"
        self.reset_counters()

    def asdict(self) -> dict:
        return asdict(self)


def start_run(conn, run_id: str, run_type: str, now: datetime, source_file=None, sha=None) -> None:
    conn.execute(
        "INSERT INTO pipeline_run (run_id, run_type, source_file, file_sha256, status, started_at)"
        " VALUES (?,?,?,?, 'RUNNING', ?)",
        (run_id, run_type, source_file, sha, iso(now)),
    )
    conn.commit()


def finish_run(conn, res: RunResult, now: datetime) -> None:
    sets = ", ".join(f"{c}=?" for c in COUNTERS)
    conn.execute(
        f"UPDATE pipeline_run SET status=?, ended_at=?, error_message=?, warnings=?, {sets} WHERE run_id=?",
        [res.status, iso(now), res.error_message, json.dumps(res.warnings)]
        + [getattr(res, c) for c in COUNTERS]
        + [res.run_id],
    )
    conn.commit()
    log.info(
        "run_id=%s type=%s status=%s read=%d valid=%d ins=%d upd=%d late=%d unchanged=%d dup=%d quarantined=%d%s",
        res.run_id,
        res.run_type,
        res.status,
        res.rows_read,
        res.rows_valid,
        res.rows_inserted,
        res.rows_updated,
        res.rows_late,
        res.rows_unchanged,
        res.rows_dup_dropped,
        res.rows_quarantined,
        f" error={res.error_message}" if res.error_message else "",
    )
