import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON
from src.pipeline.db import Base

class OrderCurated(Base):
    __tablename__ = "orders_curated"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, unique=True, index=True)
    customer_id = Column(String, index=True)
    order_date = Column(DateTime)
    amount = Column(Float)
    status = Column(String)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)

class OrderQuarantine(Base):
    __tablename__ = "orders_quarantine"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, index=True, nullable=True)
    raw_payload = Column(JSON)
    error_reason = Column(Text)
    quarantined_at = Column(DateTime, default=datetime.datetime.utcnow)

class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_type = Column(String)
    total_records = Column(Integer)
    valid_records = Column(Integer)
    invalid_records = Column(Integer)
    status = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)