"""Seeded synthetic data generator. Writes inputs to `out_dir` and expected-answer labels to a
SEPARATE `labels_dir` (labels are never part of the pipeline input).

Batch 1: base orders + labelled defects (dups, missing, bad types, unknown customers, malformed...)
Batch 2: updates, late-arriving older versions, new orders, re-sent rows (idempotency).
"""

import csv
import hashlib
import random
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from .config import DEFAULT_RULES
from .ids import make_quarantine_id

HEADER = ["order_id", "customer_id", "order_ts", "amount", "currency", "status", "updated_at"]
UTC = UTC
IST = timezone(timedelta(hours=5, minutes=30))
CURRENCIES = sorted(DEFAULT_RULES.currencies)  # sorted => deterministic with a fixed seed
OPEN_STATUSES = ["CREATED", "PAID", "SHIPPED"]  # all must be in DEFAULT_RULES.statuses
FINAL_STATUS = "DELIVERED"
BASE_DATE = datetime(2026, 1, 1, tzinfo=UTC)
SPAN_DAYS = 270
# share of base orders affected by each scenario
DEFECT_RATE, UPDATE_RATE, LATE_RATE, NEW_RATE, RESEND_RATE = 0.01, 0.10, 0.03, 0.02, 0.01


def _fmt(dt, ist=False):
    return dt.astimezone(IST).isoformat(timespec="seconds") if ist else dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Spec:
    def __init__(self, fields, expected="VALID", group=None, fix=None, later="VALID"):
        # group: specs sharing a key; first in FILE ORDER is VALID, later ones get `later`
        self.fields, self.expected, self.group, self.fix, self.later = fields, expected, group, fix or {}, later


