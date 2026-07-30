"""add constraint_report to ml_result

Revision ID: i4d5e6f7a8b9
Revises: h3c4d5e6f7a8
Create Date: 2026-07-30 00:00:00.000000

Adds the `constraint_report` JSON column to `ml_run_results`.
This stores the per-phase logistics pre-filter report so the Results page
can explain which constraints narrowed the destination pool before ML scoring.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'i4d5e6f7a8b9'
down_revision = 'h3c4d5e6f7a8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'ml_run_results',
        sa.Column('constraint_report', sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('ml_run_results', 'constraint_report')
