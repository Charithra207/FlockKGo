"""
accounts.py — Sign up / log in / who am I.

POST /v1/auth/register   {email, password, display_name} -> {token, user}
POST /v1/auth/login      {email, password}               -> {token, user}
GET  /v1/auth/me                                          -> user
PATCH /v1/auth/me    {display_name?, username?, bio?, home_district?, avatar_url?, profile_public?}
"""

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
from app.services.user_auth import create_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["accounts"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)


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
    }


@router.post("/register", status_code=201)
@limiter.limit("10/minute")
def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)):
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
