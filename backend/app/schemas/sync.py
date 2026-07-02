"""
schemas/sync.py — Pydantic schemas for SyncRun API responses.

Phase 5, Task 5.1.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SyncRunSummary(BaseModel):
    """Lightweight SyncRun representation for list endpoints."""

    id: uuid.UUID
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    fetched: int | None = None
    inserted: int | None = None
    updated: int | None = None
    deactivated: int | None = None
    rejected: int | None = None

    model_config = ConfigDict(from_attributes=True)


class SyncRunDetail(SyncRunSummary):
    """Full SyncRun representation including per-stage JSON detail."""

    stage_counts: dict | None = None

    model_config = ConfigDict(from_attributes=True)
