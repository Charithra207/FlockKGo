import uuid

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Uuid
from sqlalchemy.sql import func
from sqlalchemy.sql.expression import false as sa_false, true as sa_true

from app.db.database import Base


class User(Base):
    """
    A persistent account (separate from per-trip Participants).

    unlock_credits — the "give a spot, get a spot" currency.
                     Earned when a submitted spot is approved, spent to
                     unlock the exact location of a hidden spot.
    """
    __tablename__ = "users"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True, index=True)
    display_name = Column(String(80), nullable=False)
    password_hash = Column(String(255), nullable=False)
    unlock_credits = Column(Integer, nullable=False, default=0)
    is_admin = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Public profile (/u/<username>)
    username = Column(String(30), nullable=True, unique=True, index=True)
    bio = Column(String(200), nullable=True)
    home_district = Column(String(100), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    profile_public = Column(Boolean, nullable=False, default=True, server_default=sa_true())

    email_verified = Column(Boolean, nullable=False, default=False, server_default=sa_false())
    google_sub = Column(String(64), nullable=True, unique=True)  # "Sign in with Google" account id
