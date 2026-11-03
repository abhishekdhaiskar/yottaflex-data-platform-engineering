# AI Usage Log & Disclosure

## Project Overview
- **Project Name:** YottaFlex Data Engineering Challenge (Quarantine and Controlled Replay Data Pipeline)
- **Candidate Name:** Abhishek Nagesh Dhaiskar
- **Submission Window:** 72 Hours

## Summary of AI Tool Usage
In accordance with YottaFlex guidelines, AI assistants were used as a development accelerator for scaffolding, architecture structuring, boilerplate code generation, and test planning.

### 1. Where AI Accelerated Work
- **Project Scaffolding:** Generating initial directory structures and foundational boilerplate templates for SQLAlchemy models, Alembic/DB connections, and CLI parsers.
- **Documentation Drafts:** Structuring architectural diagrams, data dictionaries, and test plan formats to clearly communicate project decisions.
- **Boilerplate Tests:** Setting up initial `pytest` test skeletons for validation and ingestion flows.

### 2. Where Candidate Review, Validation & Customization Occurred
- **Logic Verification:** Manually reviewed and adjusted validation rules in `validation.py` and upsert workflows in `ingest.py` and `replay.py` to ensure idempotency.
- **Environment & Integration Testing:** Ran and validated local PostgreSQL Docker containers, executing the pipeline end-to-end to confirm correct routing of valid records to `orders_curated` and invalid records to `orders_quarantine`.
- **Constraint Checks:** Ensured all challenge requirements (such as tracking pipeline runs, handling error reasons, and structured replay) functioned correctly under real execution.

## Declaration
All submitted code, configuration files, and design choices have been thoroughly reviewed, executed, and validated by the candidate.