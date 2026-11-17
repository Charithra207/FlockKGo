from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.sql import func

from app.db.database import Base


class TripComment(Base):
    """Notes / chat inside a group trip, so the plan doesn't get lost in WhatsApp."""
    __tablename__ = "trip_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trip_id = Column(Uuid, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    author_name = Column(String(80), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
