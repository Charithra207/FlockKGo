"""
expense.py — Live Expense Log model for the Financial Guide & Checker.

Design:
  expenses          — one row per payment made by any participant.
                      All amounts in INR (Paisa-level precision via Integer storing paise,
                      but we store whole rupees as Integer for simplicity).
  expense_splits    — how a single expense is divided among the group.
                      If the trip has N participants and the payer pays for everyone,
                      N split rows are created (including one for the payer's own share).

Debt settlement:
  The settlement logic is computed on-the-fly in the API layer (no separate table).
  Running the Splitwise-style algorithm over all expense_splits for a trip gives
  the minimal set of transfer transactions needed to zero all balances.

Currency:
  All amounts stored as Integer rupees (INR). No USD conversion in the expense
  module — the budget_plans table uses USD (LP optimizer), but the expense tracker
  is India-first and stores INR directly.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.sql import func

from app.db.database import Base


class Expense(Base):
    """A single payment made by one participant on behalf of some or all of the group."""

    __tablename__ = "expenses"
    __table_args__ = (
        Index("ix_expenses_trip_id", "trip_id"),
        Index("ix_expenses_paid_by", "paid_by_participant_id"),
    )

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    trip_id = Column(
        Uuid, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )

    # Who paid
    paid_by_participant_id = Column(
        Uuid, ForeignKey("participants.id", ondelete="CASCADE"), nullable=False
    )

    # Payment details
    description = Column(String(300), nullable=False)
    amount_inr = Column(Integer, nullable=False)          # Total paid in INR
    category = Column(String(50), nullable=False, default="misc")
    # e.g. "food", "transport", "accommodation", "activities", "misc"

    receipt_note = Column(Text, nullable=True)            # optional free-text note / UPI ref
    paid_at = Column(DateTime(timezone=True), nullable=True)  # when the payment happened

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ExpenseSplit(Base):
    """
    How one Expense is divided among participants.

    For a ₹600 dinner split equally among 3 people:
      - 3 rows with share_amount_inr = 200 each
      - The payer's row has is_settled=True by definition (they already paid)
      - The other two rows have is_settled=False until they reimburse the payer
    """

    __tablename__ = "expense_splits"
    __table_args__ = (
        Index("ix_expense_splits_expense_id", "expense_id"),
        Index("ix_expense_splits_participant_id", "participant_id"),
        Index("ix_expense_splits_trip_id", "trip_id"),
    )

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    expense_id = Column(
        Uuid, ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False
    )
    trip_id = Column(
        Uuid, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )  # denormalized for fast per-trip queries

    participant_id = Column(
        Uuid, ForeignKey("participants.id", ondelete="CASCADE"), nullable=False
    )
    share_amount_inr = Column(Integer, nullable=False)   # this participant's share in INR
    is_settled = Column(Integer, nullable=False, default=0)  # 0=owed, 1=settled
    # Using Integer instead of Boolean for SQLite compatibility

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
