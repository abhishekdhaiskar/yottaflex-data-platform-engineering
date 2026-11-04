import pytest

from conftest import HEADER, good
from qpipe.validation import REQUIRED, parse_ts, validate_record

K = {"CUST-000001"}


def rec(**kw):
    return validate_record(dict(zip(HEADER, good(**kw), strict=False)), K)


def codes(**kw):
    return {c for c, _ in rec(**kw)[1]}


def test_happy_path_normalises():
    r, errs = rec(amount="19.99", cur="usd", status="paid", ots="2026-03-01T15:30:00+05:30")
    assert errs == [] and r.amount_cents == 1999 and r.currency == "USD" and r.status == "PAID"
    assert r.order_ts == "2026-03-01T10:00:00Z"  # offset -> UTC


def test_hash_is_deterministic():
    assert rec()[0].record_hash == rec()[0].record_hash


@pytest.mark.parametrize("field,val", [("cust", ""), ("amount", "   "), ("status", ""), ("oid", "")])
def test_missing_required(field, val):
    assert "MISSING_REQUIRED" in codes(**{field: val})


def test_all_errors_collected():
    r, errs = validate_record({}, K)
    assert r is None and len(errs) == len(REQUIRED)


@pytest.mark.parametrize(
    "amount,code",
    [
        ("abc", "INVALID_TYPE"),
        ("NaN", "INVALID_TYPE"),
        ("-1.00", "INVALID_VALUE"),
        ("0", "INVALID_VALUE"),
        ("10.123", "INVALID_VALUE"),
        ("1000000.01", "INVALID_VALUE"),
    ],
)
def test_bad_amounts(amount, code):
    assert codes(amount=amount) == {code}


@pytest.mark.parametrize("amount", ["0.01", "1000000.00", "1000000"])
def test_boundary_amounts_valid(amount):
    assert rec(amount=amount)[1] == []


def test_enums_and_formats():
    assert codes(status="LOST") == {"INVALID_ENUM"}
    assert codes(cur="JPY") == {"INVALID_ENUM"}
    assert codes(ots="2026-13-45") == {"INVALID_FORMAT"}
    assert codes(oid="XYZ-1") == {"INVALID_FORMAT"}


def test_unknown_customer_vs_bad_format():
    assert codes(cust="CUST-999999") == {"UNKNOWN_CUSTOMER"}
    assert codes(cust="bob") == {"INVALID_FORMAT"}


def test_updated_before_order_is_invalid():
    assert codes(upd="2026-02-01T00:00:00Z") == {"INVALID_VALUE"}


def test_naive_timestamp_assumed_utc():
    assert parse_ts("2026-03-01T10:00:00") == "2026-03-01T10:00:00Z"
