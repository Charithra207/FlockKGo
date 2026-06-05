"""
task_run.py — Tracks Celery task lifecycle per trip.

Why store this in the DB and not just use Celery's result backend?
  - The frontend can poll /trips/{id}/analysis without knowing anything
    about Celery task IDs.
  - We get persistent history even after Celery results expire (24h).
  - We can store a human-readable error message, not just a stack trace.
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.sql import func

from app.db.database import Base


class TaskRun(Base):
    __tablename__ = "task_runs"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    trip_id = Column(Uuid, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    celery_task_id = Column(String(255), nullable=True)   # Celery-assigned ID

    # pending → running → complete | failed
    status = Column(String(20), nullable=False, default="pending")
    error_message = Column(Text, nullable=True)           # set on failure

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
