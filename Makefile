PY ?= python
export PYTHONPATH := src

.PHONY: install test lint demo benchmark clean
install:   ; $(PY) -m pip install -r requirements.txt
lint:      ; ruff check src tests
test:      ; $(PY) -m pytest -v | tee reports/test_results.txt
demo:      ; ./scripts/demo.sh 2>/dev/null
benchmark: ; $(PY) -m qpipe.benchmark --orders 100000 | tee reports/benchmark.txt
clean:     ; rm -rf data/warehouse.db logs .pytest_cache
