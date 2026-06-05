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
