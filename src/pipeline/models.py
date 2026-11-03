import datetime
import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)

from src.pipeline.db import Base


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


class OrderCurated(Base):
    __tablename__ = "orders_curated"

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_orders_curated_positive_amount"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # Business identifier
    order_id = Column(String(100), unique=True, nullable=False, index=True)
    customer_id = Column(String(100), nullable=False, index=True)

    # Parsed business fields
    order_date = Column(DateTime(timezone=True), nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)
    status = Column(String(30), nullable=False, default="complete")

    # Source lineage
    source_record_id = Column(String(64), unique=True, nullable=True, index=True)
    source_file = Column(String(500), nullable=True)
    source_row_number = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class OrderQuarantine(Base):
    __tablename__ = "orders_quarantine"

    id = Column(Integer, primary_key=True, index=True)

    # Source lineage
    source_record_id = Column(String(64), unique=True, nullable=True, index=True)
    source_file = Column(String(500), nullable=True)
    source_row_number = Column(Integer, nullable=True)

    order_id = Column(String(100), nullable=True, index=True)
    raw_payload = Column(JSON, nullable=False)
    error_reason = Column(Text, nullable=False)

    quarantined_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(
        String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )

    run_type = Column(String(30), nullable=False)
    total_records = Column(Integer, nullable=False, default=0)
    valid_records = Column(Integer, nullable=False, default=0)
    invalid_records = Column(Integer, nullable=False, default=0)

    status = Column(String(30), nullable=False, default="RUNNING")
    failure_reason = Column(Text, nullable=True)

    started_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class ReplayAttempt(Base):
    __tablename__ = "replay_attempts"

    __table_args__ = (
        UniqueConstraint(
            "quarantine_id",
            "attempt_number",
            name="uq_replay_quarantine_attempt",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    quarantine_id = Column(
        Integer,
        ForeignKey("orders_quarantine.id"),
        nullable=False,
        index=True,
    )
    curated_order_id = Column(
        Integer,
        ForeignKey("orders_curated.id"),
        nullable=True,
    )
    run_id = Column(
        String(36),
        ForeignKey("pipeline_runs.run_id"),
        nullable=True,
        index=True,
    )

    source_record_id = Column(String(64), nullable=True, index=True)
    attempt_number = Column(Integer, nullable=False)
    status = Column(String(30), nullable=False, default="STARTED")
    error_reason = Column(Text, nullable=True)
    corrected_payload = Column(JSON, nullable=True)

    attempted_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
