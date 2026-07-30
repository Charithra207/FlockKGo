import uuid
from sqlalchemy import JSON, Column, DateTime, Integer, String, Uuid
from sqlalchemy.sql import func

from app.db.database import Base


class Trip(Base):
    """
    Core trip record.

    Logistics Constraint Fields (all nullable for backward compatibility)
    ─────────────────────────────────────────────────────────────────────
    activity_intensity_min  — group's lowest tolerated intensity (1–5 scale).
                              Destinations with intensity > this are filtered out
                              for the least-active participant.
    activity_intensity_max  — group's highest desired intensity (1–5 scale).
                              Destinations below this are permitted but scored lower.
    mandatory_amenities     — list of strings the group requires at the destination.
                              e.g. ["Vegetarian Friendly", "Wheelchair Accessible"].
                              A destination must satisfy ALL listed amenities.
    transit_preferences     — ordered list of preferred travel modes.
                              e.g. ["Train", "Private Car"].
                              Used by the duration/radius calculator to determine
                              reachable destinations given trip duration.
    immovable_events        — JSON list of fixed schedule anchors the AI must plan
                              around.  Each entry: {label, date, type}.
                              e.g. [{"label": "Wedding", "date": "2026-12-14",
                                     "type": "arrival_deadline"}].
    origin_city             — departure city used by the radius calculator.
                              e.g. "Mumbai".  Required when transit_preferences
                              includes "Private Car".
    """
    __tablename__ = "trips"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    organizer_name = Column(String(100), nullable=False)
    organizer_email = Column(String(255), nullable=False)
    name = Column(String(200), nullable=False)
    status = Column(String(50), nullable=False, default="collecting_preferences")
    trip_month = Column(String(20), nullable=True)
    duration_days = Column(Integer, nullable=True)
    settings = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # ── Logistics Constraint Fields ───────────────────────────────────────────
    # Integer 1–5 intensity range the group can handle
    activity_intensity_min = Column(Integer, nullable=True)   # lowest tolerance in group
    activity_intensity_max = Column(Integer, nullable=True)   # highest desire in group

    # Amenities every selected destination must provide
    mandatory_amenities = Column(JSON, nullable=True, default=list)   # list[str]

    # Preferred transit modes — drives the duration/radius calculator
    transit_preferences = Column(JSON, nullable=True, default=list)   # list[str]

    # Fixed schedule events the planner must respect
    immovable_events = Column(JSON, nullable=True, default=list)       # list[dict]

    # Origin city for radius calculation (used with Private Car)
    origin_city = Column(String(100), nullable=True)
