"""
user_auth.py — Email + password accounts for the spots feature.

Stdlib only (no new dependencies):
  - Passwords: hashlib.scrypt with a random 16-byte salt.
  - Tokens:    base64url(JSON payload) + "." + base64url(HMAC-SHA256),
               sent as  Authorization: Bearer <token>.

This is separate from the X-API-Key auth in services/auth.py, which
identifies the *client app*; this identifies the *person*.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dependencies import get_db
from app.models.user import User

_bearer = HTTPBearer(auto_error=False)
_DEV_SECRET = "dev-only-insecure-token-secret"

# scrypt parameters (~16 MB memory, fast enough for a login endpoint)
_N, _R, _P = 2 ** 14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_hex, dk_hex = stored.split("$")
        if algo != "scrypt":
            return False
        dk = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p), dklen=len(dk_hex) // 2,
        )
        return hmac.compare_digest(dk.hex(), dk_hex)
    except (ValueError, TypeError):
        return False


def _secret() -> bytes:
    settings = get_settings()
    secret = settings.auth_token_secret or settings.api_secret_key
    if not secret:
        if settings.environment == "production":
            raise RuntimeError("AUTH_TOKEN_SECRET must be set in production")
        secret = _DEV_SECRET
    return secret.encode()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def create_token(user_id: uuid.UUID) -> str:
    ttl = get_settings().auth_token_ttl_days * 86400
    payload = _b64(json.dumps({"sub": str(user_id), "exp": int(time.time()) + ttl}).encode())
    sig = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def decode_token(token: str) -> Optional[uuid.UUID]:
    try:
        payload, sig = token.split(".")
        expected = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(_unb64(payload))
        if int(data["exp"]) < time.time():
            return None
        return uuid.UUID(data["sub"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


# ── One-purpose tokens (password reset, email verification) ──────────────────
# Signed with a key derived per purpose, so they can never work as login tokens.

def _purpose_key(purpose: str) -> bytes:
    return hmac.new(_secret(), f"purpose:{purpose}".encode(), hashlib.sha256).digest()


def create_purpose_token(user_id: uuid.UUID, purpose: str, ttl_seconds: int, bind: str = "") -> str:
    """bind: a value that must still match when used (e.g. part of the password
    hash, so a reset link stops working once the password changes)."""
    body = {"sub": str(user_id), "exp": int(time.time()) + ttl_seconds,
            "b": hashlib.sha256(bind.encode()).hexdigest()[:16]}
    payload = _b64(json.dumps(body).encode())
    sig = _b64(hmac.new(_purpose_key(purpose), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def decode_purpose_token(token: str, purpose: str) -> Optional[tuple[uuid.UUID, str]]:
    """(user_id, bind_hash) if valid and unexpired."""
    try:
        payload, sig = token.split(".")
        expected = _b64(hmac.new(_purpose_key(purpose), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(_unb64(payload))
        if int(data["exp"]) < time.time():
            return None
        return uuid.UUID(data["sub"]), data.get("b", "")
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def bind_hash(bind: str) -> str:
    return hashlib.sha256(bind.encode()).hexdigest()[:16]


def get_optional_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not creds or creds.scheme.lower() != "bearer":
        return None
    user_id = decode_token(creds.credentials)
    if not user_id:
        return None
    return db.get(User, user_id)


def get_current_user(user: Optional[User] = Depends(get_optional_user)) -> User:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please log in to do this",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        # Accounts listed in ADMIN_EMAILS are promoted on first admin request.
        from sqlalchemy.orm import object_session

        allowed = {e.strip().lower() for e in get_settings().admin_emails.split(",") if e.strip()}
        db = object_session(user)
        if user.email.lower() in allowed and db is not None:
            user.is_admin = True
            db.commit()
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")
    return user
