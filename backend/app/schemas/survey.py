from datetime import date
from enum import Enum

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


class SurveySubmit(BaseModel):
    budget_min: int = Field(ge=0)
    budget_max: int = Field(ge=0)
    available_start: date | None = None
    available_end: date | None = None
    vibes: list[VibeEnum] = Field(default_factory=list, max_length=8)
    climate_pref: ClimateEnum = ClimateEnum.any
    activity_level: ActivityLevelEnum = ActivityLevelEnum.moderate
    excluded_destinations: list[str] = Field(default_factory=list, max_length=20)
    already_visited: list[str] = Field(default_factory=list, max_length=20)

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
