# Test Plan

## Scope of Testing
Testing is implemented using `pytest` and verifies validation rules, database persistence, ingestion outcomes, and replay handling.

## Test Modules
1. **`tests/test_validation.py`**: Verifies rule-based edge cases:
   - Missing `order_id` or `customer_id`.
   - Zero or negative transaction amounts.
   - Malformed timestamps.
2. **`tests/test_ingest.py`**: Verifies end-to-end batch parsing, database insertion into `orders_curated`, and rejection routing to `orders_quarantine`.
3. **`tests/test_replay.py`**: Verifies that corrected records can be re-run successfully and merged into the curated store without error.

## Execution
Run the full test suite in your terminal using:
```bash
pytest


---

### 5. `docs/ai_usage_log.md`
```markdown
# AI Usage Disclosure Log

## Overview
In accordance with YottaFlex candidate project guidelines, AI tools were utilized during the development of this repository as a coding and architectural assistant.

## Areas of Assistance
- **Boilerplate generation:** Scaffolding directory layouts, SQLAlchemy base models, and initial CLI arg parsing structures.
- **Debugging:** Resolving database connection string formats and transaction session commits.
- **Documentation:** Structuring architecture guides, data dictionaries, and test plans.

## Candidate Review & Validation
- All generated code, database models, and validation logic were thoroughly reviewed, locally tested using Docker and `pytest`, and verified against business requirements by the candidate.