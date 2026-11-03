# YottaFlex Data Engineering Challenge

## Quarantine and Controlled Replay Data Pipeline

### Project Overview

This project implements a reliable batch data engineering pipeline that ingests source records, validates data quality, transforms valid records, publishes them to a target database, and routes invalid records to a quarantine store.

The pipeline also provides a controlled replay mechanism that allows corrected records to be reprocessed without unnecessarily processing previously successful records.

### Business Objectives

- Ingest structured source data.
- Validate schema and business rules.
- Detect duplicate and invalid records.
- Preserve rejected records with error reasons and source context.
- Publish valid records into curated tables.
- Support controlled replay after correction.
- Ensure safe reruns and idempotent processing.
- Track execution metrics and operational failures.

### Technology Stack

- Python
- PostgreSQL
- SQLAlchemy
- Docker
- Docker Compose
- Pytest
- GitHub Actions

### Architecture

Source Data → Raw Ingestion → Validation → Transformation → Curated Storage

Invalid Records → Quarantine → Correction → Controlled Replay

### Project Status

Phase 0: Repository and project setup.

Phase 1: Database and environment setup.

Phase 2: Core data ingestion and validation.

Phase 3: Quarantine and controlled replay.

Phase 4: Testing, observability and idempotency.

Phase 5: Performance evaluation and final submission.

### Execution

Complete installation and execution instructions will be maintained here as implementation progresses.

### AI Usage Disclosure

AI tools are used as development assistance for architecture discussion, code review, debugging and documentation. All submitted code and design decisions will be reviewed, executed and validated by the candidate.

A complete prompt history and explanation of personal contributions will be provided in PROMPT_HISTORY.md.

### Known Limitations

To be documented after implementation and testing.

---

## Tech Stack
- **Language:** Python 3.10+
- **Database & ORM:** PostgreSQL & SQLAlchemy
- **Containerization:** Docker & Docker Compose
- **Testing:** Pytest
- **CI/CD:** GitHub Actions

---

## Project Structure
```text
yottaflex-data-platform-engineering/
├── .github/workflows/ci.yml    # GitHub Actions CI workflow
├── config/pipeline.yaml        # Pipeline configuration settings
├── data/
│   ├── sample/orders.csv       # Sample source dataset
│   ├── generated/              # Output/generated files directory
│   └── corrected/              # Corrected files for replay directory
├── docs/                       # Architecture, design decisions, and AI logs
├── sql/reporting_queries.sql   # Operational & analytical SQL queries
├── src/pipeline/               # Core pipeline modules (DB, models, validation, ingest, replay, CLI)
├── tests/                      # Pytest test suite
├── requirements.txt            # Python dependencies
└── docker-compose.yml          # Local PostgreSQL container service