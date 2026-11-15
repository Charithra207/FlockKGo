"""add_users_and_spots

Revision ID: k6f7a8b9c0d1
Revises: j5e6f7a8b9c0
Create Date: 2026-11-15 10:00:00.000000

Karnataka "give a spot, get a spot":

  users          — persistent accounts with unlock_credits
  spots          — hidden spots, cafes, viewpoints... (community / osm / admin)
  spot_unlocks   — which user unlocked which hidden spot
  spot_vouches   — "I've been here" confirmations

Also adds state / district / latitude / longitude to destinations.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import func

revision: str = "k6f7a8b9c0d1"
down_revision: Union[str, None] = "j5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("destinations") as b:
        b.add_column(sa.Column("state", sa.String(100), nullable=True))
        b.add_column(sa.Column("district", sa.String(100), nullable=True))
        b.add_column(sa.Column("latitude", sa.Float(), nullable=True))
        b.add_column(sa.Column("longitude", sa.Float(), nullable=True))
    op.create_index("ix_destinations_state", "destinations", ["state"])
    op.create_index("ix_destinations_district", "destinations", ["district"])

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("unlock_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "spots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("district", sa.String(100), nullable=False),
        sa.Column("destination_id", sa.Uuid(), sa.ForeignKey("destinations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("source", sa.String(20), nullable=False, server_default="community"),
        sa.Column("featured", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("osm_id", sa.String(64), nullable=True, unique=True),
        sa.Column("best_months", sa.JSON(), nullable=False),
        sa.Column("access_notes", sa.Text(), nullable=True),
        sa.Column("permit_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("photo_url", sa.String(500), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("extra", sa.JSON(), nullable=False),
        sa.Column("submitted_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("review_note", sa.String(500), nullable=True),
        sa.Column("vouch_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    for col in ("category", "district", "destination_id", "status", "submitted_by"):
        op.create_index(f"ix_spots_{col}", "spots", [col])
    op.create_index("ix_spots_lat_lng", "spots", ["latitude", "longitude"])

    for table, uq in (("spot_unlocks", "uq_spot_unlock"), ("spot_vouches", "uq_spot_vouch")):
        op.create_table(
            table,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("spot_id", sa.Uuid(), sa.ForeignKey("spots.id", ondelete="CASCADE"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
            sa.UniqueConstraint("user_id", "spot_id", name=uq),
        )
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])
        op.create_index(f"ix_{table}_spot_id", table, ["spot_id"])


def downgrade() -> None:
    for table in ("spot_vouches", "spot_unlocks"):
        op.drop_index(f"ix_{table}_spot_id", table_name=table)
        op.drop_index(f"ix_{table}_user_id", table_name=table)
        op.drop_table(table)
    op.drop_index("ix_spots_lat_lng", table_name="spots")
    for col in ("category", "district", "destination_id", "status", "submitted_by"):
        op.drop_index(f"ix_spots_{col}", table_name="spots")
    op.drop_table("spots")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_destinations_district", table_name="destinations")
    op.drop_index("ix_destinations_state", table_name="destinations")
    with op.batch_alter_table("destinations") as b:
        b.drop_column("longitude")
        b.drop_column("latitude")
        b.drop_column("district")
        b.drop_column("state")
