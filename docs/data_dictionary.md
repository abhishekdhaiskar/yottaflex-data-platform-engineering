# Data Dictionary

## 1. `orders_curated` (Target Curated Table)
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | Integer | Primary Key, Auto-increment | Internal surrogate key |
| `order_id` | String | Unique, Indexed | Unique business order identifier |
| `customer_id` | String | Indexed | Customer identifier |
| `order_date` | DateTime | Not Null | Timestamp when the order was placed |
| `amount` | Float | Not Null (> 0) | Total financial value of the order |
| `status` | String | Not Null | Order status (`complete`, `replayed`, etc.) |
| `updated_at` | DateTime | Default: UtcNow | Timestamp of last record update |

## 2. `orders_quarantine` (Quarantine Table)
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | Integer | Primary Key, Auto-increment | Internal surrogate key |
| `order_id` | String | Nullable, Indexed | Order ID if available in raw payload |
| `raw_payload` | JSON | Not Null | Original unparsed row data stored as JSON |
| `error_reason` | Text | Not Null | Specific validation failure description |
| `quarantined_at` | DateTime | Default: UtcNow | Timestamp when record was rejected |

## 3. `pipeline_runs` (Operational Audit Log)
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | Integer | Primary Key, Auto-increment | Run execution ID |
| `run_type` | String | Not Null | Execution type (`ingest` or `replay`) |
| `total_records` | Integer | Not Null | Total records processed in run |
| `valid_records` | Integer | Not Null | Count of successful valid rows |
| `invalid_records` | Integer | Not Null | Count of rejected quarantined rows |
| `status` | String | Not Null | Execution status (`SUCCESS`, `FAILED`) |
| `created_at` | DateTime | Default: UtcNow | Run start timestamp |