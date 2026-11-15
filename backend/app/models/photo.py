import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, LargeBinary, String, Uuid
from sqlalchemy.sql import func

from app.db.database import Base


class Photo(Base):
    """
    User-uploaded spot photo, stored in the database.

    The browser resizes images to ~1600 px JPEG before upload (~200 KB),
    so a free 0.5 GB Postgres holds a few thousand. Swap for object storage
    (S3 / Cloudinary / Supabase Storage) later without changing the API:
    spots reference photos by URL ("/v1/photos/<id>").
    """
    __tablename__ = "photos"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    content_type = Column(String(30), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    data = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
