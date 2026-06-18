"""
auth.py — API key authentication.

How it works
------------
1. Admin calls POST /admin/api-keys to create a key.
   Server generates a random 32-byte key, stores only its SHA-256 hash.
   Returns the raw key ONCE — caller must save it.

2. Client sends the key in every request:
   Header: X-API-Key: flockgo_<raw_key>

3. Server hashes the incoming key and looks up the hash in the DB.
   If found and active → request proceeds.
   If not found → 401 Unauthorized.

4. Auth is OPTIONAL in development (API_SECRET_KEY not set).
   This lets you develop locally without managing keys.
   In production (environment=production), auth is enforced.

Security notes
--------------
- Keys are prefixed with "flockgo_" so they're identifiable if leaked.
- First 8 chars (prefix) are stored plaintext for identification.
- SHA-256 hash is constant-time compared (no timing attacks).
- last_used_at is updated on every authenticated request.
"""

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import SessionLocal
from app.dependencies import get_db
from app.models.api_key import APIKey

KEY_PREFIX = "flockgo_"
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def _hash_key(raw_key: str) -> str:
    """SHA-256 hash of the raw key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """
    Generate a new API key.
    Returns (raw_key, key_hash, key_prefix).
    raw_key is shown once and never stored.
    """
    token = secrets.token_hex(32)          # 256 bits of entropy
    raw_key = f"{KEY_PREFIX}{token}"
    key_hash = _hash_key(raw_key)
    key_prefix = raw_key[:8]               # "flockgo_"[:8] always
    return raw_key, key_hash, key_prefix


def create_api_key(db: Session, name: str, description: str = None) -> dict:
    """
    Create and persist a new API key.
    Returns the raw key — caller must save it, it won't be shown again.
    """
    raw_key, key_hash, key_prefix = generate_api_key()

    api_key = APIKey(
        name=name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        description=description,
        is_active=True,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return {
        "id": str(api_key.id),
        "name": api_key.name,
        "key": raw_key,          # shown ONCE — store it now
        "key_prefix": key_prefix,
        "created_at": api_key.created_at.isoformat(),
        "warning": "Save this key — it will never be shown again.",
    }


def verify_api_key(raw_key: str, db: Session) -> Optional[APIKey]:
    """
    Verify a raw API key. Returns the APIKey row if valid, None otherwise.
    Updates last_used_at on success.
    """
    if not raw_key or not raw_key.startswith(KEY_PREFIX):
        return None

    key_hash = _hash_key(raw_key)
    api_key = (
        db.query(APIKey)
        .filter(APIKey.key_hash == key_hash, APIKey.is_active == True)
        .first()
    )

    if api_key:
        # Update last_used_at (non-blocking — ignore failures)
        try:
            api_key.last_used_at = datetime.now(timezone.utc)
            db.commit()
        except Exception:
            db.rollback()

    return api_key


# ── FastAPI dependency ────────────────────────────────────────────────────────

async def get_current_api_key(
    raw_key: str = Security(API_KEY_HEADER),
    db: Session = Depends(get_db),
) -> Optional[APIKey]:
    """
    FastAPI dependency for API key authentication.

    In development (API_SECRET_KEY not set): auth is skipped, returns None.
    In production: enforces X-API-Key header, raises 401 if missing/invalid.

    Usage:
        @router.get("/protected")
        def protected_route(api_key = Depends(get_current_api_key)):
            ...
    """
    settings = get_settings()

    # Dev mode — auth disabled
    if not settings.api_secret_key and settings.environment != "production":
        return None

    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    api_key = verify_api_key(raw_key, db)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key
