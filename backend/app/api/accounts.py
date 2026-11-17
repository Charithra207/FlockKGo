"""
accounts.py — Sign up / log in / who am I.

POST /v1/auth/register   {email, password, display_name} -> {token, user}
POST /v1/auth/login      {email, password}               -> {token, user}
GET  /v1/auth/me                                          -> user
PATCH /v1/auth/me    {display_name?, username?, bio?, home_district?, avatar_url?, profile_public?}
POST /v1/auth/forgot       {email}            -> always 200 (emails a reset link if the account exists)
POST /v1/auth/reset        {token, password}  -> {token, user}
POST /v1/auth/verify/send                     -> emails a verification link (logged in)
POST /v1/auth/verify       {token}            -> marks the email verified
POST /v1/auth/google       {credential}       -> {token, user}  ("Sign in with Google")
GET  /v1/auth/config                          -> which optional features are switched on
"""

import secrets

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.trips import limiter
from app.config import get_settings
from app.dependencies import get_db
from app.models.user import User
from app.api.spots import _check_photo_url
from app.core.karnataka import normalize_district
from app.services.usernames import ensure_username, unique_username, username_problem
import httpx

from app.services.captcha import check_human
from app.services.mailer import email_configured, send_email
from app.services.user_auth import (
    bind_hash, create_purpose_token, create_token, decode_purpose_token, get_admin_user, get_current_user,
    hash_password, verify_password,
)

RESET_TTL = 3600            # reset links work for 1 hour
VERIFY_TTL = 3 * 86400      # verification links work for 3 days

