import uuid

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid,
)
from sqlalchemy.sql import false, func

from app.db.database import Base

MARK_STATUSES = ["been", "want"]


class PlaceMark(Base):
    """
    "Been there" (a passport stamp) or "want to go" (bucket list), per user,
    for either a spot or a destination hub. One mark per user per place:
    stamping a bucket-list place moves it to "been".
    """
    __tablename__ = "place_marks"
    __table_args__ = (
        UniqueConstraint("user_id", "spot_id", name="uq_mark_user_spot"),
        UniqueConstraint("user_id", "destination_id", name="uq_mark_user_destination"),
        CheckConstraint(
            "(spot_id IS NULL) <> (destination_id IS NULL)", name="ck_mark_one_place",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    spot_id = Column(Uuid, ForeignKey("spots.id", ondelete="CASCADE"), nullable=True, index=True)
    destination_id = Column(Uuid, ForeignKey("destinations.id", ondelete="CASCADE"), nullable=True, index=True)
    status = Column(String(10), nullable=False)  # been | want
    # Only for "been": when you went, your photo, and whether the photo's
    # location (read in the browser, never stored) was near the place.
    visited_on = Column(Date, nullable=True)
    photo_url = Column(String(500), nullable=True)
    photo_verified = Column(Boolean, nullable=False, default=False, server_default=false())
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
