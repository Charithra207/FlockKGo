"""Username rules + generation for public profiles (/u/<username>)."""

import re
import secrets

from sqlalchemy.orm import Session

from app.models.user import User

USERNAME_RE = re.compile(r"^[a-z0-9_]{3,30}$")
RESERVED = {
    "admin", "me", "settings", "login", "logout", "signup", "api", "explore", "spots",
    "flockgo", "support", "help", "about", "u", "user", "users", "null", "undefined",
}


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9_]+", "", (text or "").lower().replace(" ", "_").replace(".", "_"))
    s = re.sub(r"_+", "_", s).strip("_")[:20]
    return s if len(s) >= 3 and s not in RESERVED else "traveller"


def username_problem(name: str) -> str | None:
    """Human-readable reason a username can't be used, or None."""
    if not USERNAME_RE.match(name):
        return "Usernames are 3–30 characters: lowercase letters, numbers and _"
    if name in RESERVED:
        return "That username is reserved"
    return None


def unique_username(db: Session, base: str) -> str:
    base = slugify(base)
    if not db.query(User.id).filter(User.username == base).first():
        return base
    for _ in range(20):
        cand = f"{base}{secrets.randbelow(9000) + 1000}"
        if not db.query(User.id).filter(User.username == cand).first():
            return cand
    return f"{base}{secrets.token_hex(4)}"


def ensure_username(db: Session, user: User) -> None:
    """Old accounts (before profiles) get a username on first use."""
    if not user.username:
        user.username = unique_username(db, user.display_name or user.email.split("@")[0])
        db.commit()
        db.refresh(user)
