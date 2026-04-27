import uuid

from pydantic import BaseModel


class RecommendationOut(BaseModel):
    id: uuid.UUID
    destination_name: str
    why_recommended: str | None = None
    estimated_budget_range: str | None = None
    best_activities: list[str]
    ml_score: float | None = None
    rank: int | None = None
    llm_model_used: str | None = None

    model_config = {"from_attributes": True}
