"""
api_key.py — API key storage model.

Keys are never stored in plaintext. Only the SHA-256 hash is persisted.
The raw key is shown once at creation and never again.

Why hash API keys?
  If the DB is breached, attackers get hashes — useless without the
  original key. Same principle as password hashing.
"""

import uuid

from sqlalchemy import Boolean, Column, DateTime, String, Text, Uuid
from sqlalchemy.sql import func

from app.db.database import Base


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)           # human label e.g. "frontend-prod"
    key_hash = Column(String(64), nullable=False, unique=True)  # SHA-256 hex
    key_prefix = Column(String(8), nullable=False)       # first 8 chars for identification
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    description = Column(Text, nullable=True)
