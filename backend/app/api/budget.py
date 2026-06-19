"""
budget.py — Group budget optimization endpoint.

POST /trips/{id}/budget-plan
  Runs the LP optimizer against all survey responses for a trip.
  Returns an itemized spending plan per participant, broken down by category.

GET  /trips/{id}/budget-plan
  Returns the most recently computed budget plan (cached in trip settings).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.ml.budget_optimizer import (
    BudgetPlan,
    ParticipantBudget,
    solve_group_budget,
    CATEGORIES,
)
from app.models.participant import Participant
from app.models.survey_response import SurveyResponse
from app.models.trip import Trip
from app.monitoring.metrics import budget_optimizer_calls_total
from app.schemas.budget import (
    BudgetPlanOut,
    BudgetPlanRequest,
    CategoryAllocationOut,
    ParticipantConstraint,
    ParticipantPlanOut,
)

limiter = Limiter(key_func=lambda request: request.client.host if request.client else "unknown")
router = APIRouter(tags=["budget"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fairness_interpretation(score: float) -> str:
    if score >= 0.9:
        return "Excellent — everyone contributes a very similar fraction of their budget."
    if score >= 0.7:
        return "Good — minor variation in budget utilisation across participants."
    if score >= 0.5:
        return "Moderate — some participants will stretch more than others."
    return "Low — budget ranges are very different; consider adjusting expectations."


def _add_participant_notes(plan: BudgetPlan) -> list[ParticipantPlanOut]:
    """Add human-readable notes to each participant's plan."""
    out = []
    for pp in plan.participants:
        note = None
        if pp.is_at_minimum:
            note = "At budget floor — this is the minimum they can contribute."
        elif pp.is_at_maximum:
            note = "At budget ceiling — fully stretched."
        elif pp.budget_utilisation >= 0.9:
            note = "Near maximum budget — limited flexibility."
        elif pp.budget_utilisation <= 0.6:
            note = "Well within budget — has spending headroom."

        out.append(ParticipantPlanOut(
            participant_id=pp.participant_id,
            name=pp.name,
            total_spend=pp.total_spend,
            budget_min=pp.budget_min,
            budget_max=pp.budget_max,
            budget_utilisation=pp.budget_utilisation,
            category_breakdown=[
                CategoryAllocationOut(
                    category=c.category,
                    amount_usd=c.amount_usd,
                    proportion=c.proportion,
                )
                for c in pp.category_breakdown
            ],
            is_at_minimum=pp.is_at_minimum,
            is_at_maximum=pp.is_at_maximum,
            note=note,
        ))
    return out


def _build_constraint_map(
    participant_constraints: list[ParticipantConstraint],
) -> dict[str, list[dict]]:
    return {
        pc.participant_id: [c.model_dump() for c in pc.category_constraints]
        for pc in participant_constraints
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/trips/{trip_id}/budget-plan")
@limiter.limit("10/minute")
def compute_budget_plan(
    request: Request,
    trip_id: uuid.UUID,
    payload: BudgetPlanRequest = None,
    db: Session = Depends(get_db),
):
    """
    Compute an optimized group budget plan using linear programming.

    Reads all survey responses for the trip, runs the LP optimizer,
    and returns a per-person spending plan broken down by category.

    Optional body: per-person category caps, e.g.:
    {
      "participant_constraints": [
        {
          "participant_id": "uuid",
          "category_constraints": [{"category": "flights", "max": 400}]
        }
      ]
    }
    """
    # Validate trip exists and has responses
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    responses = db.query(SurveyResponse).filter(SurveyResponse.trip_id == trip_id).all()
    if not responses:
        raise HTTPException(status_code=400, detail="No survey responses found — participants must submit surveys first")

    # Load participant names
    participants = db.query(Participant).filter(Participant.trip_id == trip_id).all()
    id_to_name = {str(p.id): p.name for p in participants}

    # Build constraint map from request body
    constraint_map: dict[str, list[dict]] = {}
    if payload and payload.participant_constraints:
        constraint_map = _build_constraint_map(payload.participant_constraints)

    # Build optimizer inputs
    optimizer_inputs = []
    for r in responses:
        pid = str(r.participant_id)
        optimizer_inputs.append(ParticipantBudget(
            participant_id=pid,
            name=id_to_name.get(pid, "Unknown"),
            budget_min=r.budget_min,
            budget_max=r.budget_max,
            category_constraints=constraint_map.get(pid, []),
        ))

    # Run LP optimizer
    plan = solve_group_budget(optimizer_inputs)

    # Record metric
    budget_optimizer_calls_total.labels(status=plan.status).inc()

    # Persist plan summary in trip settings for GET retrieval
    try:
        settings = trip.settings or {}
        settings["budget_plan"] = {
            "status": plan.status,
            "group_total": plan.group_total,
            "group_average": plan.group_average,
            "fairness_score": plan.fairness_score,
        }
        trip.settings = settings
        db.commit()
    except Exception:
        db.rollback()

    # Build response
    enriched_participants = _add_participant_notes(plan)

    return BudgetPlanOut(
        trip_id=str(trip_id),
        status=plan.status,
        group_total=plan.group_total,
        group_average=plan.group_average,
        min_spend=plan.min_spend,
        max_spend=plan.max_spend,
        avg_utilisation=plan.avg_utilisation,
        fairness_score=plan.fairness_score,
        solver_message=plan.solver_message,
        participants=enriched_participants,
        categories=CATEGORIES,
        interpretation=_fairness_interpretation(plan.fairness_score),
    )


@router.get("/trips/{trip_id}/budget-plan")
@limiter.limit("60/minute")
def get_budget_plan_summary(
    request: Request,
    trip_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Returns the summary of the last computed budget plan (stored in trip settings).
    Call POST first to generate the full plan.
    """
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    plan = (trip.settings or {}).get("budget_plan")
    if not plan:
        raise HTTPException(
            status_code=404,
            detail="No budget plan found — call POST /trips/{id}/budget-plan first",
        )

    return {"trip_id": str(trip_id), **plan}
