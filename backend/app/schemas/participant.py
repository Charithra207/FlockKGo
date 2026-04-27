import uuid

from pydantic import BaseModel, EmailStr


class ParticipantCreate(BaseModel):
    name: str
    email: EmailStr | None = None
    phone: str | None = None


class ParticipantOut(BaseModel):
    id: uuid.UUID
    name: str
    email: EmailStr | None = None
    phone: str | None = None
    survey_token: str

    model_config = {"from_attributes": True}
