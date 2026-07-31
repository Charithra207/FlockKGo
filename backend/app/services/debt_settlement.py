"""
debt_settlement.py — Splitwise-style debt minimisation engine (INR).

Given a list of expenses with per-participant splits, computes the
minimum number of bank transfers to zero all balances (Splitwise algorithm).

Algorithm:
  1. Compute net balance for each participant: sum(paid) - sum(owed)
  2. Separate into creditors (positive balance) and debtors (negative balance)
  3. Greedily match the largest debtor with the largest creditor, settle the
     smaller of the two amounts, and iterate.

This produces the minimum number of transactions and is O(n log n) where n
is the number of participants.

All amounts are integers (INR rupees). No floating-point used to avoid
rounding errors.
"""

from __future__ import annotations

from typing import Any


def compute_settlements(
    participants: list[dict],       # [{id, name}]
    expenses: list[dict],           # [{paid_by_participant_id, amount_inr}]
    splits: list[dict],             # [{expense_id, participant_id, share_amount_inr, is_settled}]
) -> dict[str, Any]:
    """
    Compute the minimal debt settlement plan.

    Parameters
    ----------
    participants: list[dict]
        Each dict: {"id": str, "name": str}
    expenses: list[dict]
        Each dict: {"id": str, "paid_by_participant_id": str, "amount_inr": int, ...}
    splits: list[dict]
        Each dict: {"expense_id": str, "participant_id": str,
                    "share_amount_inr": int, "is_settled": int}

    Returns
    -------
    dict with:
      balances      — {participant_id: {"name", "paid_total", "owed_total", "net_balance"}}
      settlements   — list of {"from_id", "from_name", "to_id", "to_name", "amount_inr"}
      total_spend   — total INR spent across all expenses
      is_settled    — bool, True if all balances are zero
    """
    id_to_name = {p["id"]: p["name"] for p in participants}

    # ── Step 1: compute paid and owed per participant ─────────────────────────
    paid: dict[str, int] = {p["id"]: 0 for p in participants}
    owed: dict[str, int] = {p["id"]: 0 for p in participants}

    for exp in expenses:
        pid = exp["paid_by_participant_id"]
        if pid in paid:
            paid[pid] += int(exp["amount_inr"])

    for split in splits:
        pid = split["participant_id"]
        # Only count unsettled splits as "still owed"
        if pid in owed:
            owed[pid] += int(split["share_amount_inr"])

    # ── Step 2: net balance ───────────────────────────────────────────────────
    # net > 0 → person is owed money (creditor)
    # net < 0 → person owes money (debtor)
    net: dict[str, int] = {
        pid: paid.get(pid, 0) - owed.get(pid, 0)
        for pid in id_to_name
    }

    balances = {
        pid: {
            "name": id_to_name[pid],
            "paid_total_inr": paid.get(pid, 0),
            "owed_total_inr": owed.get(pid, 0),
            "net_balance_inr": net[pid],
            "status": "creditor" if net[pid] > 0 else ("debtor" if net[pid] < 0 else "settled"),
        }
        for pid in id_to_name
    }

    # ── Step 3: greedy debt minimisation ─────────────────────────────────────
    creditors: list[list] = sorted(
        [[pid, net[pid]] for pid in net if net[pid] > 0],
        key=lambda x: x[1], reverse=True,
    )
    debtors: list[list] = sorted(
        [[pid, -net[pid]] for pid in net if net[pid] < 0],
        key=lambda x: x[1], reverse=True,
    )

    settlements: list[dict] = []

    ci, di = 0, 0
    while ci < len(creditors) and di < len(debtors):
        cred_id, cred_amt = creditors[ci]
        debt_id, debt_amt = debtors[di]

        transfer = min(cred_amt, debt_amt)

        settlements.append({
            "from_id": debt_id,
            "from_name": id_to_name.get(debt_id, "Unknown"),
            "to_id": cred_id,
            "to_name": id_to_name.get(cred_id, "Unknown"),
            "amount_inr": transfer,
        })

        creditors[ci][1] -= transfer
        debtors[di][1] -= transfer

        if creditors[ci][1] == 0:
            ci += 1
        if debtors[di][1] == 0:
            di += 1

    total_spend = sum(int(e["amount_inr"]) for e in expenses)
    all_settled = all(b["net_balance_inr"] == 0 for b in balances.values())

    return {
        "total_spend_inr": total_spend,
        "is_settled": all_settled,
        "balances": balances,
        "settlements": settlements,
        "settlement_count": len(settlements),
    }
