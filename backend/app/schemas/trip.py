import uuid
from typing import Any

from pydantic import BaseModel, EmailStr


class TripCreate(BaseModel):
    name: str
    organizer_name: str
    organizer_email: EmailStr
    trip_month: str | None = None
    duration_days: int | None = None


class TripOut(BaseModel):
    id: uuid.UUID
    organizer_name: str
    organizer_email: EmailStr
    name: str
    status: str
    trip_month: str | None = None
    duration_days: int | None = None
    settings: dict[str, Any]

    model_config = {"from_attributes": True}
