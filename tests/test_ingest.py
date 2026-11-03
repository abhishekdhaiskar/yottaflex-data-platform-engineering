import pytest
from src.pipeline.models import OrderCurated, OrderQuarantine
from src.pipeline.validation import validate_order

def test_ingestion_routing(db_session):
    # Simulate batch rows
    rows = [
        {"order_id": "O-1", "customer_id": "C-1", "order_date": "2026-10-01T10:00:00", "amount": "100.0"},
        {"order_id": "", "customer_id": "C-2", "order_date": "2026-10-01T10:00:00", "amount": "200.0"}, # Invalid (missing ID)
    ]

    for row in rows:
        is_valid, err = validate_order(row)
        if is_valid:
            db_session.merge(OrderCurated(
                order_id=row["order_id"],
                customer_id=row["customer_id"],
                amount=float(row["amount"])
            ))
        else:
            db_session.add(OrderQuarantine(
                order_id=row.get("order_id") or None,
                raw_payload=row,
                error_reason=err
            ))
    db_session.commit()

    curated_records = db_session.query(OrderCurated).all()
    quarantine_records = db_session.query(OrderQuarantine).all()

    assert len(curated_records) == 1
    assert curated_records[0].order_id == "O-1"
    
    assert len(quarantine_records) == 1
    assert "order_id" in quarantine_records[0].error_reason