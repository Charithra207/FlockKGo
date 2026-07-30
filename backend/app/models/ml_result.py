import uuid
from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Uuid
from sqlalchemy.sql import func

from app.db.database import Base


class MLRunResult(Base):
    __tablename__ = "ml_run_results"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    trip_id = Column(Uuid, ForeignKey("trips.id"), nullable=False)
    cluster_labels = Column(JSON, nullable=False, default=dict)
    cluster_centers = Column(JSON, nullable=False, default=list)
    cluster_count = Column(JSON, nullable=True)
    silhouette_score = Column(Float, nullable=True)
    destination_scores = Column(JSON, nullable=False, default=list)
    preference_drift = Column(JSON, nullable=False, default=dict)
    similarity_matrix = Column(JSON, nullable=False, default=list)
    # New — stored so the insights endpoint doesn't recompute every request
    outlier_participants = Column(JSON, nullable=True, default=list)   # [{participant_id, avg_similarity}]
    similar_pairs = Column(JSON, nullable=True, default=list)          # [{p1, p2, similarity}]
    # Anti-Dictator: {participant_id: float} — Individual Sacrifice Scores [0.0, 1.0]
    sacrifice_scores = Column(JSON, nullable=True, default=dict)
    # Logistics pre-filter report — stored for transparency in the Results page
    # Contains: total_initial, filtered counts per phase, constraint_report dict
    constraint_report = Column(JSON, nullable=True, default=dict)
    ran_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
