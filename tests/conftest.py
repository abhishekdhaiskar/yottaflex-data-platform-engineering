import csv

import pytest

from qpipe import db

HEADER = ["order_id", "customer_id", "order_ts", "amount", "currency", "status", "updated_at"]


def good(
    oid="ORD-00000001",
    cust="CUST-000001",
    ots="2026-03-01T10:00:00Z",
    amount="10.00",
    cur="USD",
    status="PAID",
    upd="2026-03-02T10:00:00Z",
):
    return [oid, cust, ots, amount, cur, status, upd]


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    c.executemany(
        "INSERT INTO dim_customer VALUES (?,?,?,?,?)",
        [("CUST-000001", "A", "IN", "r0", "c.csv"), ("CUST-000002", "B", "US", "r0", "c.csv")],
    )
    c.commit()
    return c


@pytest.fixture
def write(tmp_path):
    counter = [0]

    def _write(rows, header=HEADER, name=None):
        counter[0] += 1
        p = tmp_path / (name or f"orders_{counter[0]}.csv")
        with open(p, "w", newline="") as f:
            w = csv.writer(f)
            if header is not None:
                w.writerow(header)
            w.writerows(rows)
        return p

    return _write


def q(conn, sql, *a):
    return [tuple(r) for r in conn.execute(sql, a).fetchall()]
