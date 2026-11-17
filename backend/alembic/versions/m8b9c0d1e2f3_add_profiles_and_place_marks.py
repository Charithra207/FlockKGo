"""add_profiles_and_place_marks

Revision ID: m8b9c0d1e2f3
Revises: l7a8b9c0d1e2
Create Date: 2026-11-17 12:00:00.000000

users        — public profile fields (username, bio, home district, avatar, privacy)
place_marks  — "been there" / "want to go" per user, for a spot or a destination
"""

import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import func

revision: str = "m8b9c0d1e2f3"
down_revision: Union[str, None] = "l7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9_]+", "", (name or "").lower().replace(" ", "_"))[:20]
    return s if len(s) >= 3 else "traveller"


def upgrade() -> None:
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("username", sa.String(30), nullable=True))
        b.add_column(sa.Column("bio", sa.String(200), nullable=True))
        b.add_column(sa.Column("home_district", sa.String(100), nullable=True))
        b.add_column(sa.Column("avatar_url", sa.String(500), nullable=True))
        b.add_column(sa.Column("profile_public", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # Give existing accounts a username.
    conn = op.get_bind()
    taken = set()
    for uid, name, email in conn.execute(sa.text("SELECT id, display_name, email FROM users")).fetchall():
        base = _slug(name or email.split("@")[0])
        cand, n = base, 1
        while cand in taken:
            n += 1
            cand = f"{base}{n}"
        taken.add(cand)
        conn.execute(sa.text("UPDATE users SET username = :u WHERE id = :i"), {"u": cand, "i": uid})

    op.create_table(
        "place_marks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("spot_id", sa.Uuid(), sa.ForeignKey("spots.id", ondelete="CASCADE"), nullable=True),
        sa.Column("destination_id", sa.Uuid(), sa.ForeignKey("destinations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("visited_on", sa.Date(), nullable=True),
        sa.Column("photo_url", sa.String(500), nullable=True),
        sa.Column("photo_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "spot_id", name="uq_mark_user_spot"),
        sa.UniqueConstraint("user_id", "destination_id", name="uq_mark_user_destination"),
        sa.CheckConstraint("(spot_id IS NULL) <> (destination_id IS NULL)", name="ck_mark_one_place"),
    )
    op.create_index("ix_place_marks_user_id", "place_marks", ["user_id"])
    op.create_index("ix_place_marks_spot_id", "place_marks", ["spot_id"])
    op.create_index("ix_place_marks_destination_id", "place_marks", ["destination_id"])


def downgrade() -> None:
    op.drop_index("ix_place_marks_destination_id", table_name="place_marks")
    op.drop_index("ix_place_marks_spot_id", table_name="place_marks")
    op.drop_index("ix_place_marks_user_id", table_name="place_marks")
    op.drop_table("place_marks")
    op.drop_index("ix_users_username", table_name="users")
    with op.batch_alter_table("users") as b:
        for c in ("profile_public", "avatar_url", "home_district", "bio", "username"):
            b.drop_column(c)
