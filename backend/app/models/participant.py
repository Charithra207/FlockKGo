import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Uuid
from sqlalchemy.sql import func

from app.db.database import Base


class Participant(Base):
    __tablename__ = "participants"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    trip_id = Column(Uuid, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    survey_token = Column(String(100), unique=True, nullable=False)
    sms_sent = Column(Boolean, nullable=False, default=False)
    joined_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
