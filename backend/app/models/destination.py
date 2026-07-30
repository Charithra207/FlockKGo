import uuid

from sqlalchemy import JSON, Column, Float, Integer, String, Uuid, Boolean, DateTime
from sqlalchemy.sql import func

from app.db.database import Base


class Destination(Base):
    """
    A travel destination in the catalog.

    embedding     — OpenAI text-embedding-3-small vector (1536-d), stored as JSON.
                    NULL until embed_destinations.py has been run or the API key
                    is present at startup.
    feature_vector — hand-crafted 16-d fallback vector (always populated).
    embedding_model — which model produced the embedding, for cache invalidation.
    """
    __tablename__ = "destinations"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False, unique=True)
    country = Column(String(100), nullable=False)

    # Budget characteristics
    budget_midpoint = Column(Integer, nullable=False)   # USD per person
    budget_flexibility = Column(Float, nullable=False)  # 0.0 (rigid) – 1.0 (flexible)

    # Preference metadata (used for both embedding text and fallback scoring)
    vibes = Column(JSON, nullable=False, default=list)       # e.g. ["beach", "food"]
    climate = Column(String(20), nullable=False)             # warm | cold | any
    activity_level = Column(String(20), nullable=False)      # relaxed | moderate | intense

    # Vectors
    feature_vector = Column(JSON, nullable=True)             # 16-d hand-crafted vector
    embedding = Column(JSON, nullable=True)                  # 1536-d OpenAI embedding
    embedding_model = Column(String(100), nullable=True)     # e.g. text-embedding-3-small

    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # India Sync columns
    osm_source_id = Column(String(100), nullable=True, unique=True, index=True)
    travel_dna = Column(JSON, nullable=True)
    tourism_metadata = Column(JSON, nullable=True)

    # Human-readable one-liner generated during sync — returned to the React UI
    quick_info = Column(String(400), nullable=True)

    # ── Logistics Constraint Columns ──────────────────────────────────────────
    # Numeric intensity 1–5, derived from DNA adventure_score during sync.
    # 1=relaxed/accessible, 3=moderate, 5=high-adventure.
    activity_intensity = Column(Integer, nullable=True)

    # Amenity labels present at this destination.
    # Derived from OSM tags + tourism_metadata during sync.
    # e.g. ["Vegetarian Friendly", "Wheelchair Accessible"]
    amenities = Column(JSON, nullable=True, default=list)

    # Calendar months (1–12) when this destination is ideal to visit.
    # Derived from DNA seasonal scores during sync.
    # e.g. [10, 11, 12, 1, 2] = October through February
    best_months = Column(JSON, nullable=True, default=list)

    # True if the destination is plausibly reachable by a 6-hour private car
    # journey from most Indian metro areas (heuristic based on location).
    # Used by the Contextual Duration Calculator.
    is_road_trip_accessible = Column(Boolean, nullable=True)
