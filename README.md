# Quarantine & Controlled Replay Pipeline (Orders)

A small, fully local data-engineering pipeline that **validates incoming order files, routes bad
records to a quarantine table (with reason + source file/line + raw payload), and lets an operator
replay only the quarantined rows after a fix** - without touching rows that already loaded.

Python 3.11+, **standard library only** (SQLite). `pytest` (tests) and `ruff` (lint, optional) are the only dev tools.

## 1. Quick start (clean machine, ~1 minute)

```bash
git clone <your-repo-url> && cd <repo>
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt                          # pytest only
make test      # 59 tests, writes reports/test_results.txt  (or: PYTHONPATH=src python -m pytest -v)
make lint      # ruff (optional: pip install ruff)
make demo      # full scenario       (or: ./scripts/demo.sh)
make benchmark # 100k-order timing, writes reports/benchmark.txt
make check     # pre-submission self-check (files, placeholders, secrets, git state)
```
`make demo` produces `data/warehouse.db`, `logs/pipeline.log` and `reports/reconciliation.md`.
Windows without `make`: set `PYTHONPATH=src` and call the commands in section 5 directly.

## 2. Architecture / flow

```
 orders_*.csv ─► read + schema check ─► row validation ─► in-batch dedupe ─► version-aware publish ─► fact_order (current)
 (source)         │ missing column?      │ 8 error codes     │ exact dup: drop    │ one transaction      fact_order_history (all versions)
                  ▼                      ▼                   ▼ conflict: reject   │
              run = FAILED           ┌──────────────────── quarantine ◄───────────┘ (raw JSON + codes + file + line)
              (nothing loaded)       │
                                     ▼
   operator fixes cause / writes corrections.csv ─► `replay` (PENDING rows only, same validator + same loader)
                                     │
   every step writes a row to pipeline_run  ─►  `reconcile` report + `verify-labels`
```
Modules (`src/qpipe/`), each with one responsibility:

| module | responsibility |
|---|---|
| `config.py` + `config/pipeline.toml` | all business rules & settings (statuses, currencies, amount limits, id patterns, paths, chunk size) - **nothing hardcoded in logic** |
| `validation.py` | pure row validation/normalisation (`validate_record(raw, customers, rules)`) |
| `loader.py` | idempotent, version-aware publish; shared by ingest **and** replay |
| `ingest.py` | read file, classify rows, orchestrate one atomic load |
| `replay.py` | controlled replay of PENDING quarantine rows |
| `reference.py` | strict load of `dim_customer` |
| `runs.py` | `RunResult` + `pipeline_run` persistence (observability) |
| `ids.py` | deterministic ids, hashing, run ids |
| `reconcile.py` / `labels.py` | validation report / expected-label verification |
| `generator.py`, `benchmark.py`, `db.py`, `cli.py` | data generator, timing, schema, command line |

## 3. Key design decisions (short; full note in `docs/design_note.md`)

| Decision | Why |
|---|---|
| SQLite | Zero setup, transactional, SQL for reconciliation; swap for Postgres by changing `db.py`. |
| One transaction per file | A crash can never leave half a batch loaded. Retry = run the same command. |
| `(order_id, updated_at)` is the record version | Makes loads idempotent and handles late/out-of-order data deterministically. |
| `fact_order` = current, `fact_order_history` = every version | History is preserved, never silently overwritten. |
| Quarantine keeps the **raw payload and original reason immutable** | Full traceability; replay writes `last_error_*`, `attempts`, `corrections` separately. |
| Replay reuses validator + loader | No second code path to drift out of sync. |
| Amounts stored as integer cents (`Decimal` parsing) | No float rounding in aggregates. |

### Configuration (no hardcoding)
Rules and settings come from `config/pipeline.toml` (auto-loaded if present, or `--config path`); omitted keys fall back to
typed defaults in `config.py`; unknown keys or invalid bounds fail fast with exit code 2. A test guarantees the shipped TOML equals the code defaults,
and another proves that changing the config changes pipeline behaviour (`tests/test_config.py`). CLI flags (`--db`, `--log-file`, `--chunk-size`) override the file.
Exit codes: `0` ok, `1` run FAILED / reconciliation failed / label mismatch, `2` bad configuration - so cron/Airflow can alert on them.

