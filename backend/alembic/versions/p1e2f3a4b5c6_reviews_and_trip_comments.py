"""reviews_and_trip_comments

Revision ID: p1e2f3a4b5c6
Revises: o0d1e2f3a4b5
Create Date: 2026-11-18 18:00:00.000000

spot_reviews (rating + text + photos), trip_comments (notes inside a group trip)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import func

revision: str = "p1e2f3a4b5c6"
down_revision: Union[str, None] = "o0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "spot_reviews",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("spot_id", sa.Uuid(), sa.ForeignKey("spots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("photos", sa.JSON(), nullable=False),
        sa.Column("visited_month", sa.String(7), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "spot_id", name="uq_spot_review"),
    )
    op.create_index("ix_spot_reviews_spot_id", "spot_reviews", ["spot_id"])
    op.create_index("ix_spot_reviews_user_id", "spot_reviews", ["user_id"])

    op.create_table(
        "trip_comments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trip_id", sa.Uuid(), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("author_name", sa.String(80), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    op.create_index("ix_trip_comments_trip_id", "trip_comments", ["trip_id"])
    op.create_index("ix_trip_comments_created_at", "trip_comments", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_trip_comments_created_at", table_name="trip_comments")
    op.drop_index("ix_trip_comments_trip_id", table_name="trip_comments")
    op.drop_table("trip_comments")
    op.drop_index("ix_spot_reviews_user_id", table_name="spot_reviews")
    op.drop_index("ix_spot_reviews_spot_id", table_name="spot_reviews")
    op.drop_table("spot_reviews")
