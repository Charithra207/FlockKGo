import uuid
from sqlalchemy import JSON, Column, Date, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.sql import func

from app.db.database import Base


class SurveyResponse(Base):
    __tablename__ = "survey_responses"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    participant_id = Column(Uuid, ForeignKey("participants.id"), nullable=False)
    trip_id = Column(Uuid, ForeignKey("trips.id"), nullable=False)
    budget_min = Column(Integer, nullable=False)
    budget_max = Column(Integer, nullable=False)
    available_start = Column(Date, nullable=True)
    available_end = Column(Date, nullable=True)
    vibes = Column(JSON, nullable=False, default=list)
    climate_pref = Column(String(50), nullable=False, default="any")
    activity_level = Column(String(50), nullable=False, default="moderate")
    excluded_destinations = Column(JSON, nullable=False, default=list)
    already_visited = Column(JSON, nullable=False, default=list)
    feature_vector = Column(JSON, nullable=False, default=list)
    previous_vector = Column(JSON, nullable=False, default=list)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
