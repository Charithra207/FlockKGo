from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint, Uuid
from sqlalchemy.sql import func

from app.db.database import Base


class TripMember(Base):
    """A logged-in account that says "I'm on this trip" (for group stamps + memories)."""
    __tablename__ = "trip_members"
    __table_args__ = (UniqueConstraint("trip_id", "user_id", name="uq_trip_member"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    trip_id = Column(Uuid, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
