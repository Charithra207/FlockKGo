"""
prompt_version.py — Persists which prompt version was assigned to each trip.

Replaces the in-memory ABTestManager dict which resets on every server restart,
meaning A/B test data was being lost. Now every assignment is recorded in the DB
so we can do real statistical comparison across all trips.
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Uuid
from sqlalchemy.sql import func

from app.db.database import Base


class PromptVersionAssignment(Base):
    """Records which prompt version (v1/v2) was assigned to a trip."""
    __tablename__ = "prompt_version_assignments"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    trip_id = Column(Uuid, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, unique=True)
    version = Column(String(10), nullable=False)   # "v1" or "v2"
    assigned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
