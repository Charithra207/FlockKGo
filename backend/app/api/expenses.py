"""
expenses.py — Financial Guide & Checker endpoints.

All routes require X-API-Key authentication.

Endpoints:
  POST   /trips/{id}/expenses              — log a new expense (with auto-splits)
  GET    /trips/{id}/expenses              — list all expenses
  DELETE /trips/{id}/expenses/{exp_id}     — remove an expense
  GET    /trips/{id}/expenses/settlement   — compute Splitwise-style debt settlement
  GET    /trips/{id}/expenses/budget-health  — compare actual spend vs optimised plan

Split logic:
  By default a new expense is split equally among ALL trip participants.
  The request body can pass a custom `splits` list to do unequal splits.
  The sum of all split amounts must equal the total `amount_inr`.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from slowapi import Limiter
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models.budget_plan import BudgetPlanRecord
from app.models.expense import Expense, ExpenseSplit
from app.models.participant import Participant
from app.models.trip import Trip
from app.services.auth import get_current_api_key
from app.services.debt_settlement import compute_settlements

limiter = Limiter(key_func=lambda request: request.client.host if request.client else "unknown")
router = APIRouter(tags=["expenses"])

# INR exchange rate used for budget health comparison (approximate)
_USD_TO_INR = 83.5


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class SplitInput(BaseModel):
    participant_id: str
    share_amount_inr: int = Field(ge=0)


class AddExpenseRequest(BaseModel):
    paid_by_participant_id: str
    description: str = Field(min_length=1, max_length=300)
    amount_inr: int = Field(gt=0)
    category: str = Field(default="misc", max_length=50)
    receipt_note: Optional[str] = Field(default=None, max_length=500)
    paid_at: Optional[str] = None          # ISO datetime string
    splits: list[SplitInput] = Field(
        default_factory=list,
        description="Custom split amounts. If empty, auto-split equally among all participants.",
    )

    @model_validator(mode="after")
    def validate_splits(self) -> "AddExpenseRequest":
        if self.splits:
            total = sum(s.share_amount_inr for s in self.splits)
            if total != self.amount_inr:
                raise ValueError(
                    f"Sum of splits ({total} INR) must equal expense amount ({self.amount_inr} INR)"
                )
        return self


# ── Helpers ────────────────────────────────────────────────────────────────────

def _expense_to_dict(exp: Expense, splits: list[ExpenseSplit]) -> dict:
    return {
        "id": str(exp.id),
        "trip_id": str(exp.trip_id),
        "paid_by_participant_id": str(exp.paid_by_participant_id),
        "description": exp.description,
        "amount_inr": exp.amount_inr,
        "category": exp.category,
        "receipt_note": exp.receipt_note,
        "paid_at": exp.paid_at.isoformat() if exp.paid_at else None,
        "created_at": exp.created_at.isoformat(),
        "splits": [
            {
                "id": str(s.id),
                "participant_id": str(s.participant_id),
                "share_amount_inr": s.share_amount_inr,
                "is_settled": bool(s.is_settled),
            }
            for s in splits
        ],
    }


# ── POST /trips/{id}/expenses ─────────────────────────────────────────────────

@router.post("/trips/{trip_id}/expenses")
@limiter.limit("30/minute")
def add_expense(
    request: Request,
    trip_id: uuid.UUID,
    payload: AddExpenseRequest,
    db: Session = Depends(get_db),
    _api_key=Depends(get_current_api_key),
):
    """
    Log a new expense. Creates an Expense row and ExpenseSplit rows.

    If `splits` is empty, auto-divides equally among all trip participants
    (rounding remainder to the payer).
    """
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    # Validate payer
    try:
        payer_id = uuid.UUID(payload.paid_by_participant_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid payer participant UUID")
    payer = db.query(Participant).filter(
        Participant.id == payer_id, Participant.trip_id == trip_id
    ).first()
    if not payer:
        raise HTTPException(status_code=404, detail="Payer participant not found in this trip")

    # Parse optional paid_at
    paid_at_dt = None
    if payload.paid_at:
        try:
            from datetime import datetime
            paid_at_dt = datetime.fromisoformat(payload.paid_at)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid paid_at datetime format (use ISO 8601)")

    # Create expense row
    expense = Expense(
        trip_id=trip_id,
        paid_by_participant_id=payer_id,
        description=payload.description,
        amount_inr=payload.amount_inr,
        category=payload.category,
        receipt_note=payload.receipt_note,
        paid_at=paid_at_dt,
    )
    db.add(expense)
    db.flush()   # get expense.id before creating splits

    # Build splits
    participants = db.query(Participant).filter(Participant.trip_id == trip_id).all()
    split_rows: list[ExpenseSplit] = []

    if payload.splits:
        for s in payload.splits:
            try:
                spid = uuid.UUID(s.participant_id)
            except ValueError:
                db.rollback()
                raise HTTPException(status_code=422, detail=f"Invalid participant UUID in splits: {s.participant_id}")
            split_rows.append(ExpenseSplit(
                expense_id=expense.id,
                trip_id=trip_id,
                participant_id=spid,
                share_amount_inr=s.share_amount_inr,
                is_settled=1 if str(spid) == str(payer_id) else 0,
            ))
    else:
        # Auto equal split
        n = len(participants)
        if n == 0:
            db.rollback()
            raise HTTPException(status_code=400, detail="No participants found for this trip")
        base_share = payload.amount_inr // n
        remainder = payload.amount_inr - base_share * n
        for i, p in enumerate(participants):
            share = base_share + (remainder if i == 0 else 0)   # payer gets remainder
            split_rows.append(ExpenseSplit(
                expense_id=expense.id,
                trip_id=trip_id,
                participant_id=p.id,
                share_amount_inr=share,
                is_settled=1 if p.id == payer_id else 0,
            ))

    db.add_all(split_rows)
    db.commit()
    db.refresh(expense)

    return _expense_to_dict(expense, split_rows)


# ── GET /trips/{id}/expenses ──────────────────────────────────────────────────

@router.get("/trips/{trip_id}/expenses")
@limiter.limit("60/minute")
def list_expenses(
    request: Request,
    trip_id: uuid.UUID,
    db: Session = Depends(get_db),
    _api_key=Depends(get_current_api_key),
):
    """List all expenses for a trip with their splits."""
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    expenses = (
        db.query(Expense)
        .filter(Expense.trip_id == trip_id)
        .order_by(Expense.created_at.desc())
        .all()
    )

    # Load all splits for these expenses in one query
    exp_ids = [e.id for e in expenses]
    all_splits = (
        db.query(ExpenseSplit)
        .filter(ExpenseSplit.expense_id.in_(exp_ids))
        .all()
    ) if exp_ids else []

    splits_by_exp: dict[str, list[ExpenseSplit]] = {}
    for s in all_splits:
        splits_by_exp.setdefault(str(s.expense_id), []).append(s)

    total_inr = sum(e.amount_inr for e in expenses)

    return {
        "trip_id": str(trip_id),
        "total_spend_inr": total_inr,
        "expense_count": len(expenses),
        "expenses": [
            _expense_to_dict(e, splits_by_exp.get(str(e.id), []))
            for e in expenses
        ],
    }


# ── DELETE /trips/{id}/expenses/{exp_id} ──────────────────────────────────────

@router.delete("/trips/{trip_id}/expenses/{expense_id}")
@limiter.limit("20/minute")
def delete_expense(
    request: Request,
    trip_id: uuid.UUID,
    expense_id: uuid.UUID,
    db: Session = Depends(get_db),
    _api_key=Depends(get_current_api_key),
):
    """Delete an expense and all its splits (cascade)."""
    expense = db.query(Expense).filter(
        Expense.id == expense_id, Expense.trip_id == trip_id
    ).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    db.query(ExpenseSplit).filter(ExpenseSplit.expense_id == expense_id).delete(synchronize_session=False)
    db.delete(expense)
    db.commit()
    return {"deleted": True, "id": str(expense_id)}


# ── GET /trips/{id}/expenses/settlement ───────────────────────────────────────

@router.get("/trips/{trip_id}/expenses/settlement")
@limiter.limit("30/minute")
def get_settlement(
    request: Request,
    trip_id: uuid.UUID,
    db: Session = Depends(get_db),
    _api_key=Depends(get_current_api_key),
):
    """
    Compute Splitwise-style minimal debt settlement plan.

    Returns per-person balances and the minimum transfer transactions
    needed to settle all debts within the group.
    """
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    participants = db.query(Participant).filter(Participant.trip_id == trip_id).all()
    expenses = db.query(Expense).filter(Expense.trip_id == trip_id).all()
    splits = db.query(ExpenseSplit).filter(ExpenseSplit.trip_id == trip_id).all()

    participants_data = [{"id": str(p.id), "name": p.name} for p in participants]
    expenses_data = [{"id": str(e.id), "paid_by_participant_id": str(e.paid_by_participant_id), "amount_inr": e.amount_inr} for e in expenses]
    splits_data = [{"expense_id": str(s.expense_id), "participant_id": str(s.participant_id), "share_amount_inr": s.share_amount_inr, "is_settled": s.is_settled} for s in splits]

    result = compute_settlements(participants_data, expenses_data, splits_data)
    result["trip_id"] = str(trip_id)
    return result


# ── GET /trips/{id}/expenses/budget-health ────────────────────────────────────

@router.get("/trips/{trip_id}/expenses/budget-health")
@limiter.limit("30/minute")
def get_budget_health(
    request: Request,
    trip_id: uuid.UUID,
    db: Session = Depends(get_db),
    _api_key=Depends(get_current_api_key),
):
    """
    Real-time Budget Health report.

    Compares the group's current actual spending (INR) against the
    mathematically optimised Resentment-Prevention budget plan (USD),
    flags categories where the group is over-spending, and provides
    a health score (0–100).

    Notes:
    - The optimised plan is stored in USD (LP optimizer); actual expenses
      are in INR. Conversion uses a fixed rate of 83.5 INR/USD.
    - If no budget plan has been computed, returns a data-only response
      (no comparison, no flags).
    """
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    expenses = db.query(Expense).filter(Expense.trip_id == trip_id).all()
    total_actual_inr = sum(e.amount_inr for e in expenses)
    total_actual_usd = round(total_actual_inr / _USD_TO_INR, 2)

    # Category breakdown of actual spend
    actual_by_cat: dict[str, int] = {}
    for e in expenses:
        actual_by_cat[e.category] = actual_by_cat.get(e.category, 0) + e.amount_inr

    # Load the optimised budget plan
    plan_record = (
        db.query(BudgetPlanRecord)
        .filter(BudgetPlanRecord.trip_id == trip_id)
        .order_by(BudgetPlanRecord.computed_at.desc())
        .first()
    )

    if not plan_record:
        return {
            "trip_id": str(trip_id),
            "total_actual_inr": total_actual_inr,
            "total_actual_usd": total_actual_usd,
            "planned_group_total_usd": None,
            "planned_group_total_inr": None,
            "spend_vs_plan_pct": None,
            "health_score": None,
            "status": "no_plan",
            "message": "No optimised budget plan found. Run POST /trips/{id}/budget-plan first.",
            "actual_by_category_inr": actual_by_cat,
            "flags": [],
        }

    planned_usd = plan_record.group_total
    planned_inr = round(planned_usd * _USD_TO_INR)

    spend_pct = round(total_actual_inr / planned_inr * 100, 1) if planned_inr > 0 else 0.0

    # Per-category comparison using default proportions from budget_optimizer
    category_proportions = {
        "flights": 0.35, "accommodation": 0.30, "food": 0.15,
        "activities": 0.12, "transport": 0.05, "misc": 0.03,
    }

    flags: list[dict] = []
    for cat, proportion in category_proportions.items():
        planned_cat_inr = round(planned_inr * proportion)
        actual_cat_inr = actual_by_cat.get(cat, 0)
        if planned_cat_inr > 0 and actual_cat_inr > planned_cat_inr:
            over_pct = round((actual_cat_inr - planned_cat_inr) / planned_cat_inr * 100, 1)
            flags.append({
                "category": cat,
                "planned_inr": planned_cat_inr,
                "actual_inr": actual_cat_inr,
                "over_by_inr": actual_cat_inr - planned_cat_inr,
                "over_by_pct": over_pct,
                "severity": "critical" if over_pct > 25 else "warning",
            })

    # Health score: 100 = on budget, degrades linearly up to 0 at 150% spend
    health_raw = max(0, min(100, round(100 - max(0, spend_pct - 100) * 2)))

    if spend_pct <= 80:
        health_label = "under_budget"
    elif spend_pct <= 100:
        health_label = "on_track"
    elif spend_pct <= 115:
        health_label = "slightly_over"
    elif spend_pct <= 130:
        health_label = "over_budget"
    else:
        health_label = "critical_overspend"

    return {
        "trip_id": str(trip_id),
        "total_actual_inr": total_actual_inr,
        "total_actual_usd": total_actual_usd,
        "planned_group_total_usd": planned_usd,
        "planned_group_total_inr": planned_inr,
        "spend_vs_plan_pct": spend_pct,
        "health_score": health_raw,
        "status": health_label,
        "flags": flags,
        "actual_by_category_inr": actual_by_cat,
        "plan_computed_at": plan_record.computed_at.isoformat(),
        "exchange_rate_used": f"1 USD = {_USD_TO_INR} INR (fixed approximation)",
    }
