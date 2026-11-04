"""Compare pipeline behaviour with the SEPARATE expected-answer labels produced by the generator.

Label values: VALID | VALID_LATE | DUP_DROPPED | <error code>.
Rows labelled with an error code must be in quarantine with that code; every other label must NOT be quarantined.
"""

import csv
import json

from .validation import ERROR_CODES


def verify_labels(conn, label_files) -> list:
    """Returns a list of human-readable mismatches (empty list = pipeline matches all labels)."""
    mismatches = []
    for label_file in label_files:
        with open(label_file, newline="") as f:
            for r in csv.DictReader(f):
                where = f"{r['source_file']}:{r['line_no']}"
                row = conn.execute(
                    "SELECT error_codes FROM quarantine WHERE source_file=? AND source_line=?",
                    (r["source_file"], int(r["line_no"])),
                ).fetchone()
                codes = json.loads(row[0]) if row else []
                if r["expected"] in ERROR_CODES:
                    if r["expected"] not in codes:
                        mismatches.append(f"{where} expected {r['expected']}, got {codes or 'accepted'}")
                elif codes:
                    mismatches.append(f"{where} expected {r['expected']}, got quarantined {codes}")
    return mismatches
