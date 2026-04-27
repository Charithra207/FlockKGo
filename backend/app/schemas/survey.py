from datetime import date

from pydantic import BaseModel, Field


class SurveySubmit(BaseModel):
    budget_min: int = Field(ge=0)
    budget_max: int = Field(ge=0)
    available_start: date | None = None
    available_end: date | None = None
    vibes: list[str] = Field(default_factory=list)
    climate_pref: str = "any"
    activity_level: str = "moderate"
    excluded_destinations: list[str] = Field(default_factory=list)
    already_visited: list[str] = Field(default_factory=list)
