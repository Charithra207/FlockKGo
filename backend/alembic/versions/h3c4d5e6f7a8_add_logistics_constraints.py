"""add_logistics_constraints

Revision ID: h3c4d5e6f7a8
Revises: g2b3c4d5e6f7
Create Date: 2026-07-30 11:00:00.000000

Adds Composite Constraint fields to trips and survey_responses tables:
  trips:
    - activity_intensity_min  INTEGER  (1–5 scale)
    - activity_intensity_max  INTEGER  (1–5 scale)
    - mandatory_amenities     JSON     list[str]
    - transit_preferences     JSON     list[str]
    - immovable_events        JSON     list[dict]
    - origin_city             VARCHAR(100)

  survey_responses:
    - activity_intensity      INTEGER  (1–5 scale, per-participant)
    - mandatory_amenities     JSON     list[str]
    - transit_preferences     JSON     list[str]
    - immovable_events        JSON     list[dict]

  destinations:
    - activity_intensity      INTEGER  (1–5, derived during sync)
    - amenities               JSON     list[str]  (tags → amenity labels)
    - best_months             JSON     list[int]  (1–12, ideal visit months)
    - is_road_trip_accessible BOOLEAN  (within 6-hour drive radius heuristic)

All columns nullable for backward compatibility — existing rows default to NULL
which the pre-filter treats as "no constraint / unconstrained".
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h3c4d5e6f7a8"
down_revision: Union[str, None] = "g2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── trips ─────────────────────────────────────────────────────────────────
    op.add_column("trips", sa.Column("activity_intensity_min", sa.Integer(), nullable=True))
    op.add_column("trips", sa.Column("activity_intensity_max", sa.Integer(), nullable=True))
    op.add_column("trips", sa.Column("mandatory_amenities", sa.JSON(), nullable=True))
    op.add_column("trips", sa.Column("transit_preferences", sa.JSON(), nullable=True))
    op.add_column("trips", sa.Column("immovable_events", sa.JSON(), nullable=True))
    op.add_column("trips", sa.Column("origin_city", sa.String(length=100), nullable=True))

    # ── survey_responses ──────────────────────────────────────────────────────
    op.add_column("survey_responses", sa.Column("activity_intensity", sa.Integer(), nullable=True))
    op.add_column("survey_responses", sa.Column("mandatory_amenities", sa.JSON(), nullable=True))
    op.add_column("survey_responses", sa.Column("transit_preferences", sa.JSON(), nullable=True))
    op.add_column("survey_responses", sa.Column("immovable_events", sa.JSON(), nullable=True))

    # ── destinations ──────────────────────────────────────────────────────────
    op.add_column("destinations", sa.Column("activity_intensity", sa.Integer(), nullable=True))
    op.add_column("destinations", sa.Column("amenities", sa.JSON(), nullable=True))
    op.add_column("destinations", sa.Column("best_months", sa.JSON(), nullable=True))
    op.add_column("destinations", sa.Column(
        "is_road_trip_accessible", sa.Boolean(), nullable=True
    ))


def downgrade() -> None:
    op.drop_column("destinations", "is_road_trip_accessible")
    op.drop_column("destinations", "best_months")
    op.drop_column("destinations", "amenities")
    op.drop_column("destinations", "activity_intensity")

    op.drop_column("survey_responses", "immovable_events")
    op.drop_column("survey_responses", "transit_preferences")
    op.drop_column("survey_responses", "mandatory_amenities")
    op.drop_column("survey_responses", "activity_intensity")

    op.drop_column("trips", "origin_city")
    op.drop_column("trips", "immovable_events")
    op.drop_column("trips", "transit_preferences")
    op.drop_column("trips", "mandatory_amenities")
    op.drop_column("trips", "activity_intensity_max")
    op.drop_column("trips", "activity_intensity_min")
