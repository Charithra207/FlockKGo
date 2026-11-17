"""trust_and_safety

Revision ID: o0d1e2f3a4b5
Revises: n9c0d1e2f3a4
Create Date: 2026-11-18 14:00:00.000000

spots.safety, spot_reports, users.email_verified, users.google_sub
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import func

revision: str = "o0d1e2f3a4b5"
down_revision: Union[str, None] = "n9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("spots") as b:
        b.add_column(sa.Column("safety", sa.JSON(), nullable=True))
    op.execute("UPDATE spots SET safety = '[]'")
    with op.batch_alter_table("spots") as b:
        b.alter_column("safety", existing_type=sa.JSON(), nullable=False)

    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
        b.add_column(sa.Column("google_sub", sa.String(64), nullable=True))
    op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)

    op.create_table(
        "spot_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("spot_id", sa.Uuid(), sa.ForeignKey("spots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.String(30), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "spot_id", name="uq_spot_report"),
    )
    op.create_index("ix_spot_reports_spot_id", "spot_reports", ["spot_id"])
    op.create_index("ix_spot_reports_user_id", "spot_reports", ["user_id"])
    op.create_index("ix_spot_reports_status", "spot_reports", ["status"])


def downgrade() -> None:
    for ix in ("ix_spot_reports_status", "ix_spot_reports_user_id", "ix_spot_reports_spot_id"):
        op.drop_index(ix, table_name="spot_reports")
    op.drop_table("spot_reports")
    op.drop_index("ix_users_google_sub", table_name="users")
    with op.batch_alter_table("users") as b:
        b.drop_column("google_sub")
        b.drop_column("email_verified")
    with op.batch_alter_table("spots") as b:
        b.drop_column("safety")
