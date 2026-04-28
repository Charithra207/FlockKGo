import uuid
from sqlalchemy import Column, DateTime, ForeignKey, JSON, UniqueConstraint, Uuid
from sqlalchemy.sql import func

from app.db.database import Base


class Vote(Base):
    __tablename__ = "votes"
    __table_args__ = (UniqueConstraint("trip_id", "participant_id", name="uq_trip_participant_vote"),)

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    trip_id = Column(Uuid, ForeignKey("trips.id"), nullable=False)
    participant_id = Column(Uuid, ForeignKey("participants.id"), nullable=False)
    ranked_choices = Column(JSON, nullable=False)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
