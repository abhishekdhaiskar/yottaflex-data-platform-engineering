# Code walkthrough and likely review questions

Short answers a reviewer may ask, each pointing to the code that proves it. Flow: `validation -> loader -> ingest -> replay -> reconcile`.

| Question | Answer | Where |
|---|---|---|
| Why one transaction per file? | A bad **row** is a data problem (quarantined, run still SUCCESS). A **crash** is a system problem: the whole file rolls back, the run is FAILED, and the same command can be retried. | `ingest.py` `ingest_file`; test `test_partial_failure_rolls_back_and_retry_works` |
| How is the load idempotent? | Four layers: file sha256 (identical successful file is SKIPPED) -> history primary key `(order_id, source_updated_at)` -> guarded upsert (`WHERE excluded.source_updated_at > fact_order.source_updated_at`) -> deterministic quarantine id `sha1(file_sha256:line)` inserted with `OR IGNORE`. | `ingest.py`, `loader.py`, `ids.py`, `db.py` |
| What is a "version" of an order? | `(order_id, updated_at)`. Same version + same content = UNCHANGED; same version + different content = DUPLICATE_CONFLICT (quarantined, first one wins). | `loader.py` docstring and `load_orders` |
| What happens to late or out-of-order data? | Rows are sorted by version before applying. An older version is written to history only (`LATE`) and never overwrites the current row. | `loader.py`; tests `test_late_arriving_older_version_does_not_overwrite`, `test_out_of_order_inside_one_file` |
| What does quarantine keep? | Raw payload (JSON), original error codes and messages (immutable), source file, line number, status, attempts. | `db.py` table `quarantine`; `ingest.write_rejects` |
| How does replay avoid touching good data? | It selects only `PENDING` quarantine rows, runs the same `validate_record` and the same `loader.load_orders`, and records the outcome separately (`last_error_*`, `attempts`, `corrections`, `resolved_run_id`). | `replay.py`; `tests/test_replay.py` |
| Why integer cents? | No float rounding in aggregates; `Decimal` parsing; max 2 decimals enforced. | `validation.py` |
| A column is renamed in the source file. What happens? | The whole file fails fast with a `SchemaError` (nothing loaded) instead of quarantining 100% of rows with a useless reason. Extra columns only produce a warning. | `ingest.read_orders`; tests `test_schema_change_*`, `test_extra_column_*` |
| Where are business rules configured? | `config/pipeline.toml` over typed defaults in `config.py`; unknown keys fail with exit code 2; a test proves the shipped TOML equals the code defaults and that changing it changes behaviour. | `config.py`, `tests/test_config.py` |
| How do you know the numbers add up? | Count identities are enforced in code and re-checked by `reconcile` (read = valid + duplicates dropped + quarantined). A test corrupts data and proves the checks fail. | `reconcile.py`, `test_reconciliation_detects_corruption` |

## Weak spots I would name before being asked
- **Lineage after replay:** rows loaded by `replay` are stored with `source_file = "replay"`; the original file and line are traceable only through the `quarantine` row (`source_file`, `source_line`, `resolved_run_id`). Next step: carry the original file name into the history row.
- **Error-code filter:** `replay --error-code` matches the JSON text with `LIKE '%"CODE"%'`. Fine for this schema; SQLite JSON functions or a child table would be more robust.
- **`assert` in `validate_record`:** it is an internal invariant check and is skipped under `python -O`.
- **Single writer, whole file in memory:** see README section 11.
- **Report totals mix currencies:** the status summary adds amounts across currencies (labelled in the report); no conversion is done.
- **Benchmark baseline** is deliberately naive (per-row SELECT and commit) to show the effect of bulk prefetch; its numbers depend on the machine.
