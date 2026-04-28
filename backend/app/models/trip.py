import uuid
from sqlalchemy import JSON, Column, DateTime, Integer, String, Uuid
from sqlalchemy.sql import func

from app.db.database import Base


class Trip(Base):
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
