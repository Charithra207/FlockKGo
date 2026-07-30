"""
budget_optimizer.py — Anti-Dictator group budget optimizer.

OVERVIEW
--------
Standard LP: minimise variance in budget utilisation across all participants.

ANTI-DICTATOR EXTENSION
-----------------------
The standard LP uses a hardcoded 75% utilisation target for everyone.
This is unfair when participants had different levels of say in the destination
chosen. Someone who loved Bali and got Bali should contribute fully; someone
who wanted Shimla and ended up in Bali "sacrificed" more.

The Anti-Dictator extension reads each participant's Individual Sacrifice Score
(ISS, computed in scoring.py) and lowers their personal spending target
proportionally:

    target_i = BASE_TARGET - ISS_i * MAX_SUBSIDY

Where:
    BASE_TARGET  = 0.75  (everyone pays 75% of their max budget by default)
    MAX_SUBSIDY  = 0.25  (a participant with ISS=1.0 pays as low as 50%)

This means participants who compromised heavily on destination are given a
lower budget utilisation target — effectively the group pool absorbs their
flex costs (room splits, shared transport, activity tickets) rather than
billing them individually.

The LP solver still minimises the sum of per-person deviations from their
individual targets, so the math remains fair and optimal — it just uses
personalised targets instead of a uniform one.

CATEGORIES
----------
  flights, accommodation, food, activities, transport, misc
  Default proportions sum to 1.0. Per-category caps are respected as hard
  upper bounds on the implied spend for that category.

FAIRNESS SCORE
--------------
  fairness = max(0.0, 1.0 - variance(utilisation_i) * 10)

  Higher is better. Note: after applying sacrifice adjustments, utilisation
  variance will naturally increase slightly (different targets), so the
  fairness score reflects raw utilisation spread, not sacrifice-adjusted spread.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

try:
    import pulp
    PULP_AVAILABLE = True
except ImportError:
    PULP_AVAILABLE = False


# ── Constants ─────────────────────────────────────────────────────────────────

CATEGORIES = ["flights", "accommodation", "food", "activities", "transport", "misc"]

DEFAULT_CATEGORY_PROPORTIONS: dict[str, float] = {
    "flights":       0.35,
    "accommodation": 0.30,
    "food":          0.15,
    "activities":    0.12,
    "transport":     0.05,
    "misc":          0.03,
}

# Base spending target: everyone aims for 75% of their max budget by default.
BASE_TARGET = 0.75

# Maximum sacrifice subsidy: a participant with ISS=1.0 gets their target
# reduced by up to 25 percentage points (from 75% down to 50%).
MAX_SUBSIDY = 0.25

# Threshold above which a participant is considered a "high sacrifice" case.
HIGH_SACRIFICE_THRESHOLD = 0.50


# ── Input / output types ──────────────────────────────────────────────────────

@dataclass
class ParticipantBudget:
    participant_id: str
    name: str
    budget_min: int          # USD, absolute minimum contribution
    budget_max: int          # USD, absolute maximum contribution
    # Optional per-category hard caps e.g. [{"category": "flights", "max": 400}]
    category_constraints: list[dict] = field(default_factory=list)
    # Anti-Dictator: Individual Sacrifice Score [0.0, 1.0], default 0.0 (no sacrifice)
    sacrifice_score: float = 0.0


@dataclass
class CategoryAllocation:
    category: str
    amount_usd: float
    proportion: float        # fraction of total spend


@dataclass
class ParticipantPlan:
    participant_id: str
    name: str
    total_spend: float
    budget_min: int
    budget_max: int
    budget_utilisation: float    # total_spend / budget_max
    adjusted_target: float       # personalised utilisation target used in LP
    sacrifice_score: float       # ISS that drove the target adjustment
    category_breakdown: list[CategoryAllocation]
    is_at_minimum: bool
    is_at_maximum: bool


@dataclass
class BudgetPlan:
    status: str                  # "optimal" | "feasible" | "infeasible" | "fallback"
    group_total: float
    group_average: float
    min_spend: float
    max_spend: float
    avg_utilisation: float       # average fraction of max budget used
    fairness_score: float        # 0–1, higher = more equal utilisation
    sacrifice_applied: bool      # True if at least one ISS > 0 was used
    participants: list[ParticipantPlan]
    solver_message: str


# ── Target calculation — the Anti-Dictator formula ───────────────────────────

def compute_adjusted_target(sacrifice_score: float) -> float:
    """
    Compute the personalised budget utilisation target for one participant.

    Formula:
        target = BASE_TARGET - sacrifice_score × MAX_SUBSIDY
               = 0.75 - ISS × 0.25

    Clipped to [0.40, 0.75] so no participant pays less than 40% of their
    maximum budget (prevents degenerate LP solutions) and no one exceeds the
    standard 75% ceiling (prevents unfairly over-charging low-sacrifice participants).

    Examples:
        ISS = 0.00  →  target = 0.75  (no sacrifice, pay full standard rate)
        ISS = 0.40  →  target = 0.65  (moderate sacrifice, 10% relief)
        ISS = 0.80  →  target = 0.55  (high sacrifice, 20% relief)
        ISS = 1.00  →  target = 0.50  (maximum sacrifice, 25% relief)
    """
    raw = BASE_TARGET - float(sacrifice_score) * MAX_SUBSIDY
    return round(max(0.40, min(BASE_TARGET, raw)), 4)


# ── Core LP solver ────────────────────────────────────────────────────────────

def solve_group_budget(participants: list[ParticipantBudget]) -> BudgetPlan:
    """
    Solve the group budget allocation problem with Anti-Dictator sacrifice adjustments.

    The LP minimises the sum of absolute deviations from each participant's
    personalised utilisation target.  Participants with higher ISS receive a
    lower target — meaning the solver accepts (and even prefers) lower spending
    for them without penalising the objective.

    Falls back to proportional allocation if PuLP is unavailable or the LP
    is infeasible (e.g. conflicting per-category caps).
    """
    if not PULP_AVAILABLE:
        return _fallback_proportional(participants, reason="PuLP not installed")

    if not participants:
        return BudgetPlan(
            status="infeasible", group_total=0, group_average=0,
            min_spend=0, max_spend=0, avg_utilisation=0, fairness_score=0,
            sacrifice_applied=False, participants=[], solver_message="No participants provided",
        )

    n = len(participants)
    sacrifice_applied = any(p.sacrifice_score > 0.0 for p in participants)

    # ── Build LP problem ──────────────────────────────────────────────────────
    prob = pulp.LpProblem("antidictator_group_budget", pulp.LpMinimize)

    # Decision variables: spend_i ∈ [budget_min_i, budget_max_i]
    spend = {
        p.participant_id: pulp.LpVariable(
            f"spend_{i}",
            lowBound=float(p.budget_min),
            upBound=float(p.budget_max),
        )
        for i, p in enumerate(participants)
    }

    # Slack variables for absolute deviation from each participant's target
    deviation = {
        p.participant_id: pulp.LpVariable(f"dev_{i}", lowBound=0)
        for i, p in enumerate(participants)
    }

    # ── Objective: minimise sum of per-person deviations from adjusted targets
    prob += pulp.lpSum(deviation[p.participant_id] for p in participants)

    # ── Constraints ───────────────────────────────────────────────────────────
    for p in participants:
        pid = p.participant_id
        bmax = float(p.budget_max)

        # Personalised target: lower for high-sacrifice participants
        target = compute_adjusted_target(p.sacrifice_score)

        # Absolute-value linearisation:
        #   |spend_i / bmax - target| ≤ deviation_i
        # Rewritten as two linear inequalities:
        #   spend_i - target × bmax ≤ deviation_i × bmax
        #   target × bmax - spend_i ≤ deviation_i × bmax
        prob += spend[pid] - target * bmax <= deviation[pid] * bmax
        prob += target * bmax - spend[pid] <= deviation[pid] * bmax

        # Per-category hard caps
        for constraint in (p.category_constraints or []):
            cat = constraint.get("category", "").lower()
            cat_max = constraint.get("max")
            if cat in CATEGORIES and cat_max is not None:
                proportion = DEFAULT_CATEGORY_PROPORTIONS.get(cat, 0.1)
                # spend_i × proportion ≤ cat_max
                prob += spend[pid] * proportion <= float(cat_max)

    # ── Solve ─────────────────────────────────────────────────────────────────
    solver = pulp.PULP_CBC_CMD(msg=0)
    prob.solve(solver)
    status_str = pulp.LpStatus[prob.status]

    if prob.status == -1:
        return _fallback_proportional(participants, reason="LP infeasible — constraints conflict")

    # ── Extract solution ──────────────────────────────────────────────────────
    participant_plans: list[ParticipantPlan] = []
    total_spend = 0.0

    for p in participants:
        pid = p.participant_id
        raw_spend = pulp.value(spend[pid])
        if raw_spend is None:
            raw_spend = float(p.budget_min)

        actual_spend = round(
            max(float(p.budget_min), min(float(p.budget_max), raw_spend)), 2
        )
        utilisation = actual_spend / float(p.budget_max) if p.budget_max > 0 else 0.0
        total_spend += actual_spend

        category_breakdown = _build_category_breakdown(actual_spend, p.category_constraints)

        participant_plans.append(ParticipantPlan(
            participant_id=pid,
            name=p.name,
            total_spend=actual_spend,
            budget_min=p.budget_min,
            budget_max=p.budget_max,
            budget_utilisation=round(utilisation, 3),
            adjusted_target=compute_adjusted_target(p.sacrifice_score),
            sacrifice_score=round(p.sacrifice_score, 4),
            category_breakdown=category_breakdown,
            is_at_minimum=abs(actual_spend - p.budget_min) < 1.0,
            is_at_maximum=abs(actual_spend - p.budget_max) < 1.0,
        ))

    utilisations = [pp.budget_utilisation for pp in participant_plans]
    avg_util = sum(utilisations) / len(utilisations) if utilisations else 0.0
    variance = (
        sum((u - avg_util) ** 2 for u in utilisations) / len(utilisations)
        if utilisations else 0.0
    )
    fairness = max(0.0, 1.0 - variance * 10)

    return BudgetPlan(
        status="optimal" if prob.status == 1 else "feasible",
        group_total=round(total_spend, 2),
        group_average=round(total_spend / n, 2),
        min_spend=round(min(pp.total_spend for pp in participant_plans), 2),
        max_spend=round(max(pp.total_spend for pp in participant_plans), 2),
        avg_utilisation=round(avg_util, 3),
        fairness_score=round(fairness, 3),
        sacrifice_applied=sacrifice_applied,
        participants=participant_plans,
        solver_message=f"LP status: {status_str}",
    )


# ── Category breakdown ────────────────────────────────────────────────────────

def _build_category_breakdown(
    total_spend: float,
    constraints: list[dict],
) -> list[CategoryAllocation]:
    """
    Allocate total_spend across categories using default proportions,
    respecting any per-category hard caps.  Excess is redistributed to misc.
    """
    allocations = {
        cat: total_spend * prop
        for cat, prop in DEFAULT_CATEGORY_PROPORTIONS.items()
    }

    excess = 0.0
    for constraint in (constraints or []):
        cat = constraint.get("category", "").lower()
        cap = constraint.get("max")
        if cat in allocations and cap is not None:
            if allocations[cat] > float(cap):
                excess += allocations[cat] - float(cap)
                allocations[cat] = float(cap)

    allocations["misc"] = allocations.get("misc", 0.0) + excess

    return [
        CategoryAllocation(
            category=cat,
            amount_usd=round(allocations[cat], 2),
            proportion=round(allocations[cat] / total_spend, 3) if total_spend > 0 else 0.0,
        )
        for cat in CATEGORIES
    ]


# ── Proportional fallback ─────────────────────────────────────────────────────

def _fallback_proportional(
    participants: list[ParticipantBudget],
    reason: str,
) -> BudgetPlan:
    """
    Fallback when PuLP is unavailable or LP is infeasible.

    Each participant spends their personalised target fraction of their max
    budget, clamped to their [min, max] range.  Sacrifice adjustments still
    apply so the Anti-Dictator property is preserved even in fallback mode.
    """
    participant_plans: list[ParticipantPlan] = []
    total = 0.0

    for p in participants:
        target = compute_adjusted_target(p.sacrifice_score)
        raw_spend = float(p.budget_max) * target
        actual_spend = round(max(float(p.budget_min), raw_spend), 2)
        total += actual_spend
        participant_plans.append(ParticipantPlan(
            participant_id=p.participant_id,
            name=p.name,
            total_spend=actual_spend,
            budget_min=p.budget_min,
            budget_max=p.budget_max,
            budget_utilisation=round(actual_spend / p.budget_max, 3) if p.budget_max > 0 else 0.0,
            adjusted_target=target,
            sacrifice_score=round(p.sacrifice_score, 4),
            category_breakdown=_build_category_breakdown(actual_spend, p.category_constraints),
            is_at_minimum=False,
            is_at_maximum=False,
        ))

    n = len(participants)
    utilisations = [pp.budget_utilisation for pp in participant_plans]
    avg_util = sum(utilisations) / len(utilisations) if utilisations else 0.0
    variance = (
        sum((u - avg_util) ** 2 for u in utilisations) / len(utilisations)
        if utilisations else 0.0
    )
    fairness = max(0.0, 1.0 - variance * 10)

    return BudgetPlan(
        status="fallback",
        group_total=round(total, 2),
        group_average=round(total / n, 2) if n else 0.0,
        min_spend=round(min(pp.total_spend for pp in participant_plans), 2) if participant_plans else 0.0,
        max_spend=round(max(pp.total_spend for pp in participant_plans), 2) if participant_plans else 0.0,
        avg_utilisation=round(avg_util, 3),
        fairness_score=round(fairness, 3),
        sacrifice_applied=any(p.sacrifice_score > 0.0 for p in participants),
        participants=participant_plans,
        solver_message=f"Fallback mode: {reason}",
    )
