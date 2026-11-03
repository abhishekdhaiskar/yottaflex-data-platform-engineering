import csv
from sqlalchemy.orm import Session
from src.pipeline.db import engine, Base
from src.pipeline.models import OrderCurated, OrderQuarantine, PipelineRun
from src.pipeline.validation import validate_order

def init_db():
    Base.metadata.create_all(bind=engine)

def run_ingestion(file_path: str):
    init_db()
    db = Session(bind=engine)
    total, valid_count, invalid_count = 0, 0, 0

    try:
        with open(file_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total += 1
                is_valid, error_msg = validate_order(row)

                if is_valid:
                    valid_count += 1
                    order_id = row["order_id"]
                    
                    # Check if record already exists in curated store to achieve idempotency
                    existing_order = db.query(OrderCurated).filter_by(order_id=order_id).first()
                    
                    if existing_order:
                        existing_order.customer_id = row["customer_id"]
                        existing_order.order_date = row.get("order_date")
                        existing_order.amount = float(row["amount"])
                        existing_order.status = row.get("status", "complete")
                    else:
                        new_order = OrderCurated(
                            order_id=order_id,
                            customer_id=row["customer_id"],
                            order_date=row.get("order_date"),
                            amount=float(row["amount"]),
                            status=row.get("status", "complete")
                        )
                        db.add(new_order)
                else:
                    invalid_count += 1
                    db.add(OrderQuarantine(
                        order_id=row.get("order_id") if row.get("order_id") else None,
                        raw_payload=row,
                        error_reason=error_msg
                    ))
        
        db.add(PipelineRun(
            run_type="ingest",
            total_records=total,
            valid_records=valid_count,
            invalid_records=invalid_count,
            status="SUCCESS"
        ))
        db.commit()
        print(f"Ingestion successful! Total: {total}, Valid: {valid_count}, Quarantined: {invalid_count}")
    except Exception as e:
        db.rollback()
        print(f"Ingestion failed: {e}")
        raise
    finally:
        db.close()