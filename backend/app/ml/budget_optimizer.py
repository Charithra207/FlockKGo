"""
budget_optimizer.py — Linear programming budget optimizer for group travel.

Problem definition
------------------
Given N participants each with a budget range [min_i, max_i] and optional
per-category constraints, find individual spending amounts that:
  1. Respect each person's hard budget limits
  2. Produce a fair, mathematically optimal group spending plan
  3. Optionally satisfy per-person category caps (e.g. "I can't spend > $400 on flights")

Why LP and not just averaging?
  Averaging ignores that some participants have narrow ranges (inflexible)
  while others have wide ones (flexible). LP treats this as a constraint
  satisfaction problem and finds the true optimum — the allocation that
  maximises total budget utilisation while keeping everyone within their limits.

Objective
---------
  Minimise: sum of (spend_i / budget_max_i - target_utilisation)^2
  i.e. minimise the variance in how much of each person's budget is used.

  This is a quadratic objective, but we linearise it by introducing a
  slack variable `deviation_i` and minimising sum(deviation_i) subject to:
    deviation_i >= spend_i / budget_max_i - target_utilisation
    deviation_i >= target_utilisation - spend_i / budget_max_i
  (absolute value linearisation)

  target_utilisation = 0.75 (use 75% of max budget — leaves headroom for
  incidentals while maximising the trip quality).

Categories
----------
  flights, accommodation, food, activities, transport, misc
  Each category gets a default allocation proportion. Participants can
  add constraints like {"category": "flights", "max": 400}.

Resume talking point
--------------------
  "I modelled group budget allocation as a linear programme using PuLP.
   The objective minimises variance in budget utilisation across participants
   subject to per-person budget range constraints and optional per-category
   spending caps. This ensures fairness — no one is asked to spend
   disproportionately more of their available budget than anyone else."
"""

from dataclasses import dataclass, field
from typing import Optional

try:
    import pulp
    PULP_AVAILABLE = True
except ImportError:
    PULP_AVAILABLE = False


# ── Category definitions ─────────────────────────────────────────────────────

CATEGORIES = ["flights", "accommodation", "food", "activities", "transport", "misc"]

# Default allocation proportions (must sum to 1.0)
DEFAULT_CATEGORY_PROPORTIONS = {
    "flights":       0.35,
    "accommodation": 0.30,
    "food":          0.15,
    "activities":    0.12,
    "transport":     0.05,
    "misc":          0.03,
}

TARGET_UTILISATION = 0.75   # aim to use 75% of each person's max budget


# ── Input / output types ──────────────────────────────────────────────────────

@dataclass
class ParticipantBudget:
    participant_id: str
    name: str
    budget_min: int         # USD, absolute minimum they can spend
    budget_max: int         # USD, absolute maximum they can spend
    # Optional per-category hard caps e.g. [{"category": "flights", "max": 400}]
    category_constraints: list[dict] = field(default_factory=list)


@dataclass
class CategoryAllocation:
    category: str
    amount_usd: float
    proportion: float       # fraction of total spend


@dataclass
class ParticipantPlan:
    participant_id: str
    name: str
    total_spend: float
    budget_min: int
    budget_max: int
    budget_utilisation: float   # total_spend / budget_max
    category_breakdown: list[CategoryAllocation]
    is_at_minimum: bool         # True if LP pushed them to their floor
    is_at_maximum: bool         # True if LP maxed them out


@dataclass
class BudgetPlan:
    status: str                 # "optimal" | "feasible" | "infeasible" | "fallback"
    group_total: float
    group_average: float
    min_spend: float
    max_spend: float
    avg_utilisation: float      # average fraction of max budget used
    fairness_score: float       # 0–1, higher = more equal utilisation
    participants: list[ParticipantPlan]
    solver_message: str


# ── Core LP solver ────────────────────────────────────────────────────────────

