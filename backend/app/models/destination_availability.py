import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Uuid
from sqlalchemy.sql import func
from app.db.database import Base


class DestinationAvailability(Base):
    __tablename__ = "destination_availability"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    destination_id = Column(Uuid, ForeignKey("destinations.id", ondelete="CASCADE"), nullable=False, index=True)
    is_available = Column(Boolean, nullable=False, default=True)
    reason = Column(String(200), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
