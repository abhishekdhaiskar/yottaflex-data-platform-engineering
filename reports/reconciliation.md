# Reconciliation report
_Generated 2026-11-04T02:36:19Z_

## Checks

| Result | Check | Detail |
|---|---|---|
| PASS | run counts reconcile (read = valid + dup_dropped + quarantined; history rows = inserted+updated+late) | all successful runs balance |
| PASS | every order in history has exactly one current row | fact_order=216, distinct history ids=216 |
| PASS | referential integrity: no fact_order without dim_customer | orphans=0 |
| PASS | current row is always the latest version in history | stale current rows=0 |
| PASS | current row content equals its history version (hash) | mismatches=0 |
| PASS | every quarantine row has source file, line, raw record and error reason | untraceable=0 |
| PASS | every RESOLVED quarantine row points to its replay run | missing=0 |

## Runs

| run_id | type | file | status | read | valid | ins | upd | late | unchanged | dup | quarantined |
|---|---|---|---|---|---|---|---|---|---|---|---|
| customers_20261104T023612Z_02f28b | customers | customers.csv | SUCCESS | 20 | 20 | 20 | 0 | 0 | 0 | 0 | 0 |
| ingest_20261104T023612Z_882c0c | ingest | orders_batch_01.csv | SUCCESS | 224 | 202 | 202 | 0 | 0 | 0 | 2 | 20 |
| ingest_20261104T023614Z_62ab4d | ingest | orders_batch_02.csv | SUCCESS | 32 | 32 | 4 | 20 | 6 | 2 | 0 | 0 |
| ingest_20261104T023615Z_1fcefb | ingest | orders_bad_schema.csv | FAILED | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| ingest_20261104T023615Z_8c4c88 | ingest | orders_batch_02.csv | SKIPPED | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| ingest_20261104T023616Z_bbd4ba | ingest | orders_empty.csv | SUCCESS | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| customers_20261104T023617Z_60c4db | customers | customers_late.csv | SUCCESS | 3 | 3 | 3 | 0 | 0 | 0 | 0 | 0 |
| replay_20261104T023617Z_e5cb7e | replay |  | SUCCESS | 4 | 2 | 2 | 0 | 0 | 0 | 0 | 2 |
| replay_20261104T023618Z_734ffb | replay |  | SUCCESS | 18 | 8 | 8 | 0 | 0 | 0 | 0 | 10 |

## Target summary

- fact_order rows: 216
- fact_order_history rows: 242

| status | orders | total_amount (major units, all currencies) |
|---|---|---|
| CREATED | 65 | 168574.66 |
| DELIVERED | 20 | 56022.34 |
| PAID | 63 | 156709.76 |
| SHIPPED | 68 | 1160470.18 |

## Quarantine by error code and status

| error_code | status | rows |
|---|---|---|
| DUPLICATE_CONFLICT | PENDING | 2 |
| INVALID_ENUM | RESOLVED | 2 |
| INVALID_FORMAT | RESOLVED | 2 |
| INVALID_TYPE | RESOLVED | 2 |
| INVALID_VALUE | PENDING | 4 |
| MALFORMED_ROW | PENDING | 2 |
| MISSING_REQUIRED | RESOLVED | 2 |
| UNKNOWN_CUSTOMER | PENDING | 2 |
| UNKNOWN_CUSTOMER | RESOLVED | 2 |
