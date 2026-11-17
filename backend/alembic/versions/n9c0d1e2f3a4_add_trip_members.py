"""add_trip_members

Revision ID: n9c0d1e2f3a4
Revises: m8b9c0d1e2f3
Create Date: 2026-11-18 10:00:00.000000

trip_members — logged-in accounts that joined a group trip (group stamps, memories)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import func

revision: str = "n9c0d1e2f3a4"
down_revision: Union[str, None] = "m8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trip_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trip_id", sa.Uuid(), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.UniqueConstraint("trip_id", "user_id", name="uq_trip_member"),
    )
    op.create_index("ix_trip_members_trip_id", "trip_members", ["trip_id"])
    op.create_index("ix_trip_members_user_id", "trip_members", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_trip_members_user_id", table_name="trip_members")
    op.drop_index("ix_trip_members_trip_id", table_name="trip_members")
    op.drop_table("trip_members")
