import uuid
from sqlalchemy import JSON, Column, Date, DateTime, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.sql import func

from app.db.database import Base


class SurveyResponse(Base):
    """
    Per-participant survey submission.

    Logistics Constraint Fields (all nullable for backward compatibility)
    ─────────────────────────────────────────────────────────────────────
    activity_intensity      — participant's personal intensity rating (1–5).
                              1 = Slow/Accessible, 5 = High Adventure.
                              The pipeline uses min/max across the group to
                              bracket the destination activity filter.
    mandatory_amenities     — amenities this participant personally requires.
                              Merged with other participants' lists; a destination
                              must satisfy the union of all mandatory amenities.
    transit_preferences     — this participant's preferred travel modes.
    immovable_events        — this participant's fixed events.
                              Merged with the trip-level events for scheduling.
    """
    __tablename__ = "survey_responses"
    __table_args__ = (
        Index("ix_survey_responses_trip_id", "trip_id"),
        Index("ix_survey_responses_participant_id", "participant_id"),
    )

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

    # ── Logistics Constraint Fields ───────────────────────────────────────────
    activity_intensity = Column(Integer, nullable=True)                # 1–5
    mandatory_amenities = Column(JSON, nullable=True, default=list)    # list[str]
    transit_preferences = Column(JSON, nullable=True, default=list)    # list[str]
    immovable_events = Column(JSON, nullable=True, default=list)       # list[dict]