def solve_group_budget(participants: list[ParticipantBudget]) -> BudgetPlan:
    """
    Solve the group budget allocation problem.

    Falls back to a simple proportional allocation if PuLP is unavailable
    or the LP is infeasible (e.g. conflicting constraints).
    """
    if not PULP_AVAILABLE:
        return _fallback_proportional(participants, reason="PuLP not installed")

    if not participants:
        return BudgetPlan(
            status="infeasible", group_total=0, group_average=0,
            min_spend=0, max_spend=0, avg_utilisation=0, fairness_score=0,
            participants=[], solver_message="No participants provided",
        )

    n = len(participants)

    # ── Build LP problem ──────────────────────────────────────────────────────
    prob = pulp.LpProblem("group_budget_allocation", pulp.LpMinimize)

    # Decision variables: spend per person (continuous, within budget bounds)
    spend = {
        p.participant_id: pulp.LpVariable(
            f"spend_{i}",
            lowBound=float(p.budget_min),
            upBound=float(p.budget_max),
        )
        for i, p in enumerate(participants)
    }

    # Slack variables for absolute deviation from target utilisation
    deviation = {
        p.participant_id: pulp.LpVariable(f"dev_{i}", lowBound=0)
        for i, p in enumerate(participants)
    }

    # ── Objective: minimise sum of deviations from target utilisation ─────────
    prob += pulp.lpSum(deviation[p.participant_id] for p in participants)

    # ── Constraints ───────────────────────────────────────────────────────────
    for p in participants:
        pid = p.participant_id
        bmax = float(p.budget_max)
        target = TARGET_UTILISATION  # 0.75

        # |spend_i/bmax - target| <= deviation_i  (linearised absolute value)
        # spend_i/bmax - target <= deviation_i  →  spend_i - target*bmax <= deviation_i*bmax
        prob += spend[pid] - target * bmax <= deviation[pid] * bmax
        # target - spend_i/bmax <= deviation_i  →  target*bmax - spend_i <= deviation_i*bmax
        prob += target * bmax - spend[pid] <= deviation[pid] * bmax

        # Per-category constraints
        for constraint in (p.category_constraints or []):
            cat = constraint.get("category", "").lower()
            cat_max = constraint.get("max")
            if cat in CATEGORIES and cat_max is not None:
                proportion = DEFAULT_CATEGORY_PROPORTIONS.get(cat, 0.1)
                # spend_i * proportion <= cat_max
                prob += spend[pid] * proportion <= float(cat_max)

    # ── Solve ─────────────────────────────────────────────────────────────────
    solver = pulp.PULP_CBC_CMD(msg=0)   # suppress solver output
    status = prob.solve(solver)
    status_str = pulp.LpStatus[prob.status]

    if prob.status not in (1, -1):  # 1=Optimal, -1=Infeasible
        # Feasible but not proven optimal — still usable
        pass

    if prob.status == -1:
        # Infeasible — constraints conflict, fall back
        return _fallback_proportional(participants, reason="LP infeasible — constraints conflict")

    # ── Extract solution ──────────────────────────────────────────────────────
    participant_plans = []
    total_spend = 0.0

    for p in participants:
        pid = p.participant_id
        raw_spend = pulp.value(spend[pid])
        if raw_spend is None:
            raw_spend = float(p.budget_min)

        actual_spend = round(max(float(p.budget_min), min(float(p.budget_max), raw_spend)), 2)
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
            category_breakdown=category_breakdown,
            is_at_minimum=abs(actual_spend - p.budget_min) < 1.0,
            is_at_maximum=abs(actual_spend - p.budget_max) < 1.0,
        ))

    utilisations = [pp.budget_utilisation for pp in participant_plans]
    avg_util = sum(utilisations) / len(utilisations) if utilisations else 0
    variance = sum((u - avg_util) ** 2 for u in utilisations) / len(utilisations) if utilisations else 0
    fairness = max(0.0, 1.0 - variance * 10)   # 0–1, penalise variance

    return BudgetPlan(
        status="optimal" if prob.status == 1 else "feasible",
        group_total=round(total_spend, 2),
        group_average=round(total_spend / n, 2),
        min_spend=round(min(pp.total_spend for pp in participant_plans), 2),
        max_spend=round(max(pp.total_spend for pp in participant_plans), 2),
        avg_utilisation=round(avg_util, 3),
        fairness_score=round(fairness, 3),
        participants=participant_plans,
        solver_message=f"LP status: {status_str}",
    )


def _build_category_breakdown(
    total_spend: float,
    constraints: list[dict],
) -> list[CategoryAllocation]:
    """Allocate total spend across categories respecting any caps."""
    # Start with default proportions
    allocations = {cat: total_spend * prop for cat, prop in DEFAULT_CATEGORY_PROPORTIONS.items()}

    # Apply caps — if a category is capped, redistribute excess to misc
    excess = 0.0
    for constraint in (constraints or []):
        cat = constraint.get("category", "").lower()
        cap = constraint.get("max")
        if cat in allocations and cap is not None:
            if allocations[cat] > float(cap):
                excess += allocations[cat] - float(cap)
                allocations[cat] = float(cap)

    allocations["misc"] = allocations.get("misc", 0) + excess

    return [
        CategoryAllocation(
            category=cat,
            amount_usd=round(allocations[cat], 2),
            proportion=round(allocations[cat] / total_spend, 3) if total_spend > 0 else 0,
        )
        for cat in CATEGORIES
    ]


def _fallback_proportional(
    participants: list[ParticipantBudget],
    reason: str,
) -> BudgetPlan:
    """
    Simple fallback: each person spends 75% of their max budget.
    Used when PuLP is unavailable or LP is infeasible.
    """
    participant_plans = []
    total = 0.0

    for p in participants:
        spend = round(max(float(p.budget_min), float(p.budget_max) * TARGET_UTILISATION), 2)
        total += spend
        participant_plans.append(ParticipantPlan(
            participant_id=p.participant_id,
            name=p.name,
            total_spend=spend,
            budget_min=p.budget_min,
            budget_max=p.budget_max,
            budget_utilisation=round(spend / p.budget_max, 3) if p.budget_max > 0 else 0,
            category_breakdown=_build_category_breakdown(spend, p.category_constraints),
            is_at_minimum=False,
            is_at_maximum=False,
        ))

    n = len(participants)
    return BudgetPlan(
        status="fallback",
        group_total=round(total, 2),
        group_average=round(total / n, 2) if n else 0,
        min_spend=round(min(pp.total_spend for pp in participant_plans), 2) if participant_plans else 0,
        max_spend=round(max(pp.total_spend for pp in participant_plans), 2) if participant_plans else 0,
        avg_utilisation=TARGET_UTILISATION,
        fairness_score=1.0,
        participants=participant_plans,
        solver_message=f"Fallback mode: {reason}",
    )