## 4. Assumptions
* Source is CSV files dropped per batch; one row = one version of an order (`updated_at` = version).
* Naive timestamps are treated as UTC; offsets are converted to UTC; stored as ISO-8601 `...Z`.
* Currencies: USD/EUR/GBP/INR; amount 0.01-1,000,000.00 with max 2 decimals; amounts are not converted across currencies.
* `customers.csv` is trusted reference data: strict load, any bad row fails that load.
* Zero-byte file (no header) = FAILED; header-only file = SUCCESS with 0 rows.
* Extra columns are ignored with a warning; a missing required column fails the whole file (nothing loaded).

## 5. Commands

```bash
export PYTHONPATH=src            # PowerShell: $env:PYTHONPATH="src"
python -m qpipe generate --orders 200 --seed 42          # inputs -> data/sample, labels -> data/labels
python -m qpipe load-customers --file data/sample/customers.csv
python -m qpipe ingest --file data/sample/orders_batch_01.csv [--force] [--chunk-size 5000]
python -m qpipe replay [--error-code X] [--source-file F] [--source-run-id R] [--id Q] [--limit N] [--corrections corrections.csv] [--dry-run]
python -m qpipe reconcile --out reports/reconciliation.md   # exit code 1 if any check fails
python -m qpipe verify-labels data/labels/labels_batch_01.csv data/labels/labels_batch_02.csv
python -m qpipe runs
python -m qpipe.benchmark --orders 100000
```
Large dataset: `python -m qpipe generate --orders 100000 --out data/large --labels-dir data/labels_large` then ingest `data/large/*`.

Ready-made SQL in `sql_sample_queries.sql`.

## 6. Error codes
`MALFORMED_ROW` (wrong field count) · `MISSING_REQUIRED` · `INVALID_FORMAT` (ids, ISO timestamps) · `INVALID_TYPE` (non-numeric amount) ·
`INVALID_VALUE` (range, >2 decimals, `updated_at < order_ts`) · `INVALID_ENUM` (status/currency) · `UNKNOWN_CUSTOMER` (referential) ·
`DUPLICATE_CONFLICT` (same key+version, different content). All errors on a row are collected, not just the first.

## 7. Idempotency, retry, restart, backfill
* **Re-run same file**: sha256 recorded; identical file already `SUCCESS` -> run recorded as `SKIPPED`.
* **`--force`**: reprocesses anyway; safe because history PK `(order_id, updated_at)` makes each row `UNCHANGED`; quarantine ids are deterministic (`sha1(file_sha256:line)`) and inserted `OR IGNORE`, so rejects are not duplicated and resolved ones stay resolved.
* **Partial failure / restart**: whole file is one transaction -> rollback, run = `FAILED` with the error, exit code 1. `FAILED` runs never block a retry. (Test: `test_partial_failure_rolls_back_and_retry_works`.)
* **Replay**: touches only `PENDING` rows; a 2nd replay selects 0 rows. `--dry-run` writes nothing. Failed attempts increment `attempts`.
* **Backfill**: ingest historical files in any order; version comparison guarantees the newest version wins and older ones go to history as `LATE`.

## 8. Test evidence (`reports/test_results.txt`, 59 tests; CI in `.github/workflows/ci.yml` runs lint + tests + demo)
| Required scenario | Test(s) |
|---|---|
| happy path | `test_happy_path`, `test_full_pipeline_matches_labels_and_reconciles` |
| empty batch | `test_empty_batch_header_only`, `test_zero_byte_file_fails` |
| malformed records | `test_malformed_row_quarantined_with_context` |
| missing required / nulls | `test_missing_required`, `test_nulls_and_invalid_reference_quarantined` |
| duplicates | `test_exact_duplicate_dropped_and_counted`, `test_conflicting_duplicate_quarantined`, `test_conflict_against_already_loaded_version` |
| schema change | `test_schema_change_missing_column_fails_cleanly`, `test_extra_column_is_warning_not_failure` |
| partial failure + retry | `test_partial_failure_rolls_back_and_retry_works` |
| late / out-of-order | `test_late_arriving_older_version_does_not_overwrite`, `test_out_of_order_inside_one_file` |
| invalid reference key | `test_unknown_customer_vs_bad_format`, replay tests |
| rerun same input | `test_rerun_same_file_is_skipped`, `test_forced_rerun_creates_no_duplicates` |
| domain edge cases | amount boundaries 0.01 / 1,000,000.00, >2 decimals, `updated_at < order_ts`, history preserved on update |
| replay | 8 tests in `test_replay.py` (untouched good rows, corrections audit, idempotent, dry-run, filters) |
| reconciliation | `test_reconciliation_detects_corruption` (the checks really fail on bad data) |
| configuration | `test_config.py` (defaults, TOML override changes behaviour, unknown key rejected) |
| CLI contract | `test_cli.py` (exit codes 0/1/2) |