router = APIRouter(prefix="/auth", tags=["accounts"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)
    captcha_token: Optional[str] = Field(default=None, max_length=4000)
    website: Optional[str] = Field(default=None, max_length=200)  # honeypot: humans leave it empty


class ForgotRequest(BaseModel):
    email: EmailStr


class ResetRequest(BaseModel):
    token: str = Field(max_length=500)
    password: str = Field(min_length=8, max_length=128)


class TokenRequest(BaseModel):
    token: str = Field(max_length=500)


class GoogleRequest(BaseModel):
    credential: str = Field(max_length=5000)


class ProfileUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    username: Optional[str] = Field(default=None, max_length=30)
    bio: Optional[str] = Field(default=None, max_length=200)
    home_district: Optional[str] = Field(default=None, max_length=100)
    avatar_url: Optional[str] = Field(default=None, max_length=500)
    profile_public: Optional[bool] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


def _admin_emails() -> set[str]:
    return {e.strip().lower() for e in get_settings().admin_emails.split(",") if e.strip()}


def _sync_admin(user: User, db: Session) -> None:
    """Promote accounts listed in ADMIN_EMAILS (never demotes anyone)."""
    if not user.is_admin and user.email.lower() in _admin_emails():
        user.is_admin = True
        db.commit()
        db.refresh(user)


def user_out(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "unlock_credits": user.unlock_credits,
        "is_admin": user.is_admin,
        "username": user.username,
        "bio": user.bio,
        "home_district": user.home_district,
        "avatar_url": user.avatar_url,
        "profile_public": user.profile_public,
        "email_verified": user.email_verified,
    }


@router.post("/register", status_code=201)
@limiter.limit("10/minute")
def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)):
    check_human(body.captcha_token, body.website, request.client.host if request.client else None)
    email = body.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(
        email=email,
        display_name=body.display_name.strip(),
        password_hash=hash_password(body.password),
        unlock_credits=get_settings().signup_bonus_credits,
        username=unique_username(db, body.display_name or email.split("@")[0]),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    db.refresh(user)
    _sync_admin(user, db)
    _send_verification(user)
    return {"token": create_token(user.id), "user": user_out(user)}


@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong email or password")
    _sync_admin(user, db)
    ensure_username(db, user)
    return {"token": create_token(user.id), "user": user_out(user)}


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _sync_admin(user, db)
    ensure_username(db, user)
    return user_out(user)


@router.patch("/me")
@limiter.limit("30/hour")
def update_me(
    request: Request,
    body: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = body.model_dump(exclude_unset=True)
    if "display_name" in data and data["display_name"] is not None:
        user.display_name = data["display_name"].strip() or user.display_name
    if data.get("username") is not None:
        name = data["username"].strip().lower()
        if name != user.username:
            problem = username_problem(name)
            if problem:
                raise HTTPException(status_code=422, detail=problem)
            if db.query(User.id).filter(User.username == name, User.id != user.id).first():
                raise HTTPException(status_code=409, detail="That username is taken")
            user.username = name
    if "bio" in data:
        user.bio = (data["bio"] or "").strip() or None
    if "home_district" in data:
        raw = (data["home_district"] or "").strip()
        if raw:
            district = normalize_district(raw)
            if not district:
                raise HTTPException(status_code=422, detail="Pick a Karnataka district")
            user.home_district = district
        else:
            user.home_district = None
    if "avatar_url" in data:
        try:
            user.avatar_url = _check_photo_url(data["avatar_url"] or None)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
    if data.get("profile_public") is not None:
        user.profile_public = data["profile_public"]
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That username is taken")
    db.refresh(user)
    return user_out(user)



# ── Optional features ─────────────────────────────────────────────────────────

@router.get("/config")
def auth_config():
    s = get_settings()
    return {
        "email": email_configured(),
        "google_client_id": s.google_client_id,
        "captcha_site_key": s.turnstile_site_key if s.turnstile_secret else None,
        "require_email_verification": bool(s.require_email_verification and email_configured()),
    }


def _link(path: str, token: str) -> str:
    return f"{get_settings().frontend_base_url.rstrip('/')}{path}?token={token}"


def reset_link_for(user: User) -> str:
    token = create_purpose_token(user.id, "reset", RESET_TTL, bind=user.password_hash)
    return _link("/reset-password", token)


def _send_verification(user: User) -> bool:
    if user.email_verified or not email_configured():
        return False
    token = create_purpose_token(user.id, "verify", VERIFY_TTL, bind=user.email)
    return send_email(
        user.email, "Confirm your FlockGo email",
        f"Hi {user.display_name},\n\nConfirm your email to start sharing spots on FlockGo:\n"
        f"{_link('/verify-email', token)}\n\nThe link works for 3 days. If you didn't sign up, ignore this email.",
    )


# ── Password reset ────────────────────────────────────────────────────────────

@router.post("/forgot")
@limiter.limit("5/hour")
def forgot_password(request: Request, body: ForgotRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if user:
        send_email(
            user.email, "Reset your FlockGo password",
            f"Hi {user.display_name},\n\nReset your password here (the link works for 1 hour):\n"
            f"{reset_link_for(user)}\n\nIf you didn't ask for this, you can ignore this email.",
        )
    # Same answer either way, so this can't be used to find out who has an account.
    return {"ok": True, "email_enabled": email_configured()}


@router.post("/reset")
@limiter.limit("10/hour")
def reset_password(request: Request, body: ResetRequest, db: Session = Depends(get_db)):
    data = decode_purpose_token(body.token, "reset")
    user = db.get(User, data[0]) if data else None
    if not user or data[1] != bind_hash(user.password_hash):  # used already / password changed since
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired. Ask for a new one.")
    user.password_hash = hash_password(body.password)
    user.email_verified = True  # they proved they can read this inbox
    db.commit()
    db.refresh(user)
    return {"token": create_token(user.id), "user": user_out(user)}


# ── Email verification ───────────────────────────────────────────────────────

@router.post("/verify/send")
@limiter.limit("5/hour")
def resend_verification(request: Request, user: User = Depends(get_current_user)):
    if user.email_verified:
        return {"sent": False, "already": True}
    if not email_configured():
        raise HTTPException(status_code=503, detail="Email isn't set up on this server yet")
    return {"sent": _send_verification(user)}


@router.post("/verify")
def verify_email(body: TokenRequest, db: Session = Depends(get_db)):
    data = decode_purpose_token(body.token, "verify")
    user = db.get(User, data[0]) if data else None
    if not user or data[1] != bind_hash(user.email):
        raise HTTPException(status_code=400, detail="This link is invalid or has expired")
    user.email_verified = True
    db.commit()
    return {"verified": True}


# ── Sign in with Google ───────────────────────────────────────────────────────

def verify_google_credential(credential: str) -> dict:
    """Check a Google Identity Services ID token with Google. Returns its claims."""
    client_id = get_settings().google_client_id
    if not client_id:
        raise HTTPException(status_code=503, detail="Google sign-in isn't set up")
    try:
        r = httpx.get("https://oauth2.googleapis.com/tokeninfo", params={"id_token": credential}, timeout=10)
        claims = r.json() if r.status_code == 200 else {}
    except Exception:
        claims = {}
    if (
        claims.get("aud") != client_id
        or claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com")
        or str(claims.get("email_verified")).lower() != "true"
        or not claims.get("sub") or not claims.get("email")
    ):
        raise HTTPException(status_code=401, detail="Google sign-in failed. Please try again.")
    return claims


@router.post("/google")
@limiter.limit("20/minute")
def google_login(request: Request, body: GoogleRequest, db: Session = Depends(get_db)):
    claims = verify_google_credential(body.credential)
    email = claims["email"].lower()
    user = db.query(User).filter(User.google_sub == claims["sub"]).first()
    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:  # Google has verified this inbox, so it's safe to link
            user.google_sub = claims["sub"]
            user.email_verified = True
        else:
            name = (claims.get("name") or email.split("@")[0])[:80]
            user = User(
                email=email, display_name=name,
                password_hash=hash_password(secrets.token_urlsafe(32)),  # no password: Google only
                unlock_credits=get_settings().signup_bonus_credits,
                username=unique_username(db, name),
                email_verified=True, google_sub=claims["sub"],
            )
            db.add(user)
        db.commit()
        db.refresh(user)
    _sync_admin(user, db)
    ensure_username(db, user)
    return {"token": create_token(user.id), "user": user_out(user)}



class AdminResetRequest(BaseModel):
    email: EmailStr


@router.post("/admin/reset-link")
def admin_reset_link(body: AdminResetRequest, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    """For when email isn't set up: an admin makes a reset link to send the person (e.g. on WhatsApp)."""
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="No account with that email")
    return {"link": reset_link_for(user), "expires_in_minutes": RESET_TTL // 60}
