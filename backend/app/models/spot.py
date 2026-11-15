import uuid

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint, Uuid,
)
from sqlalchemy.sql import func

from app.db.database import Base

SPOT_CATEGORIES = [
    "cafe", "viewpoint", "waterfall", "trek", "beach", "lake", "temple",
    "heritage", "food", "stay", "wildlife", "other",
]
SPOT_STATUSES = ["pending", "approved", "rejected"]


class Spot(Base):
    """
    A specific place inside Karnataka: a hidden viewpoint, a waterfall, a
    cafe, a military hotel...

    is_hidden  — hidden spots are "locked": non-owners only see a teaser
                 (category, district, rough area) until they spend a credit.
    status     — community submissions start as "pending" and only become
                 visible once an admin approves them.
    source     — community | osm | admin
    featured   — admin-picked "famous" (used for cafes, food, etc.)
    """
    __tablename__ = "spots"
    __table_args__ = (Index("ix_spots_lat_lng", "latitude", "longitude"),)

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(30), nullable=False, index=True)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    district = Column(String(100), nullable=False, index=True)
    # Nearest catalog hub (e.g. Coorg) within ~60 km, if any.
    destination_id = Column(Uuid, ForeignKey("destinations.id", ondelete="SET NULL"), nullable=True, index=True)

    is_hidden = Column(Boolean, nullable=False, default=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    source = Column(String(20), nullable=False, default="community")
    featured = Column(Boolean, nullable=False, default=False)
    osm_id = Column(String(64), nullable=True, unique=True)

    # Practical info locals know
    best_months = Column(JSON, nullable=False, default=list)       # [6, 7, 8]
    access_notes = Column(Text, nullable=True)                     # "1 km walk from the parking..."
    permit_required = Column(Boolean, nullable=False, default=False)
    photo_url = Column(String(500), nullable=True)
    tags = Column(JSON, nullable=False, default=list)              # ["monsoon", "sunrise"]
    extra = Column(JSON, nullable=False, default=dict)             # source-specific (opening hours...)

    submitted_by = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    review_note = Column(String(500), nullable=True)
    vouch_count = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)


class SpotUnlock(Base):
    __tablename__ = "spot_unlocks"
    __table_args__ = (UniqueConstraint("user_id", "spot_id", name="uq_spot_unlock"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    spot_id = Column(Uuid, ForeignKey("spots.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SpotVouch(Base):
    """'I've been here, it's real.' One per user per spot. Used for ranking."""
    __tablename__ = "spot_vouches"
    __table_args__ = (UniqueConstraint("user_id", "spot_id", name="uq_spot_vouch"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    spot_id = Column(Uuid, ForeignKey("spots.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
