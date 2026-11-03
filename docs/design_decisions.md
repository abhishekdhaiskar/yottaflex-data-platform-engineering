# Design Decisions & Trade-Offs

## 1. Database & ORM Selection (PostgreSQL + SQLAlchemy)
- **Decision:** Used PostgreSQL with SQLAlchemy ORM.
- **Why:** Provides robust relational capabilities, JSON column support for raw payload storage, and seamless migration/session control.

## 2. Quarantine Routing Strategy
- **Decision:** Failed validation rows are written to `orders_quarantine` with full JSON payloads rather than crashing the batch job.
- **Why:** Ensures fault tolerance. A single malformed row will not fail an entire batch ingestion run.

## 3. Idempotent Upsert Logic
- **Decision:** Used SQLAlchemy session `.merge()` behavior mapped against unique keys (`order_id`).
- **Why:** Ensures that running ingestion or replay multiple times updates existing records safely without creating duplicate rows.