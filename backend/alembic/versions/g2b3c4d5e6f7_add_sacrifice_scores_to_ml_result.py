"""add_sacrifice_scores_to_ml_result

Revision ID: g2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-07-30 10:05:00.000000

Adds sacrifice_scores JSON column to ml_run_results.
This stores the Anti-Dictator Individual Sacrifice Scores
{participant_id: float} computed by scoring.compute_sacrifice_scores().
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g2b3c4d5e6f7"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ml_run_results",
        sa.Column("sacrifice_scores", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ml_run_results", "sacrifice_scores")
