"""
budget_plan.py — Persisted BudgetPlan model.

Stores the output of solve_group_budget() in the database so the GET
endpoint reads from DB instead of re-running the LP on every page load.
The full per-participant JSON is stored in `participants_json`; the
aggregate fields are stored as typed columns for indexed querying.

One row per trip — POST /budget-plan upserts (deletes previous, inserts fresh).
"""

import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Uuid
from sqlalchemy.sql import func

from app.db.database import Base


class BudgetPlanRecord(Base):
    __tablename__ = "budget_plans"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    trip_id = Column(Uuid, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)

    # LP solver status: "optimal" | "feasible" | "fallback" | "infeasible"
    status = Column(String(20), nullable=False)

    # Aggregate stats — typed columns for fast summary reads
    group_total = Column(Float, nullable=False)
    group_average = Column(Float, nullable=False)
    min_spend = Column(Float, nullable=False)
    max_spend = Column(Float, nullable=False)
    avg_utilisation = Column(Float, nullable=False)
    fairness_score = Column(Float, nullable=False)
    solver_message = Column(String(200), nullable=True)

    # Full per-participant plan stored as JSON (includes category_breakdown)
    participants_json = Column(JSON, nullable=False, default=list)

    # Optional: per-participant sacrifice scores injected after ML run
    # {participant_id: float} — populated by the Anti-Dictator pipeline
    sacrifice_scores_json = Column(JSON, nullable=True, default=dict)

    computed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
