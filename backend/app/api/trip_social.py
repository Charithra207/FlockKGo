"""
trip_social.py — connects a group trip to the spots map and the passport.

GET    /v1/trips/{id}/destination   the group's chosen place (vote winner, else top pick),
                                    with its district + coordinates, so the UI can show
                                    hidden gems and cafes around it
POST   /v1/trips/{id}/join          "I'm on this trip" (logged in)
DELETE /v1/trips/{id}/join          leave
GET    /v1/trips/{id}/memories      who's on the trip, who has stamped the place, trip photos
GET    /v1/trips/{id}/comments      trip notes / chat (?after=<last id> for polling)
POST   /v1/trips/{id}/comments      {text, author_name?}

Anyone with the trip link can see memories (the link is already the trip's
access control). Trip photos are only shown for members with public profiles.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.trips import limiter
from app.dependencies import get_db
from app.services.voting_service import RankedChoiceVoting
from app.models.destination import Destination
from app.models.place_mark import PlaceMark
from app.models.recommendation import Recommendation
from app.models.trip import Trip
from app.models.trip_member import TripMember
from app.models.trip_comment import TripComment
from app.models.user import User
from app.models.vote import Vote
from app.services.user_auth import get_current_user, get_optional_user

router = APIRouter(prefix="/trips", tags=["trip-social"])


def _get_trip(db: Session, trip_id: uuid.UUID) -> Trip:
    trip = db.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


def chosen_destination(db: Session, trip_id: uuid.UUID) -> tuple[Optional[Recommendation], Optional[Destination], bool]:
    """(recommendation, destination row, decided_by_vote)."""
    recs = db.query(Recommendation).filter(Recommendation.trip_id == trip_id).all()
    if not recs:
        return None, None, False
    rec, decided = None, False
    ballots = [v.ranked_choices for v in db.query(Vote).filter(Vote.trip_id == trip_id).all()]
    if ballots:
        result = RankedChoiceVoting(ml_scores={str(r.id): float(r.ml_score or 0.0) for r in recs}).run_election(ballots)
        winner = result.get("winner")
        rec = next((r for r in recs if str(r.id) == str(winner)), None)
        decided = rec is not None
    if rec is None:
        rec = min(recs, key=lambda r: (r.rank if r.rank is not None else 999))
    dest = (
        db.query(Destination)
        .filter(func.lower(Destination.name) == (rec.destination_name or "").lower())
        .first()
    )
    return rec, dest, decided


def dest_out(dest: Optional[Destination]) -> Optional[dict]:
    if not dest:
        return None
    return {
        "id": str(dest.id),
        "name": dest.name,
        "district": dest.district,
        "latitude": dest.latitude,
        "longitude": dest.longitude,
        "quick_info": dest.quick_info,
    }


@router.get("/{trip_id}/destination")
def trip_destination(trip_id: uuid.UUID, db: Session = Depends(get_db)):
    trip = _get_trip(db, trip_id)
    rec, dest, decided = chosen_destination(db, trip.id)
    return {
        "trip_id": str(trip.id),
        "name": rec.destination_name if rec else None,
        "decided_by_vote": decided,
        "destination": dest_out(dest),
    }


@router.post("/{trip_id}/join")
def join_trip(trip_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    trip = _get_trip(db, trip_id)
    db.add(TripMember(trip_id=trip.id, user_id=user.id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # already a member
    return {"joined": True, "members": db.query(TripMember).filter(TripMember.trip_id == trip.id).count()}


@router.delete("/{trip_id}/join")
def leave_trip(trip_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    trip = _get_trip(db, trip_id)
    db.query(TripMember).filter(TripMember.trip_id == trip.id, TripMember.user_id == user.id).delete()
    db.commit()
    return {"joined": False}


@router.get("/{trip_id}/memories")
def trip_memories(
    trip_id: uuid.UUID,
    db: Session = Depends(get_db),
    viewer: Optional[User] = Depends(get_optional_user),
):
    trip = _get_trip(db, trip_id)
    rec, dest, decided = chosen_destination(db, trip.id)
    rows = (
        db.query(TripMember, User)
        .join(User, User.id == TripMember.user_id)
        .filter(TripMember.trip_id == trip.id)
        .order_by(TripMember.joined_at)
        .all()
    )
    marks = {}
    if dest and rows:
        marks = {
            m.user_id: m for m in db.query(PlaceMark).filter(
                PlaceMark.destination_id == dest.id, PlaceMark.user_id.in_([u.id for _, u in rows]),
            ).all()
        }
    members = []
    for _, u in rows:
        m = marks.get(u.id)
        been = bool(m and m.status == "been")
        show_photo = been and (u.profile_public or (viewer and viewer.id == u.id))
        members.append({
            "username": u.username,
            "display_name": u.display_name,
            "avatar_url": u.avatar_url,
            "stamped": been,
            "visited_on": m.visited_on.isoformat() if been and m.visited_on else None,
            "photo_verified": bool(been and m.photo_verified),
            "trip_photo_url": m.photo_url if show_photo else None,
        })
    return {
        "trip_id": str(trip.id),
        "trip_name": trip.name,
        "destination_name": rec.destination_name if rec else None,
        "decided_by_vote": decided,
        "destination": dest_out(dest),
        "members": members,
        "me_joined": bool(viewer and any(u.id == viewer.id for _, u in rows)),
        "stamped_count": sum(1 for m in members if m["stamped"]),
    }


# ── Trip notes / chat ─────────────────────────────────────────────────────────

class CommentIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    author_name: Optional[str] = Field(default=None, max_length=80)  # if not logged in


@router.get("/{trip_id}/comments")
def list_comments(trip_id: uuid.UUID, after: int = 0, db: Session = Depends(get_db)):
    trip = _get_trip(db, trip_id)
    rows = (
        db.query(TripComment, User).outerjoin(User, User.id == TripComment.user_id)
        .filter(TripComment.trip_id == trip.id, TripComment.id > after)
        .order_by(TripComment.id.asc()).limit(300).all()
    )
    return {"items": [
        {
            "id": c.id, "text": c.text, "author_name": c.author_name,
            "username": u.username if u else None, "avatar_url": u.avatar_url if u else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c, u in rows
    ]}


@router.post("/{trip_id}/comments", status_code=201)
@limiter.limit("30/minute")
def add_comment(
    request: Request,
    trip_id: uuid.UUID,
    body: CommentIn,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    trip = _get_trip(db, trip_id)
    name = user.display_name if user else (body.author_name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Add your name (or log in)")
    c = TripComment(trip_id=trip.id, user_id=user.id if user else None, author_name=name[:80], text=body.text.strip())
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"id": c.id}
