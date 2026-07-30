"""
trip.py — Pydantic schemas for trip creation and output.

TripCreate now accepts the full Composite Constraint fields so the organiser
can specify group-level logistics constraints at trip creation time.
Participants can also override / extend these in their individual surveys.
"""

import uuid
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class TripCreate(BaseModel):
    name: str
    organizer_name: str
    organizer_email: EmailStr
    trip_month: str | None = None
    duration_days: int | None = None

    # ── Logistics Constraint Fields ───────────────────────────────────────────
    activity_intensity_min: int | None = Field(
        default=None, ge=1, le=5,
        description="Minimum intensity the least-active member can handle (1–5)",
    )
    activity_intensity_max: int | None = Field(
        default=None, ge=1, le=5,
        description="Maximum intensity the most adventurous member wants (1–5)",
    )
    mandatory_amenities: list[str] = Field(
        default_factory=list,
        description="Amenities every destination must provide for the group",
    )
    transit_preferences: list[str] = Field(
        default_factory=list,
        description="Preferred travel modes — drives the radius calculator",
    )
    immovable_events: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Fixed schedule events the planner must respect",
    )
    origin_city: str | None = Field(
        default=None,
        description="Departure city for the radius calculator (required for Private Car)",
    )


class TripOut(BaseModel):
    id: uuid.UUID
    organizer_name: str
    organizer_email: EmailStr
    name: str
    status: str
    trip_month: str | None = None
    duration_days: int | None = None
    settings: dict[str, Any]
    activity_intensity_min: int | None = None
    activity_intensity_max: int | None = None
    mandatory_amenities: list[str] = Field(default_factory=list)
    transit_preferences: list[str] = Field(default_factory=list)
    immovable_events: list[dict[str, Any]] = Field(default_factory=list)
    origin_city: str | None = None

    model_config = {"from_attributes": True}
