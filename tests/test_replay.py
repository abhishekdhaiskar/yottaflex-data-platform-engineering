import pytest
from src.pipeline.models import OrderCurated
from src.pipeline.validation import validate_order

def test_controlled_replay(db_session):
    # Simulate corrected record coming from quarantine/correction file
    corrected_row = {
        "order_id": "O-2",
        "customer_id": "C-2",
        "order_date": "2026-10-01T11:00:00",
        "amount": "250.0",
        "status": "replayed"
    }

    is_valid, err = validate_order(corrected_row)
    assert is_valid is True

    # Replay into curated table
    db_session.merge(OrderCurated(
        order_id=corrected_row["order_id"],
        customer_id=corrected_row["customer_id"],
        amount=float(corrected_row["amount"]),
        status=corrected_row["status"]
    ))
    db_session.commit()

    replayed_order = db_session.query(OrderCurated).filter_by(order_id="O-2").first()
    assert replayed_order is not None
    assert replayed_order.amount == 250.0
    assert replayed_order.status == "replayed"