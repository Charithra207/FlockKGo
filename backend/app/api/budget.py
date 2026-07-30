"""
budget.py — Group budget optimization endpoints.

POST /trips/{id}/budget-plan
  Runs the Anti-Dictator LP optimizer.
  Reads Individual Sacrifice Scores from the latest MLRunResult to apply
  personalised budget targets.  Persists the full plan to the budget_plans table.

GET  /trips/{id}/budget-plan
  Reads the persisted plan directly from the DB — no LP re-run on every load.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.ml.budget_optimizer import (
    BudgetPlan,
    HIGH_SACRIFICE_THRESHOLD,
    ParticipantBudget,
    solve_group_budget,
    CATEGORIES,
)
from app.models.budget_plan import BudgetPlanRecord
from app.models.ml_result import MLRunResult
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


def _participant_note(pp) -> str | None:
    """Generate a human-readable note for one participant's plan."""
    parts: list[str] = []

    if pp.sacrifice_score > HIGH_SACRIFICE_THRESHOLD:
        parts.append(
            f"Anti-Dictator relief applied (sacrifice score {pp.sacrifice_score:.2f}) "
            f"— target reduced from {int(0.75 * 100)}% to {int(pp.adjusted_target * 100)}% "
            "of max budget."
        )

    if pp.is_at_minimum:
        parts.append("At budget floor — this is the minimum they can contribute.")
    elif pp.is_at_maximum:
        parts.append("At budget ceiling — fully stretched.")
    elif pp.budget_utilisation >= 0.9:
        parts.append("Near maximum budget — limited flexibility.")
    elif pp.budget_utilisation <= 0.55:
        parts.append("Well within budget — has spending headroom.")

    return "  ".join(parts) if parts else None


def _build_plan_out(
    trip_id: str,
    plan: BudgetPlan,
    sacrifice_scores: dict[str, float],
) -> BudgetPlanOut:
    """Convert internal BudgetPlan dataclass to the Pydantic response model."""
    enriched = []
    for pp in plan.participants:
        enriched.append(ParticipantPlanOut(
            participant_id=pp.participant_id,
            name=pp.name,
            total_spend=pp.total_spend,
            budget_min=pp.budget_min,
            budget_max=pp.budget_max,
            budget_utilisation=pp.budget_utilisation,
            adjusted_target=pp.adjusted_target,
            sacrifice_score=pp.sacrifice_score,
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
            note=_participant_note(pp),
        ))

    return BudgetPlanOut(
        trip_id=trip_id,
        status=plan.status,
        group_total=plan.group_total,
        group_average=plan.group_average,
        min_spend=plan.min_spend,
        max_spend=plan.max_spend,
        avg_utilisation=plan.avg_utilisation,
        fairness_score=plan.fairness_score,
        sacrifice_applied=plan.sacrifice_applied,
        solver_message=plan.solver_message,
        participants=enriched,
        categories=CATEGORIES,
        interpretation=_fairness_interpretation(plan.fairness_score),
    )


def _constraint_map(
    participant_constraints: list[ParticipantConstraint],
) -> dict[str, list[dict]]:
    return {
        pc.participant_id: [c.model_dump() for c in pc.category_constraints]
        for pc in participant_constraints
    }


# ── POST /trips/{id}/budget-plan ─────────────────────────────────────────────

