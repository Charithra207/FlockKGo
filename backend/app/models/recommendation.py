import uuid
from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.sql import func

from app.db.database import Base


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    trip_id = Column(Uuid, ForeignKey("trips.id"), nullable=False)
    destination_name = Column(String(200), nullable=False)
    country = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    ml_score = Column(Float, nullable=True)
    cluster_alignment = Column(Float, nullable=True)
    why_recommended = Column(Text, nullable=True)
    estimated_budget_range = Column(String(100), nullable=True)
    best_activities = Column(JSON, nullable=False, default=list)
    potential_concerns = Column(Text, nullable=True)
    llm_model_used = Column(String(100), nullable=True)
    prompt_version = Column(String(20), nullable=True)
    quality_score = Column(Float, nullable=True)   # 0.0–1.0 from LLMEvaluator
    rank = Column(Integer, nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LLMUsageLog(Base):
    __tablename__ = "llm_usage_logs"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    trip_id = Column(Uuid, ForeignKey("trips.id"), nullable=True)
    model_name = Column(String(100), nullable=False)
    task_type = Column(String(100), nullable=False)
    prompt_tokens = Column(Integer, nullable=False)
    completion_tokens = Column(Integer, nullable=False)
    cost_usd = Column(Float, nullable=False)
    latency_ms = Column(Integer, nullable=False)
    prompt_version = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