def generate(out_dir, labels_dir, n_orders=200, seed=42):
    rng = random.Random(seed)
    out, lab = Path(out_dir), Path(labels_dir)
    out.mkdir(parents=True, exist_ok=True)
    lab.mkdir(parents=True, exist_ok=True)

    n_cust = max(20, n_orders // 10)
    customers = [(f"CUST-{i:06d}", f"Customer {i}", rng.choice(["IN", "US", "GB", "DE"])) for i in range(1, n_cust + 1)]
    late_customers = [(f"CUST-{900000 + i}", f"Late Customer {i}", "IN") for i in range(1, 4)]
    for name, rows in (("customers.csv", customers), ("customers_late.csv", late_customers)):
        with open(out / name, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["customer_id", "customer_name", "country_code"])
            w.writerows(rows)

    base_time = BASE_DATE
    counter = [0]

    def new_order(customer=None):
        counter[0] += 1
        oid = f"ORD-{counter[0]:08d}"
        ots = base_time + timedelta(seconds=rng.randint(0, SPAN_DAYS * 86400))
        upd = ots + timedelta(seconds=rng.randint(2 * 3600, 3 * 86400))  # >= 2h so a "late" version fits before it
        return {
            "oid": oid,
            "cust": customer or rng.choice(customers)[0],
            "ots": ots,
            "upd": upd,
            "cents": rng.randint(100, 500000),
            "cur": rng.choice(CURRENCIES),
            "status": rng.choice(OPEN_STATUSES),
            "ist": rng.random() < 0.05,
        }

    def row(o, **ov):
        d = {**o, **ov}
        return [
            d["oid"],
            d["cust"],
            _fmt(d["ots"], d["ist"]),
            f"{d['cents'] / 100:.2f}",
            d["cur"],
            d["status"],
            _fmt(d["upd"], d["ist"]),
        ]

    k = max(1, int(n_orders * DEFECT_RATE))
    base = [new_order() for _ in range(n_orders)]
    specs = [Spec(row(o)) for o in base]

    # ---- labelled duplicates (first copy in file is VALID, later copy gets the label) ----
    picks = rng.sample(range(n_orders), 2 * k)
    for gi, idx in enumerate(picks[:k]):
        specs[idx].group, specs[idx].later = f"dupx{gi}", "DUP_DROPPED"
        specs.append(Spec(list(specs[idx].fields), "DUP_DROPPED", f"dupx{gi}", later="DUP_DROPPED"))
    for gi, idx in enumerate(picks[k:]):
        specs[idx].group, specs[idx].later = f"dupc{gi}", "DUPLICATE_CONFLICT"
        f = list(specs[idx].fields)
        f[3] = f"{(base[idx]['cents'] + 1) / 100:.2f}"
        specs.append(Spec(f, "DUPLICATE_CONFLICT", f"dupc{gi}", later="DUPLICATE_CONFLICT"))
    grouped = set(picks)

    # ---- labelled invalid rows (each has exactly ONE defect; "fix" is what the operator would correct) ----
    def defect(label, mutate, fix_fields=None):
        o = new_order()
        f = row(o)
        mutate(f)
        good = row(o)
        fix = {HEADER[i]: good[i] for i in (fix_fields or [])}
        specs.append(Spec(f, label, fix=fix))

    for _ in range(k):
        i = rng.choice([1, 2, 4, 5])  # customer_id, order_ts, currency, status
        defect("MISSING_REQUIRED", lambda f, i=i: f.__setitem__(i, ""), [i])
        defect("INVALID_TYPE", lambda f: f.__setitem__(3, "12.5O"), [3])
        defect("INVALID_VALUE", lambda f: f.__setitem__(3, rng.choice(["-5.00", "0.00", "10.123", "1000000.01"])))
        defect("INVALID_ENUM", lambda f: f.__setitem__(5, "SHIPPING??"), [5])
        defect("INVALID_FORMAT", lambda f: f.__setitem__(2, "2026-13-45"), [2])
        defect("INVALID_VALUE", lambda f: f.__setitem__(6, "2020-01-01T00:00:00Z"))  # updated_at < order_ts
        defect(
            "UNKNOWN_CUSTOMER", lambda f: f.__setitem__(1, rng.choice(late_customers)[0]), [1]
        )  # fixed by customers_late.csv
        defect("UNKNOWN_CUSTOMER", lambda f: f.__setitem__(1, "CUST-999999"))  # never resolvable
        o = new_order()
        specs.append(Spec(row(o)[:-2], "MALFORMED_ROW"))  # 2 fields missing
    # boundary values that are VALID
    for cents in (DEFAULT_RULES.min_cents, DEFAULT_RULES.max_cents):
        specs.append(Spec(row(new_order(), cents=cents)))

    rng.shuffle(specs)  # out-of-order input
    b1 = _write_batch(out / "orders_batch_01.csv", specs, lab)

    # ---------------- batch 2 ----------------
    free = [i for i in range(n_orders) if i not in grouped]
    rng.shuffle(free)
    n_upd, n_late, n_new, n_resend = (
        max(1, int(n_orders * p)) for p in (UPDATE_RATE, LATE_RATE, NEW_RATE, RESEND_RATE)
    )
    s2 = []
    for i in free[:n_upd]:
        o = base[i]
        s2.append(Spec(row(o, upd=o["upd"] + timedelta(days=rng.randint(1, 5)), status=FINAL_STATUS)))
    for i in free[n_upd : n_upd + n_late]:
        o = base[i]
        s2.append(Spec(row(o, upd=o["ots"] + timedelta(hours=1), status="CREATED"), "VALID_LATE"))
    for _ in range(n_new):
        s2.append(Spec(row(new_order())))
    for i in free[n_upd + n_late : n_upd + n_late + n_resend]:
        s2.append(Spec(row(base[i])))  # identical to batch 1 => UNCHANGED
    rng.shuffle(s2)
    _write_batch(out / "orders_batch_02.csv", s2, lab)

    # ---------------- corrections for replay (needs quarantine ids => depends on file hash) ----------------
    sha1 = _sha(out / "orders_batch_01.csv")
    with open(out / "corrections.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["quarantine_id", "field", "new_value"])
        for line_no, sp in b1:
            if sp.expected in ("MISSING_REQUIRED", "INVALID_TYPE", "INVALID_ENUM", "INVALID_FORMAT") and sp.fix:
                for fld, val in sp.fix.items():
                    w.writerow([make_quarantine_id(sha1, line_no), fld, val])

    # ---------------- schema-change + empty fixtures ----------------
    with open(out / "orders_bad_schema.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["order_id", "customer_id", "order_ts", "total_amount", "currency", "status", "updated_at"])
        w.writerow(
            ["ORD-90000001", "CUST-000001", "2026-02-01T00:00:00Z", "10.00", "USD", "PAID", "2026-02-02T00:00:00Z"]
        )
    with open(out / "orders_empty.csv", "w", newline="") as f:
        csv.writer(f).writerow(HEADER)
    return {"customers": len(customers), "batch1_rows": len(b1), "batch2_rows": len(s2), "seed": seed}


def _write_batch(path, specs, labels_dir):
    """Writes the file, resolves group labels, writes labels to ../labels. Returns [(line_no, Spec)]."""
    seen, numbered = set(), []
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for i, sp in enumerate(specs):
            if sp.group:
                if sp.group not in seen:
                    seen.add(sp.group)
                    sp.expected = "VALID"
                else:
                    sp.expected = sp.later
            w.writerow(sp.fields)
            numbered.append((i + 2, sp))  # header is line 1
    labels_path = Path(labels_dir) / f"labels_{Path(path).stem.replace('orders_', '')}.csv"
    with open(labels_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source_file", "line_no", "expected"])
        for line_no, sp in numbered:
            w.writerow([Path(path).name, line_no, sp.expected])
    return numbered