@router.post("/trips/{trip_id}/budget-plan")
@limiter.limit("10/minute")
def compute_budget_plan(
    request: Request,
    trip_id: uuid.UUID,
    payload: BudgetPlanRequest = None,
    db: Session = Depends(get_db),
):
    """
    Compute and persist an optimized Anti-Dictator group budget plan.

    Reads the latest MLRunResult to obtain Individual Sacrifice Scores.
    If no ML run has been performed yet, sacrifice scores default to 0.0
    (standard 75% target for everyone).

    The full plan is stored in the budget_plans table and returned in the response.
    Subsequent GET calls read from the DB — no LP re-run.
    """
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    responses = (
        db.query(SurveyResponse)
        .filter(SurveyResponse.trip_id == trip_id)
        .all()
    )
    if not responses:
        raise HTTPException(
            status_code=400,
            detail="No survey responses found — participants must submit surveys first",
        )

    # Load participant names
    participants = db.query(Participant).filter(Participant.trip_id == trip_id).all()
    id_to_name = {str(p.id): p.name for p in participants}

    # ── Read sacrifice scores from the latest ML run ─────────────────────────
    ml_run = (
        db.query(MLRunResult)
        .filter(MLRunResult.trip_id == trip_id)
        .order_by(MLRunResult.ran_at.desc())
        .first()
    )
    sacrifice_scores: dict[str, float] = {}
    if ml_run and ml_run.sacrifice_scores:
        sacrifice_scores = {str(k): float(v) for k, v in ml_run.sacrifice_scores.items()}

    # ── Build constraint map ──────────────────────────────────────────────────
    constraints: dict[str, list[dict]] = {}
    if payload and payload.participant_constraints:
        constraints = _constraint_map(payload.participant_constraints)

    # ── Build optimizer inputs ────────────────────────────────────────────────
    optimizer_inputs: list[ParticipantBudget] = []
    for r in responses:
        pid = str(r.participant_id)
        optimizer_inputs.append(ParticipantBudget(
            participant_id=pid,
            name=id_to_name.get(pid, "Unknown"),
            budget_min=r.budget_min,
            budget_max=r.budget_max,
            category_constraints=constraints.get(pid, []),
            sacrifice_score=sacrifice_scores.get(pid, 0.0),
        ))

    # ── Run LP optimizer ──────────────────────────────────────────────────────
    plan = solve_group_budget(optimizer_inputs)
    budget_optimizer_calls_total.labels(status=plan.status).inc()

    # ── Serialize participants for JSON storage ───────────────────────────────
    participants_json = [
        {
            "participant_id": pp.participant_id,
            "name": pp.name,
            "total_spend": pp.total_spend,
            "budget_min": pp.budget_min,
            "budget_max": pp.budget_max,
            "budget_utilisation": pp.budget_utilisation,
            "adjusted_target": pp.adjusted_target,
            "sacrifice_score": pp.sacrifice_score,
            "category_breakdown": [
                {
                    "category": c.category,
                    "amount_usd": c.amount_usd,
                    "proportion": c.proportion,
                }
                for c in pp.category_breakdown
            ],
            "is_at_minimum": pp.is_at_minimum,
            "is_at_maximum": pp.is_at_maximum,
        }
        for pp in plan.participants
    ]

    # ── Upsert: delete previous plan for this trip, insert new ───────────────
    try:
        db.query(BudgetPlanRecord).filter(
            BudgetPlanRecord.trip_id == trip_id
        ).delete(synchronize_session=False)

        record = BudgetPlanRecord(
            trip_id=trip_id,
            status=plan.status,
            group_total=plan.group_total,
            group_average=plan.group_average,
            min_spend=plan.min_spend,
            max_spend=plan.max_spend,
            avg_utilisation=plan.avg_utilisation,
            fairness_score=plan.fairness_score,
            solver_message=plan.solver_message[:200] if plan.solver_message else None,
            participants_json=participants_json,
            sacrifice_scores_json=sacrifice_scores,
        )
        db.add(record)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to persist budget plan")

    return _build_plan_out(str(trip_id), plan, sacrifice_scores)


# ── GET /trips/{id}/budget-plan ───────────────────────────────────────────────

@router.get("/trips/{trip_id}/budget-plan")
@limiter.limit("60/minute")
def get_budget_plan(
    request: Request,
    trip_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Return the most recently persisted budget plan for a trip.

    Reads directly from the budget_plans table — the LP does NOT re-run.
    Call POST /trips/{id}/budget-plan to generate or refresh the plan.
    """
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    record = (
        db.query(BudgetPlanRecord)
        .filter(BudgetPlanRecord.trip_id == trip_id)
        .order_by(BudgetPlanRecord.computed_at.desc())
        .first()
    )
    if not record:
        raise HTTPException(
            status_code=404,
            detail="No budget plan found — call POST /trips/{id}/budget-plan first",
        )

    # Reconstruct Pydantic response from stored JSON
    from app.schemas.budget import CategoryAllocationOut, ParticipantPlanOut

    participants_out: list[ParticipantPlanOut] = []
    for pp in (record.participants_json or []):
        participants_out.append(ParticipantPlanOut(
            participant_id=pp["participant_id"],
            name=pp["name"],
            total_spend=pp["total_spend"],
            budget_min=pp["budget_min"],
            budget_max=pp["budget_max"],
            budget_utilisation=pp["budget_utilisation"],
            adjusted_target=pp.get("adjusted_target", 0.75),
            sacrifice_score=pp.get("sacrifice_score", 0.0),
            category_breakdown=[
                CategoryAllocationOut(**c)
                for c in pp.get("category_breakdown", [])
            ],
            is_at_minimum=pp.get("is_at_minimum", False),
            is_at_maximum=pp.get("is_at_maximum", False),
            note=_participant_note(
                # Build a minimal namespace object so _participant_note works
                type("_P", (), {
                    "sacrifice_score": pp.get("sacrifice_score", 0.0),
                    "adjusted_target": pp.get("adjusted_target", 0.75),
                    "is_at_minimum": pp.get("is_at_minimum", False),
                    "is_at_maximum": pp.get("is_at_maximum", False),
                    "budget_utilisation": pp.get("budget_utilisation", 0.0),
                })(),
            ),
        ))

    return BudgetPlanOut(
        trip_id=str(trip_id),
        status=record.status,
        group_total=record.group_total,
        group_average=record.group_average,
        min_spend=record.min_spend,
        max_spend=record.max_spend,
        avg_utilisation=record.avg_utilisation,
        fairness_score=record.fairness_score,
        sacrifice_applied=bool(record.sacrifice_scores_json),
        solver_message=record.solver_message or "",
        participants=participants_out,
        categories=CATEGORIES,
        interpretation=_fairness_interpretation(record.fairness_score),
        computed_at=record.computed_at.isoformat(),
    )
