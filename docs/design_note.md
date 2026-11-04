# Design & trade-off note

**Goal**: a complete, tested vertical slice: invalid rows are quarantined with enough context to fix and replay them, and replay never re-processes good data.

**Trade-offs**
1. *SQLite vs Postgres/Spark* - chosen for zero-setup reproducibility; the loader logic (version compare + idempotent upsert) is database-agnostic.
2. *File-level transaction vs row-level* - a bad row is a **data** problem (quarantined, run still succeeds); a crash is a **system** problem (whole file rolls back). Keeps "what was loaded" easy to reason about.
3. *Quarantine row-level, schema errors file-level* - one renamed column would otherwise quarantine 100% of rows with a useless reason; failing fast is clearer.
4. *Duplicates*: exact duplicate = harmless noise (dropped, counted); same key+version with different content = real conflict (quarantined, first wins) - we do not guess.
5. *Late data*: older versions go to history, never overwrite current. Out-of-order rows inside a file are sorted by version before applying.
6. *Replay semantics*: raw payload immutable; corrections applied at replay time and recorded; reason of failure recorded separately so the original cause is never lost.
7. *Idempotency layers*: file hash (skip) -> version PK (no duplicate history) -> guarded upsert (older never beats newer) -> deterministic quarantine id.
8. *run_id is not deterministic* (timestamp + random) because each execution is a distinct event; all business entities have deterministic ids.

**Failure modes considered**: crash mid-load (rollback), same file twice (skip/force), schema drift (fail file), reference data arriving late (replay), bad correction (stays PENDING, attempts++), conflicting duplicate (quarantine), corrupted target (reconcile fails with exit 1).

**Not covered**: concurrency, streaming, SCD on customers, currency conversion, authz on replay.
