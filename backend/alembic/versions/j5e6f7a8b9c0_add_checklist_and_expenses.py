"""add_checklist_and_expenses

Revision ID: j5e6f7a8b9c0
Revises: i4d5e6f7a8b9
Create Date: 2026-07-31 10:00:00.000000

Adds two new tables for the Trip Lifecycle Companion:

  checklist_items   — Collaborative Packing Hub (Module 1)
                      One pool of packing items per trip.
                      Items can be assigned to participants (Divvy Up)
                      and marked as packed (real-time sync via WS).

  expenses          — Live Expense Log (Module 2)
                      INR-denominated payments per trip participant.

  expense_splits    — Per-participant share for each expense.
                      Powers the Splitwise-style debt settlement engine.

All FK constraints include CASCADE delete so removing a Trip or Participant
cleans up all related rows automatically.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func


revision: str = "j5e6f7a8b9c0"
down_revision: Union[str, None] = "i4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── checklist_items ───────────────────────────────────────────────────────
    op.create_table(
        "checklist_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "trip_id",
            sa.Uuid(),
            sa.ForeignKey("trips.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False, server_default="misc"),
        sa.Column("suggested_by", sa.String(length=100), nullable=False, server_default="system"),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column(
            "assigned_to_participant_id",
            sa.Uuid(),
            sa.ForeignKey("participants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_packed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("packed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "packed_by_participant_id",
            sa.Uuid(),
            sa.ForeignKey("participants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_checklist_items_trip_id", "checklist_items", ["trip_id"])
    op.create_index(
        "ix_checklist_items_trip_packed",
        "checklist_items",
        ["trip_id", "is_packed"],
    )

    # ── expenses ──────────────────────────────────────────────────────────────
    op.create_table(
        "expenses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "trip_id",
            sa.Uuid(),
            sa.ForeignKey("trips.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "paid_by_participant_id",
            sa.Uuid(),
            sa.ForeignKey("participants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("description", sa.String(length=300), nullable=False),
        sa.Column("amount_inr", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False, server_default="misc"),
        sa.Column("receipt_note", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expenses_trip_id", "expenses", ["trip_id"])
    op.create_index("ix_expenses_paid_by", "expenses", ["paid_by_participant_id"])

    # ── expense_splits ────────────────────────────────────────────────────────
    op.create_table(
        "expense_splits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "expense_id",
            sa.Uuid(),
            sa.ForeignKey("expenses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "trip_id",
            sa.Uuid(),
            sa.ForeignKey("trips.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "participant_id",
            sa.Uuid(),
            sa.ForeignKey("participants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("share_amount_inr", sa.Integer(), nullable=False),
        sa.Column("is_settled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expense_splits_expense_id", "expense_splits", ["expense_id"])
    op.create_index("ix_expense_splits_participant_id", "expense_splits", ["participant_id"])
    op.create_index("ix_expense_splits_trip_id", "expense_splits", ["trip_id"])


def downgrade() -> None:
    # expense_splits
    op.drop_index("ix_expense_splits_trip_id", table_name="expense_splits")
    op.drop_index("ix_expense_splits_participant_id", table_name="expense_splits")
    op.drop_index("ix_expense_splits_expense_id", table_name="expense_splits")
    op.drop_table("expense_splits")

    # expenses
    op.drop_index("ix_expenses_paid_by", table_name="expenses")
    op.drop_index("ix_expenses_trip_id", table_name="expenses")
    op.drop_table("expenses")

    # checklist_items
    op.drop_index("ix_checklist_items_trip_packed", table_name="checklist_items")
    op.drop_index("ix_checklist_items_trip_id", table_name="checklist_items")
    op.drop_table("checklist_items")
