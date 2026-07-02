import uuid
from sqlalchemy import Column, DateTime, Integer, JSON, String, Text, Uuid
from sqlalchemy.sql import func
from app.db.database import Base


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    status = Column(String(20), nullable=False, default="running")
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    fetched = Column(Integer, nullable=True)
    inserted = Column(Integer, nullable=True)
    updated = Column(Integer, nullable=True)
    deactivated = Column(Integer, nullable=True)
    rejected = Column(Integer, nullable=True)
    stage_counts = Column(JSON, nullable=True)
