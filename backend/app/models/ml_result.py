import uuid
from sqlalchemy import JSON, Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.database import Base


class MLRunResult(Base):
    __tablename__ = "ml_run_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id = Column(UUID(as_uuid=True), ForeignKey("trips.id"), nullable=False)
    cluster_labels = Column(JSON, nullable=False, default=dict)
    cluster_centers = Column(JSON, nullable=False, default=list)
    destination_scores = Column(JSON, nullable=False, default=list)
    preference_drift = Column(JSON, nullable=False, default=dict)
    similarity_matrix = Column(JSON, nullable=False, default=list)
    ran_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
