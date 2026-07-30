"""
budget.py — Pydantic schemas for the budget optimization endpoints.
"""

from typing import Optional

from pydantic import BaseModel, Field


class CategoryConstraint(BaseModel):
    """A per-person cap on a specific spending category."""
    category: str = Field(
        description="One of: flights, accommodation, food, activities, transport, misc"
    )
    max: int = Field(ge=0, description="Maximum USD this person can spend on this category")


class ParticipantConstraint(BaseModel):
    """Optional per-person category constraints submitted by the organiser."""
    participant_id: str
    category_constraints: list[CategoryConstraint] = Field(default_factory=list)


class BudgetPlanRequest(BaseModel):
    """
    Optional request body for POST /trips/{id}/budget-plan.
    If omitted, the optimizer runs with just the survey budget data and
    sacrifice scores pulled automatically from the latest ML run.
    """
    participant_constraints: list[ParticipantConstraint] = Field(
        default_factory=list,
        description="Optional per-person category caps",
    )


class CategoryAllocationOut(BaseModel):
    category: str
    amount_usd: float
    proportion: float


class ParticipantPlanOut(BaseModel):
    participant_id: str
    name: str
    total_spend: float
    budget_min: int
    budget_max: int
    budget_utilisation: float
    # Anti-Dictator fields
    adjusted_target: float = Field(
        default=0.75,
        description="Personalised LP target: BASE_TARGET - ISS × MAX_SUBSIDY",
    )
    sacrifice_score: float = Field(
        default=0.0,
        description="Individual Sacrifice Score [0.0–1.0] from the ML pipeline",
    )
    category_breakdown: list[CategoryAllocationOut]
    is_at_minimum: bool
    is_at_maximum: bool
    note: Optional[str] = None


class BudgetPlanOut(BaseModel):
    trip_id: str
    status: str
    group_total: float
    group_average: float
    min_spend: float
    max_spend: float
    avg_utilisation: float
    fairness_score: float
    # Anti-Dictator: True when at least one participant received a sacrifice adjustment
    sacrifice_applied: bool = False
    solver_message: str
    participants: list[ParticipantPlanOut]
    categories: list[str]
    interpretation: str
    # Populated on GET (read from DB record timestamp)
    computed_at: Optional[str] = None
