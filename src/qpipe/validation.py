"""Row-level validation + normalisation. Pure functions: easy to unit-test."""

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from functools import lru_cache

from .config import DEFAULT_RULES, Rules

REQUIRED = ["order_id", "customer_id", "order_ts", "amount", "currency", "status", "updated_at"]  # source contract

# Error codes (documented in README / data dictionary)
MISSING_REQUIRED = "MISSING_REQUIRED"
INVALID_FORMAT = "INVALID_FORMAT"
INVALID_TYPE = "INVALID_TYPE"
INVALID_VALUE = "INVALID_VALUE"
INVALID_ENUM = "INVALID_ENUM"
UNKNOWN_CUSTOMER = "UNKNOWN_CUSTOMER"
MALFORMED_ROW = "MALFORMED_ROW"
DUPLICATE_CONFLICT = "DUPLICATE_CONFLICT"
ERROR_CODES = frozenset(
    {
        MISSING_REQUIRED,
        INVALID_FORMAT,
        INVALID_TYPE,
        INVALID_VALUE,
        INVALID_ENUM,
        UNKNOWN_CUSTOMER,
        MALFORMED_ROW,
        DUPLICATE_CONFLICT,
    }
)


@lru_cache(maxsize=32)
def _rx(pattern: str):
    return re.compile(pattern)


@dataclass(frozen=True)
class ValidRecord:
    order_id: str
    customer_id: str
    order_ts: str
    amount_cents: int
    currency: str
    status: str
    updated_at: str
    record_hash: str


def parse_ts(value: str) -> str:
    """Parse ISO-8601; naive timestamps are assumed UTC. Returns normalised UTC 'Z' string."""
    s = value.strip()
    if s.endswith(("Z", "z")):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)  # raises ValueError if bad
    dt = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def make_hash(*parts) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()


def validate_record(raw: dict, known_customers: set, rules: Rules = DEFAULT_RULES):
    """Return (ValidRecord | None, [(error_code, message), ...]). Collects ALL errors."""
    errors = []
    v = {}
    for f in REQUIRED:
        x = raw.get(f)
        v[f] = "" if x is None else str(x).strip()
        if v[f] == "":
            errors.append((MISSING_REQUIRED, f"{f} is required"))

    if v["order_id"] and not _rx(rules.order_id_pattern).match(v["order_id"]):
        errors.append((INVALID_FORMAT, f"order_id '{v['order_id']}' does not match {rules.order_id_pattern}"))

    cust_ok = False
    if v["customer_id"]:
        if not _rx(rules.customer_id_pattern).match(v["customer_id"]):
            errors.append(
                (INVALID_FORMAT, f"customer_id '{v['customer_id']}' does not match {rules.customer_id_pattern}")
            )
        elif v["customer_id"] not in known_customers:
            errors.append((UNKNOWN_CUSTOMER, f"customer_id '{v['customer_id']}' not in dim_customer"))
        else:
            cust_ok = True

    ts = {}
    for f in ("order_ts", "updated_at"):
        if v[f]:
            try:
                ts[f] = parse_ts(v[f])
            except ValueError:
                errors.append((INVALID_FORMAT, f"{f} '{v[f]}' is not ISO-8601"))
    if len(ts) == 2 and ts["updated_at"] < ts["order_ts"]:
        errors.append((INVALID_VALUE, "updated_at is earlier than order_ts"))

    cents = None
    if v["amount"]:
        try:
            d = Decimal(v["amount"])
            if not d.is_finite():
                raise InvalidOperation
        except InvalidOperation:
            errors.append((INVALID_TYPE, f"amount '{v['amount']}' is not numeric"))
        else:
            lo, hi = Decimal(rules.min_cents) / 100, Decimal(rules.max_cents) / 100
            if not lo <= d <= hi:
                errors.append((INVALID_VALUE, f"amount {d} outside {lo}..{hi}"))
            elif d != d.quantize(Decimal("0.01")):
                errors.append((INVALID_VALUE, f"amount {d} has more than 2 decimal places"))
            else:
                cents = int(d * 100)

    currency = v["currency"].upper()
    if currency and currency not in rules.currencies:
        errors.append((INVALID_ENUM, f"currency '{v['currency']}' not in {sorted(rules.currencies)}"))
    status = v["status"].upper()
    if status and status not in rules.statuses:
        errors.append((INVALID_ENUM, f"status '{v['status']}' not in {sorted(rules.statuses)}"))

    if errors:
        return None, errors
    assert cust_ok and cents is not None
    h = make_hash(v["order_id"], v["customer_id"], ts["order_ts"], cents, currency, status, ts["updated_at"])
    return ValidRecord(
        v["order_id"], v["customer_id"], ts["order_ts"], cents, currency, status, ts["updated_at"], h
    ), []
