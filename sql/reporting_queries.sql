-- 1. Summary of Pipeline Execution Runs
SELECT 
    id, 
    run_type, 
    total_records, 
    valid_records, 
    invalid_records, 
    status, 
    created_at 
FROM pipeline_runs 
ORDER BY created_at DESC;

-- 2. View All Successfully Curated Orders
SELECT 
    order_id, 
    customer_id, 
    order_date, 
    amount, 
    status, 
    updated_at 
FROM orders_curated 
ORDER BY order_date DESC;

-- 3. View Quarantined / Rejected Records with Error Reasons
SELECT 
    id, 
    order_id, 
    error_reason, 
    raw_payload, 
    quarantined_at 
FROM orders_quarantine 
ORDER BY quarantined_at DESC;

-- 4. Data Quality Error Summary (Count of rejections by error reason)
SELECT 
    error_reason, 
    COUNT(*) AS rejection_count 
FROM orders_quarantine 
GROUP BY error_reason 
ORDER BY rejection_count DESC;

-- 5. Total Sales Revenue from Curated Orders
SELECT 
    COUNT(id) AS total_orders, 
    SUM(amount) AS total_revenue, 
    AVG(amount) AS average_order_amount 
FROM orders_curated;