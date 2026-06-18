"""
admin.py — Admin endpoints for API key management.

These endpoints are protected by the API_SECRET_KEY env var (master secret).
In production, set API_SECRET_KEY to a strong random value and keep it safe.

Endpoints:
  POST /admin/api-keys          — create a new API key
  GET  /admin/api-keys          — list all keys (no raw values)
  DELETE /admin/api-keys/{id}   — revoke a key
"""

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dependencies import get_db
from app.models.api_key import APIKey
from app.services.auth import create_api_key

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Master secret guard ───────────────────────────────────────────────────────

def _require_master_secret(x_admin_secret: str = Header(None)):
    """
    Protect admin endpoints with the master secret (X-Admin-Secret header).
    This is separate from API keys — only the server operator knows this.
    """
    settings = get_settings()
    if not settings.api_secret_key:
        # Dev mode — admin endpoints are open (no master secret configured)
        return
    if x_admin_secret != settings.api_secret_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin secret",
        )


# ── Schemas ───────────────────────────────────────────────────────────────────

class CreateAPIKeyRequest(BaseModel):
    name: str
    description: str | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/api-keys")
def create_key(
    payload: CreateAPIKeyRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_require_master_secret),
):
    """
    Create a new API key. The raw key is returned once — store it immediately.
    """
    return create_api_key(db, name=payload.name, description=payload.description)


@router.get("/api-keys")
def list_keys(
    db: Session = Depends(get_db),
    _: None = Depends(_require_master_secret),
):
    """List all API keys (raw values never shown)."""
    keys = db.query(APIKey).order_by(APIKey.created_at.desc()).all()
    return [
        {
            "id": str(k.id),
            "name": k.name,
            "key_prefix": k.key_prefix,
            "is_active": k.is_active,
            "description": k.description,
            "created_at": k.created_at.isoformat(),
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        }
        for k in keys
    ]


@router.delete("/api-keys/{key_id}")
def revoke_key(
    key_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(_require_master_secret),
):
    """Revoke (deactivate) an API key."""
    key = db.query(APIKey).filter(APIKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    key.is_active = False
    db.commit()
    return {"success": True, "message": f"Key '{key.name}' revoked"}
