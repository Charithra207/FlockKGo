import uuid

from pydantic import BaseModel, Field


class RankedChoiceItem(BaseModel):
    rank: int = Field(ge=1)
    recommendation_id: uuid.UUID


class VoteCreate(BaseModel):
    participant_id: uuid.UUID
    ranked_choices: list[RankedChoiceItem]
