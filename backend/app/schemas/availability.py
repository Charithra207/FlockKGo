"""
schemas/availability.py — Pydantic schemas for the Destination Availability endpoint.

Phase 5, Task 5.1 (also used by Phase 7).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AvailabilityRequest(BaseModel):
    """Request body for POST /admin/destinations/{id}/availability."""

    is_available: bool
    reason: str = Field(..., max_length=200)
    expires_at: datetime | None = None


class AvailabilityResponse(BaseModel):
    """Response for availability endpoints."""

    id: uuid.UUID
    destination_id: uuid.UUID
    destination_name: str
    is_available: bool
    reason: str
    expires_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
