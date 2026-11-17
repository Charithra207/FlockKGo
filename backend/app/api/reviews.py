"""
reviews.py — star ratings, short reviews and photos on spots.

GET    /v1/spots/{id}/reviews     list + average (only if you can see the spot)
PUT    /v1/spots/{id}/reviews     add or update yours  {rating 1-5, text?, photos[<=4], visited_month?}
DELETE /v1/spots/{id}/reviews     remove yours

Reviews of a locked hidden spot are only visible to people who can see it,
because photos and text would give the place away.
"""

import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.spots import _can_see, _check_photo_url, _get_spot, _user_context
from app.api.trips import limiter
from app.dependencies import get_db
from app.models.spot import SpotReview
from app.models.user import User
from app.services.user_auth import get_current_user, get_optional_user

router = APIRouter(tags=["reviews"])

MONTH_RE = re.compile(r"^(19|20)\d{2}-(0[1-9]|1[0-2])$")


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    text: Optional[str] = Field(default=None, max_length=1000)
    photos: list[str] = Field(default_factory=list, max_length=4)
    visited_month: Optional[str] = None

    @field_validator("photos")
    @classmethod
    def _photos(cls, v: list[str]) -> list[str]:
        return [p for p in (_check_photo_url(x) for x in v) if p]

    @field_validator("visited_month")
    @classmethod
    def _month(cls, v: Optional[str]) -> Optional[str]:
        if v and not MONTH_RE.match(v):
            raise ValueError("visited_month looks like 2026-07")
        return v or None


def _visible_spot(db: Session, spot_id: uuid.UUID, user: Optional[User]):
    spot = _get_spot(db, spot_id)
    if spot.status != "approved":
        raise HTTPException(status_code=404, detail="Spot not found")
    unlocked, _ = _user_context(db, user, [spot.id])
    if not _can_see(spot, user, unlocked):
        raise HTTPException(status_code=403, detail="Unlock this spot to see and write reviews")
    return spot


def _out(r: SpotReview, u: User, me: Optional[User]) -> dict:
    return {
        "id": r.id,
        "rating": r.rating,
        "text": r.text,
        "photos": r.photos or [],
        "visited_month": r.visited_month,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "author": {"username": u.username, "display_name": u.display_name, "avatar_url": u.avatar_url},
        "mine": bool(me and me.id == u.id),
    }


@router.get("/spots/{spot_id}/reviews")
def list_reviews(spot_id: uuid.UUID, db: Session = Depends(get_db), user: Optional[User] = Depends(get_optional_user)):
    spot = _visible_spot(db, spot_id, user)
    rows = (
        db.query(SpotReview, User).join(User, User.id == SpotReview.user_id)
        .filter(SpotReview.spot_id == spot.id)
        .order_by(SpotReview.updated_at.desc()).limit(100).all()
    )
    ratings = [r.rating for r, _ in rows]
    return {
        "count": len(rows),
        "average": round(sum(ratings) / len(ratings), 1) if ratings else None,
        "items": [_out(r, u, user) for r, u in rows],
    }


@router.put("/spots/{spot_id}/reviews")
@limiter.limit("30/hour")
def upsert_review(
    request: Request,
    spot_id: uuid.UUID,
    body: ReviewIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    spot = _visible_spot(db, spot_id, user)
    if spot.submitted_by == user.id:
        raise HTTPException(status_code=400, detail="You can't review a spot you shared")
    review = db.query(SpotReview).filter(SpotReview.spot_id == spot.id, SpotReview.user_id == user.id).first()
    fields = {"rating": body.rating, "text": (body.text or "").strip() or None,
              "photos": body.photos, "visited_month": body.visited_month}
    if review:
        for k, v in fields.items():
            setattr(review, k, v)
    else:
        review = SpotReview(spot_id=spot.id, user_id=user.id, **fields)
        db.add(review)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Try again")
    db.refresh(review)
    return _out(review, user, user)


@router.delete("/spots/{spot_id}/reviews")
def delete_review(spot_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.query(SpotReview).filter(SpotReview.spot_id == spot_id, SpotReview.user_id == user.id).delete()
    db.commit()
    return {"deleted": True}
