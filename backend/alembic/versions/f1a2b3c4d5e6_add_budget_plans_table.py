"""add_budget_plans_table

Revision ID: f1a2b3c4d5e6
Revises: e1a2b3c4d5e6
Create Date: 2026-07-30 10:00:00.000000

Adds budget_plans table to persist LP optimizer output per trip,
and adds quick_info column to destinations for human-readable
destination descriptions surfaced by the India sync pipeline.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── budget_plans table ────────────────────────────────────────────────────
    op.create_table(
        "budget_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "trip_id",
            sa.Uuid(),
            sa.ForeignKey("trips.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("group_total", sa.Float(), nullable=False),
        sa.Column("group_average", sa.Float(), nullable=False),
        sa.Column("min_spend", sa.Float(), nullable=False),
        sa.Column("max_spend", sa.Float(), nullable=False),
        sa.Column("avg_utilisation", sa.Float(), nullable=False),
        sa.Column("fairness_score", sa.Float(), nullable=False),
        sa.Column("solver_message", sa.String(length=200), nullable=True),
        sa.Column("participants_json", sa.JSON(), nullable=False),
        sa.Column("sacrifice_scores_json", sa.JSON(), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_budget_plans_trip_id", "budget_plans", ["trip_id"], unique=False)

    # ── destinations: add quick_info column ───────────────────────────────────
    op.add_column(
        "destinations",
        sa.Column("quick_info", sa.String(length=400), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("destinations", "quick_info")
    op.drop_index("ix_budget_plans_trip_id", table_name="budget_plans")
    op.drop_table("budget_plans")
