import datetime

def validate_order(record: dict) -> tuple[bool, str | None]:
    if not record.get("order_id"):
        return False, "Missing order_id"
    if not record.get("customer_id"):
        return False, "Missing customer_id"
    
    try:
        amount = float(record.get("amount", 0))
        if amount <= 0:
            return False, "Order amount must be greater than zero"
    except (ValueError, TypeError):
        return False, "Invalid amount format"

    date_str = record.get("order_date")
    if date_str:
        try:
            datetime.datetime.fromisoformat(str(date_str))
        except ValueError:
            return False, "Invalid date format (expected ISO)"
            
    return True, None