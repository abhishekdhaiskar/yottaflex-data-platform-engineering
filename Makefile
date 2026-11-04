SHELL := /bin/bash
.SHELLFLAGS := -o pipefail -c
PY ?= python
export PYTHONPATH := src

.PHONY: install test lint demo benchmark check clean
install:   ; $(PY) -m pip install -r requirements.txt
lint:      ; ruff check src tests
test:      ; @mkdir -p reports && $(PY) -m pytest -v | tee reports/test_results.txt
demo:      ; @mkdir -p reports logs && bash scripts/demo.sh 2>/dev/null
benchmark: ; @mkdir -p reports && $(PY) -m qpipe.benchmark --orders 100000 | tee reports/benchmark.txt
check:     ; @bash scripts/check_submission.sh
clean:     ; rm -rf data/warehouse.db logs .pytest_cache
