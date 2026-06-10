"""
cache.py — Redis cache helper.

Provides a simple get/set/delete interface that degrades gracefully
when Redis is unavailable (returns None on get, silently skips on set).

Used for:
  - Caching recommendation lists per trip (invalidated on regenerate)
  - Can be extended for any other cacheable data
"""

import json
import uuid
from typing import Any, Optional

RECOMMENDATIONS_TTL = 3600   # 1 hour — recommendations don't change until regenerated


def _get_client():
    """Return a Redis client, or None if Redis is unavailable."""
    try:
        import redis
        from app.config import get_settings
        client = redis.from_url(get_settings().redis_url, decode_responses=True, socket_connect_timeout=2)
        client.ping()
        return client
    except Exception:
        return None


def cache_get(key: str) -> Optional[Any]:
    """Get a value from cache. Returns None if missing or Redis is down."""
    client = _get_client()
    if not client:
        return None
    try:
        raw = client.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def cache_set(key: str, value: Any, ttl: int = 300) -> bool:
    """Set a value in cache. Returns False silently if Redis is down."""
    client = _get_client()
    if not client:
        return False
    try:
        client.setex(key, ttl, json.dumps(value))
        return True
    except Exception:
        return False


def cache_delete(key: str) -> bool:
    """Delete a key from cache."""
    client = _get_client()
    if not client:
        return False
    try:
        client.delete(key)
        return True
    except Exception:
        return False


def recommendations_key(trip_id: uuid.UUID) -> str:
    return f"recommendations:{trip_id}"


def invalidate_recommendations(trip_id: uuid.UUID) -> None:
    """Call this whenever recommendations are regenerated."""
    cache_delete(recommendations_key(trip_id))
