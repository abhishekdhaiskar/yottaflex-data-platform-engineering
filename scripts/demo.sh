#!/usr/bin/env bash
# End-to-end demo on the small sample. Safe to re-run: it starts from a clean DB.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=src
Q="python -m qpipe"
rm -f data/warehouse.db

echo "== 1. generate sample inputs (seed 42) + separate labels"
$Q generate --orders 200 --seed 42
echo "== 2. load reference data"
$Q load-customers --file data/sample/customers.csv > /dev/null
echo "== 3. ingest batch 1 (contains deliberately bad rows)"
$Q ingest --file data/sample/orders_batch_01.csv > /dev/null
echo "== 4. ingest batch 2 (updates, late-arriving, re-sent rows)"
$Q ingest --file data/sample/orders_batch_02.csv > /dev/null
echo "== 5. re-run batch 2 -> must be SKIPPED (idempotent)"
$Q ingest --file data/sample/orders_batch_02.csv > /dev/null
echo "== 6. schema change + empty file"
$Q ingest --file data/sample/orders_bad_schema.csv > /dev/null || echo "   (expected FAILED, exit code 1)"
$Q ingest --file data/sample/orders_empty.csv > /dev/null
echo "== 7. replay dry-run BEFORE fixing reference data"
$Q replay --error-code UNKNOWN_CUSTOMER --dry-run > /dev/null
echo "== 8. fix cause: load late customers, then replay only UNKNOWN_CUSTOMER"
$Q load-customers --file data/sample/customers_late.csv > /dev/null
$Q replay --error-code UNKNOWN_CUSTOMER > /dev/null
echo "== 9. replay with operator corrections"
$Q replay --corrections data/sample/corrections.csv > /dev/null
echo "== 10. verify against expected labels + reconcile"
$Q verify-labels data/labels/labels_batch_01.csv data/labels/labels_batch_02.csv
$Q reconcile --out reports/reconciliation.md > /dev/null && echo "reconciliation: ALL CHECKS PASSED (see reports/reconciliation.md)"
echo "== runs"; $Q runs
