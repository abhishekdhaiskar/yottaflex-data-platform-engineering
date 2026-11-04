-- Run:  sqlite3 data/warehouse.db < sql_sample_queries.sql      (or any SQLite browser)

-- 1. Run history / observability
SELECT run_id, run_type, source_file, status, rows_read, rows_valid, rows_dup_dropped, rows_quarantined, error_message
FROM pipeline_run ORDER BY started_at;

-- 2. Source-to-target reconciliation per ingest run (must be 0 in the last column)
SELECT run_id, rows_read, rows_valid + rows_dup_dropped + rows_quarantined AS accounted,
       rows_read - (rows_valid + rows_dup_dropped + rows_quarantined) AS diff
FROM pipeline_run WHERE run_type='ingest' AND status='SUCCESS';

-- 3. What is waiting in quarantine, and why?
SELECT j.value AS error_code, COUNT(*) AS pending_rows
FROM quarantine q, json_each(q.error_codes) j WHERE q.status='PENDING'
GROUP BY j.value ORDER BY pending_rows DESC;

-- 4. Trace one rejected record back to its source (file + line + raw payload)
SELECT quarantine_id, source_file, source_line, raw_record, error_messages FROM quarantine LIMIT 5;

-- 5. Order lifecycle: all versions of orders that changed (history is never overwritten)
SELECT order_id, source_updated_at, status, run_id FROM fact_order_history
WHERE order_id IN (SELECT order_id FROM fact_order_history GROUP BY order_id HAVING COUNT(*) > 1)
ORDER BY order_id, source_updated_at LIMIT 20;

-- 6. Key aggregate: revenue by status (current state), amounts stored as integer cents
SELECT status, COUNT(*) orders, SUM(amount_cents)/100.0 AS total_amount FROM fact_order GROUP BY status;

-- 7. Referential integrity (must return 0)
SELECT COUNT(*) AS orphan_orders FROM fact_order f LEFT JOIN dim_customer c USING(customer_id) WHERE c.customer_id IS NULL;

-- 8. Duplicate check on target keys (must return no rows)
SELECT order_id, COUNT(*) FROM fact_order GROUP BY order_id HAVING COUNT(*) > 1;
