import pytest
from src.pipeline.validation import validate_order

def test_valid_order():
    record = {
        "order_id": "ORD-001",
        "customer_id": "CUST-001",
        "order_date": "2026-10-01T10:00:00",
        "amount": "150.00"
    }
    is_valid, error = validate_order(record)
    assert is_valid is True
    assert error is None

def test_missing_order_id():
    record = {
        "order_id": "",
        "customer_id": "CUST-001",
        "order_date": "2026-10-01T10:00:00",
        "amount": "150.00"
    }
    is_valid, error = validate_order(record)
    assert is_valid is False
    assert "order_id" in error

def test_negative_amount():
    record = {
        "order_id": "ORD-002",
        "customer_id": "CUST-001",
        "order_date": "2026-10-01T10:00:00",
        "amount": "-50.00"
    }
    is_valid, error = validate_order(record)
    assert is_valid is False
    assert "amount" in error

def test_invalid_date():
    record = {
        "order_id": "ORD-003",
        "customer_id": "CUST-001",
        "order_date": "not-a-date",
        "amount": "100.00"
    }
    is_valid, error = validate_order(record)
    assert is_valid is False
    assert "date format" in error