# Data dictionary

## Source: `orders_*.csv` (required columns; order of columns is free, names are case-insensitive)
| column | type | null? | rules |
|---|---|---|---|
| order_id | text | no | `ORD-` + 6-12 digits. Business key. |
| customer_id | text | no | `CUST-` + 4-12 digits; must exist in `dim_customer` (referential integrity). |
| order_ts | ISO-8601 | no | When the order was placed. Offsets converted to UTC; naive = UTC. |
| amount | decimal | no | 0.01 - 1,000,000.00, max 2 decimals. |
| currency | text | no | USD, EUR, GBP, INR (case-insensitive, stored upper). |
| status | text | no | CREATED, PAID, SHIPPED, DELIVERED, CANCELLED, REFUNDED. |
| updated_at | ISO-8601 | no | **Version of the record**; must be >= order_ts. |

Grain: one source row = one version of one order. Unique key of a version: `(order_id, updated_at)`.

## Source: `customers*.csv`
`customer_id` (PK), `customer_name`, `country_code` (2 letters). Strict load.

## Target tables
**dim_customer**: customer_id PK, customer_name, country_code, run_id, source_file.

**fact_order** (current state, 1 row per order): order_id PK, customer_id FK, order_ts, `amount_cents` (INTEGER, derived = amount x 100),
currency, status, `source_updated_at`, `record_hash` (derived sha1 of normalised fields), run_id, source_file, loaded_at.

**fact_order_history** (append-only): same columns; PK `(order_id, source_updated_at)`.

**quarantine**: `quarantine_id` PK (deterministic), run_id (rejecting run), source_file, source_line, raw_record (JSON, immutable),
error_codes / error_messages (JSON lists, immutable original reason), status (PENDING | RESOLVED), attempts, created_at,
last_attempt_at, last_error_codes / last_error_messages (latest failed replay), resolved_run_id, corrections (JSON).

**pipeline_run**: run_id PK, run_type (ingest | replay | customers), source_file, file_sha256, status (RUNNING | SUCCESS | FAILED | SKIPPED),
started_at, ended_at, rows_read, rows_valid, rows_inserted, rows_updated, rows_late, rows_unchanged, rows_dup_dropped, rows_quarantined, error_message, warnings.

## Metric identities (checked by `reconcile`)
* ingest: `rows_read = rows_valid + rows_dup_dropped + rows_quarantined`
* both: `rows_valid = inserted + updated + late + unchanged`
* replay: `rows_read (selected) = rows_valid (resolved) + rows_quarantined (still pending)`
* `history rows with run_id = inserted + updated + late`

## Labels (separate from input): `data/labels/labels_*.csv`
`source_file, line_no, expected` where expected is VALID, VALID_LATE, DUP_DROPPED or an error code.
