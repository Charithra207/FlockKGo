"""
survey.py — Pydantic schema for survey submission.

Includes the new Composite Constraint fields:
  activity_intensity    — personal intensity rating 1–5
  mandatory_amenities   — amenities the participant must have
  transit_preferences   — preferred transit modes
  immovable_events      — fixed schedule events (weddings, pre-booked flights, etc.)
"""

from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class VibeEnum(str, Enum):
    beach = "beach"
    adventure = "adventure"
    cultural = "cultural"
    nightlife = "nightlife"
    nature = "nature"
    food = "food"
    relaxation = "relaxation"
    city = "city"


class ClimateEnum(str, Enum):
    warm = "warm"
    cold = "cold"
    any = "any"


class ActivityLevelEnum(str, Enum):
    relaxed = "relaxed"
    moderate = "moderate"
    intense = "intense"


class TransitModeEnum(str, Enum):
    """Recognised transit modes for the duration/radius calculator."""
    private_car = "Private Car"
    train = "Train"
    flight = "Flight"
    bus = "Bus"
    motorbike = "Motorbike"
    any = "Any"


class AmenityEnum(str, Enum):
    """
    Recognised mandatory amenity labels.
    The pipeline matches these against destination travel_dna / tourism_metadata.
    """
    vegetarian_friendly = "Vegetarian Friendly"
    vegan_friendly = "Vegan Friendly"
    wheelchair_accessible = "Wheelchair Accessible"
    high_speed_wifi = "High-speed WiFi"
    family_friendly = "Family Friendly"
    pet_friendly = "Pet Friendly"
    atm_nearby = "ATM Nearby"
    medical_facilities = "Medical Facilities"
    english_speaking = "English Speaking"


class ImmovableEvent(BaseModel):
    """A fixed schedule anchor that the AI must plan around."""
    label: str = Field(description="Human-readable event name, e.g. 'Wedding'")
    event_date: date = Field(description="Fixed date of the event")
    type: str = Field(
        default="block",
        description=(
            "Type of constraint: "
            "'block' (trip cannot overlap), "
            "'arrival_deadline' (must arrive before this date), "
            "'departure_deadline' (must depart by this date)"
        ),
    )

    @field_validator("type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        allowed = {"block", "arrival_deadline", "departure_deadline"}
        if v not in allowed:
            raise ValueError(f"type must be one of {allowed}")
        return v


class SurveySubmit(BaseModel):
    # ── Core fields ───────────────────────────────────────────────────────────
    budget_min: int = Field(ge=0)
    budget_max: int = Field(ge=0)
    available_start: date | None = None
    available_end: date | None = None
    vibes: list[VibeEnum] = Field(default_factory=list, max_length=8)
    climate_pref: ClimateEnum = ClimateEnum.any
    activity_level: ActivityLevelEnum = ActivityLevelEnum.moderate
    excluded_destinations: list[str] = Field(default_factory=list, max_length=20)
    already_visited: list[str] = Field(default_factory=list, max_length=20)

    # ── Logistics Constraint Fields ───────────────────────────────────────────
    activity_intensity: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description=(
            "Physical intensity tolerance: "
            "1=Slow/Accessible, 2=Easy, 3=Moderate, 4=Active, 5=High Adventure"
        ),
    )
    mandatory_amenities: list[AmenityEnum] = Field(
        default_factory=list,
        max_length=9,
        description="Amenities the destination must provide for this participant",
    )
    transit_preferences: list[TransitModeEnum] = Field(
        default_factory=list,
        max_length=5,
        description="Ordered list of preferred transit modes",
    )
    immovable_events: list[ImmovableEvent] = Field(
        default_factory=list,
        max_length=10,
        description="Fixed schedule events the trip must plan around",
    )

    # ── Validators ────────────────────────────────────────────────────────────

    @model_validator(mode="after")
    def budget_max_gte_min(self) -> "SurveySubmit":
        if self.budget_max < self.budget_min:
            raise ValueError("budget_max must be greater than or equal to budget_min")
        return self

    @model_validator(mode="after")
    def end_after_start(self) -> "SurveySubmit":
        if self.available_start and self.available_end:
            if self.available_end < self.available_start:
                raise ValueError("available_end must be on or after available_start")
        return self

    @field_validator("excluded_destinations", "already_visited", mode="before")
    @classmethod
    def strip_and_deduplicate(cls, v: list) -> list:
        seen = set()
        result = []
        for item in v:
            cleaned = str(item).strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                result.append(cleaned)
        return result