**Expected-answer labels** live in `data/labels/` (separate from `data/sample/`); `verify-labels` compares them with what the pipeline actually did.

## 9. Sample results (seed 42, 200 orders) - see `reports/reconciliation.md`
Batch 1: 224 rows read -> 202 loaded, 2 exact duplicates dropped, 20 quarantined. Batch 2: 32 rows -> 4 inserted, 20 updated, 6 late (history only), 2 unchanged.
Replay: 2 resolved by loading missing customers; 8 resolved by corrections; the rest correctly remain `PENDING`.

## 10. Performance (`reports/benchmark.txt`, 100,000 orders -> 111,002 rows incl. defects)
Optimised ingest ~22k rows/s (~5 s for 111k rows). Naive baseline (per-row SELECT + commit per row) ~0.9k rows/s => **~24x**.
**Optimisation applied:** bulk prefetch of existing versions (1 query / 500 ids), in-memory customer set, `executemany`, one commit.
Numbers vary by machine.

## 11. Known limitations & next steps
* Single-writer SQLite; no concurrent ingests. Next: Postgres + row-level locks / `INSERT ... ON CONFLICT`.
* Whole file is read into memory (fine to a few million rows). Next: stream in chunks with per-chunk savepoints.
* Corrections are CSV-only; no approval workflow/UI.
* No currency conversion; no status-transition rules (e.g. DELIVERED -> CREATED is accepted if versioned later).
* Orchestration (Airflow/cron) and alerting (e.g. on non-zero exit / quarantine thresholds) not included.
* Non-UTF-8 files fail the run (documented, not auto-repaired).
* Rows loaded by `replay` carry `source_file = 'replay'`; their original file/line is kept in the `quarantine` row (see `docs/CODE_WALKTHROUGH.md`).

## 12. Naming conventions
snake_case tables/columns; `dim_`/`fact_` prefixes; IDs: `ORD-########`, `CUST-######`, quarantine `q_<16 hex>` (deterministic),
`run_id = <type>_<UTC yyyymmddThhmmssZ>_<6 hex>` (unique per execution by design); timestamps ISO-8601 UTC; `run_id` and `source_file` on every target row.

## 13. AI usage
See `docs/AI_USAGE.md` and `prompts/PROMPT_LOG.md`.

## 14. How to verify this submission
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
make test && make demo
```
Expected: `59 passed`; `label check: OK - pipeline behaviour matches all expected labels`; `reconciliation: ALL CHECKS PASSED`.
Evidence produced by these commands is committed in `reports/` (`test_results.txt`, `benchmark.txt`, `reconciliation.md`).
**Environment:** Python 3.11+ (uses `tomllib`), `make` + bash (Windows: Git Bash or WSL, or run the commands in section 5). No network, no database server, no API keys, no paid services.

### 5-minute reviewer walkthrough
1. `make demo` - watch the 10 steps (bad rows quarantined, re-run skipped, schema change fails cleanly, replay after the fix).
2. Open `reports/reconciliation.md` - 7 checks, all PASS, plus quarantine by error code and status.
3. `sqlite3 data/warehouse.db < sql_sample_queries.sql` - run history, trace a rejected row to file + line + raw payload.
4. Read `src/qpipe/loader.py` (version-aware upsert, shared by ingest and replay) then `replay.py`.
5. `tests/test_replay.py` and `tests/test_ingest.py` map to the scenario table in section 8.

## 15. How AI was used
See `docs/AI_USAGE.md` (what AI did vs. what I reviewed and validated) and `prompts/PROMPT_LOG.md` (all prompts).

## 16. Third-party code, licences, data safety
* Runtime dependencies: **none** (Python standard library only). Dev tools: `pytest` and `ruff` (both MIT-licensed, installed from PyPI, not vendored).
* No existing pipeline or solution code is included; the project is released under the MIT `LICENSE` in this repository.
* All data in `data/` is **synthetic** (seeded generator). No credentials, personal data or proprietary code are in the repository.
* More review material: `docs/CODE_WALKTHROUGH.md` (decisions, where to find them, known weak spots).
