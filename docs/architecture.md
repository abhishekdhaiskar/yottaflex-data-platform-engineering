# Architecture Documentation - YottaFlex Data Pipeline

## Overview
The Quarantine and Controlled Replay Data Pipeline is designed to ensure robust, idempotent, and fault-tolerant batch processing of structured order data.

## Data Flow Diagram

[ Source CSV ]
↓
[ Ingestion & Validation Engine ]
├── (Valid Records)   → [ PostgreSQL: orders_curated ]
└── (Invalid Records) → [ PostgreSQL: orders_quarantine ]
↓
[ Correction ]
↓
[ Controlled Replay CLI ] → [ PostgreSQL: orders_curated ]

## Component Architecture
1. **Source Ingestion (`src/pipeline/ingest.py`)**: Reads batch CSV files line-by-line or via DictReader.
2. **Validation Engine (`src/pipeline/validation.py`)**: Enforces data quality rules (non-null IDs, positive amounts, valid ISO timestamps).
3. **Curated Store (`orders_curated`)**: Stores clean, production-ready records with unique order constraints supporting upserts (`MERGE`).
4. **Quarantine Store (`orders_quarantine`)**: Captures rejected records along with JSON raw payloads and explicit error reasons for auditing and correction.
5. **Replay Mechanism (`src/pipeline/replay.py`)**: Reprocesses corrected files without duplicating or reprocessing previously valid records.