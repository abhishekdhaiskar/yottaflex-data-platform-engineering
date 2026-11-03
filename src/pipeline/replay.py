import csv
from sqlalchemy.orm import Session
from src.pipeline.db import engine, Base
from src.pipeline.models import OrderCurated, PipelineRun
from src.pipeline.validation import validate_order

def run_replay(file_path: str):
    Base.metadata.create_all(bind=engine)
    db = Session(bind=engine)
    total, replayed_count, failed_count = 0, 0, 0

    try:
        with open(file_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total += 1
                is_valid, error_msg = validate_order(row)

                if is_valid:
                    replayed_count += 1
                    order_id = row["order_id"]
                    
                    # Check if the order already exists to support idempotent replays
                    existing_order = db.query(OrderCurated).filter_by(order_id=order_id).first()
                    
                    if existing_order:
                        existing_order.customer_id = row["customer_id"]
                        existing_order.order_date = row.get("order_date")
                        existing_order.amount = float(row["amount"])
                        existing_order.status = "replayed"
                    else:
                        new_order = OrderCurated(
                            order_id=order_id,
                            customer_id=row["customer_id"],
                            order_date=row.get("order_date"),
                            amount=float(row["amount"]),
                            status="replayed"
                        )
                        db.add(new_order)
                else:
                    failed_count += 1

        db.add(PipelineRun(
            run_type="replay",
            total_records=total,
            valid_records=replayed_count,
            invalid_records=failed_count,
            status="SUCCESS"
        ))
        db.commit()
        print(f"Replay successful! Total processed: {total}, Replayed/Updated: {replayed_count}, Failed: {failed_count}")
    except Exception as e:
        db.rollback()
        print(f"Replay failed: {e}")
        raise
    finally:
        db.close()