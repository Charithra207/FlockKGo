"""
accounts.py — Sign up / log in / who am I.

POST /v1/auth/register   {email, password, display_name} -> {token, user}
POST /v1/auth/login      {email, password}               -> {token, user}
GET  /v1/auth/me                                          -> user
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.trips import limiter
from app.config import get_settings
from app.dependencies import get_db
from app.models.user import User
from app.services.user_auth import create_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["accounts"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)


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
    return {"token": create_token(user.id), "user": user_out(user)}


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _sync_admin(user, db)
    return user_out(user)
