"""
spots.py — Karnataka spots: "give a hidden spot, get a hidden spot".

How the economy works
---------------------
* Public spots (cafes, well-known viewpoints...) are fully visible to everyone.
* Hidden spots are LOCKED. Without unlocking, the API only returns a teaser:
  category, district, the nearest hub town and a ~10 km area. The name,
  exact coordinates, photo, description and directions are never sent.
* Every new account gets SIGNUP_BONUS_CREDITS (1) so people can taste it.
* Submit a spot -> an admin reviews it -> on approval the submitter earns
  CREDITS_PER_HIDDEN_SPOT (3) or CREDITS_PER_PUBLIC_SPOT (1).
* Spending 1 credit unlocks one hidden spot forever.
* Your own submissions are always visible to you.
* "Vouch" = "I've been here, it's real". It ranks spots and earns nothing,
  so it can't be farmed.

Endpoints
---------
GET    /v1/spots                 list / map (filters: category, district, destination_id,
                                 hidden, featured, q, lat+lng+radius_km)
GET    /v1/spots/meta            categories, districts, hubs, counts
GET    /v1/spots/mine            my submissions (any status)
GET    /v1/spots/{id}            one spot (redacted if locked)
POST   /v1/spots                 submit (login required)
POST   /v1/spots/{id}/unlock     spend 1 credit
POST   /v1/spots/{id}/vouch      "I've been here"
GET    /v1/admin/spots/pending   review queue (admin)
POST   /v1/admin/spots/{id}/review  approve / reject / feature (admin)
"""

import math
import re
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.trips import limiter
from app.config import get_settings
from app.core.karnataka import (
    KARNATAKA_DISTRICTS, haversine_km, in_karnataka_bbox, normalize_district,
)
from app.dependencies import get_db
from app.models.destination import Destination
from app.models.spot import SPOT_CATEGORIES, Spot, SpotUnlock, SpotVouch
from app.models.user import User
from app.services.user_auth import get_admin_user, get_current_user, get_optional_user

router = APIRouter(tags=["spots"])

HUB_RADIUS_KM = 60.0        # link a spot to the nearest hub within this distance
DUPLICATE_RADIUS_KM = 0.15  # same category this close = probably the same place
TEASER_DECIMALS = 1         # ~11 km — the "somewhere around here" circle


# ── Schemas ───────────────────────────────────────────────────────────────────

def _norm_category(v: str) -> str:
    v = v.strip().lower()
    if v not in SPOT_CATEGORIES:
        raise ValueError(f"category must be one of {SPOT_CATEGORIES}")
    return v


def _norm_months(v: list[int]) -> list[int]:
    if any(m < 1 or m > 12 for m in v):
        raise ValueError("months must be 1-12")
    return sorted(set(v))


def _norm_tags(v: list[str]) -> list[str]:
    return [t.strip().lower()[:30] for t in v if t.strip()]


class SpotSubmit(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    category: str
    latitude: float
    longitude: float
    district: str
    description: Optional[str] = Field(default=None, max_length=3000)
    is_hidden: bool = True
    best_months: list[int] = Field(default_factory=list)
    access_notes: Optional[str] = Field(default=None, max_length=2000)
    permit_required: bool = False
    photo_url: Optional[str] = Field(default=None, max_length=500)
    tags: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("category")
    @classmethod
    def _category(cls, v: str) -> str:
        return _norm_category(v)

    @field_validator("best_months")
    @classmethod
    def _months(cls, v: list[int]) -> list[int]:
        return _norm_months(v)

    @field_validator("photo_url")
    @classmethod
    def _photo(cls, v: Optional[str]) -> Optional[str]:
        return _check_photo_url(v)

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        return _norm_tags(v)


PHOTO_PATH_RE = re.compile(r"^/v1/photos/[0-9a-fA-F-]{36}$")


def _check_photo_url(v: Optional[str]) -> Optional[str]:
    """An uploaded photo (/v1/photos/<id>) or an https:// link."""
    if not v:
        return None
    v = v.strip()
    if not (v.startswith("https://") or PHOTO_PATH_RE.match(v)):
        raise ValueError("photo_url must be an uploaded photo or an https:// link")
    return v


class SpotEdit(BaseModel):
    """Partial update. Owners can edit while pending; admins can edit anything."""
    name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    category: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    district: Optional[str] = None
    description: Optional[str] = Field(default=None, max_length=3000)
    is_hidden: Optional[bool] = None
    best_months: Optional[list[int]] = None
    access_notes: Optional[str] = Field(default=None, max_length=2000)
    permit_required: Optional[bool] = None
    photo_url: Optional[str] = Field(default=None, max_length=500)
    tags: Optional[list[str]] = Field(default=None, max_length=10)

    @field_validator("category")
    @classmethod
    def _category(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _norm_category(v)

    @field_validator("best_months")
    @classmethod
    def _months(cls, v: Optional[list[int]]) -> Optional[list[int]]:
        return None if v is None else _norm_months(v)

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        return None if v is None else _norm_tags(v)

    @field_validator("photo_url")
    @classmethod
    def _photo(cls, v: Optional[str]) -> Optional[str]:
        # "" clears the photo
        return "" if v == "" else _check_photo_url(v)


class ReviewRequest(BaseModel):
    action: Literal["approve", "reject", "feature", "unfeature", "make_public", "make_hidden"]
    note: Optional[str] = Field(default=None, max_length=500)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _nearest_hub(db: Session, lat: float, lng: float) -> Optional[Destination]:
    hubs = (
        db.query(Destination)
        .filter(Destination.is_active == True, Destination.latitude.isnot(None))  # noqa: E712
        .all()
    )
    best, best_d = None, HUB_RADIUS_KM
    for h in hubs:
        d = haversine_km(lat, lng, h.latitude, h.longitude)
        if d <= best_d:
            best, best_d = h, d
    return best


def _user_context(db: Session, user: Optional[User], spot_ids: list) -> tuple[set, set]:
    if not user or not spot_ids:
        return set(), set()
    unlocked = {
        r[0] for r in db.query(SpotUnlock.spot_id)
        .filter(SpotUnlock.user_id == user.id, SpotUnlock.spot_id.in_(spot_ids)).all()
    }
    vouched = {
        r[0] for r in db.query(SpotVouch.spot_id)
        .filter(SpotVouch.user_id == user.id, SpotVouch.spot_id.in_(spot_ids)).all()
    }
    return unlocked, vouched


def _can_see(spot: Spot, user: Optional[User], unlocked: set) -> bool:
    if not spot.is_hidden:
        return True
    if not user:
        return False
    return user.is_admin or spot.submitted_by == user.id or spot.id in unlocked


def _serialize(
    spot: Spot, *, visible: bool, hub_names: dict, vouched: bool = False,
    distance_km: Optional[float] = None, mine: bool = False,
) -> dict:
    hub = hub_names.get(spot.destination_id)
    base = {
        "id": str(spot.id),
        "category": spot.category,
        "district": spot.district,
        "destination": hub,
        "is_hidden": spot.is_hidden,
        "featured": spot.featured,
        "vouch_count": spot.vouch_count,
        "best_months": spot.best_months or [],
        "permit_required": spot.permit_required,
        "tags": spot.tags or [],
        "status": spot.status,
        "locked": not visible,
        "distance_km": round(distance_km, 1) if distance_km is not None else None,
    }
    if not visible:
        base.update({
            "name": f"Hidden {spot.category} near {hub or spot.district}",
            "approx_latitude": round(spot.latitude, TEASER_DECIMALS),
            "approx_longitude": round(spot.longitude, TEASER_DECIMALS),
        })
        return base
    base.update({
        "name": spot.name,
        "description": spot.description,
        "latitude": spot.latitude,
        "longitude": spot.longitude,
        "access_notes": spot.access_notes,
        "photo_url": spot.photo_url,
        "source": spot.source,
        "extra": spot.extra or {},
        "vouched_by_me": vouched,
        "is_mine": mine,
        "is_hidden": spot.is_hidden,
    })
    if mine:
        base["review_note"] = spot.review_note
    return base


def _hub_names(db: Session, spots: list[Spot]) -> dict:
    ids = {s.destination_id for s in spots if s.destination_id}
    if not ids:
        return {}
    return {d.id: d.name for d in db.query(Destination).filter(Destination.id.in_(ids)).all()}


def _get_spot(db: Session, spot_id: uuid.UUID) -> Spot:
    spot = db.get(Spot, spot_id)
    if not spot:
        raise HTTPException(status_code=404, detail="Spot not found")
    return spot


# ── Public read endpoints ─────────────────────────────────────────────────────

@router.get("/spots/meta")
def spots_meta(db: Session = Depends(get_db)):
    counts = dict(
        db.query(Spot.category, func.count(Spot.id))
        .filter(Spot.status == "approved").group_by(Spot.category).all()
    )
    hidden_count = db.query(func.count(Spot.id)).filter(
        Spot.status == "approved", Spot.is_hidden == True  # noqa: E712
    ).scalar()
    hubs = (
        db.query(Destination)
        .filter(Destination.is_active == True, Destination.latitude.isnot(None))  # noqa: E712
        .order_by(Destination.name).all()
    )
    return {
        "categories": SPOT_CATEGORIES,
        "districts": KARNATAKA_DISTRICTS,
        "counts": {c: counts.get(c, 0) for c in SPOT_CATEGORIES},
        "hidden_count": hidden_count,
        "hubs": [
            {"id": str(h.id), "name": h.name, "district": h.district,
             "latitude": h.latitude, "longitude": h.longitude, "vibes": h.vibes}
            for h in hubs
        ],
    }


@router.get("/spots")
def list_spots(
    category: Optional[str] = None,
    district: Optional[str] = None,
    destination_id: Optional[uuid.UUID] = None,
    hidden: Optional[bool] = None,
    featured: Optional[bool] = None,
    q: Optional[str] = Query(default=None, max_length=100),
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_km: float = Query(default=50.0, gt=0, le=500),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    query = db.query(Spot).filter(Spot.status == "approved")
    if category:
        query = query.filter(Spot.category == category.lower())
    if district:
        query = query.filter(Spot.district == (normalize_district(district) or district))
    if destination_id:
        query = query.filter(Spot.destination_id == destination_id)
    if hidden is not None:
        query = query.filter(Spot.is_hidden == hidden)
    if featured is not None:
        query = query.filter(Spot.featured == featured)
    if q:
        # Search only matches visible text: a hidden spot's name is secret.
        like = f"%{q.strip()}%"
        query = query.filter(or_(
            (Spot.is_hidden == False) & Spot.name.ilike(like),  # noqa: E712
            Spot.district.ilike(like),
            Spot.category.ilike(like),
        ))

    near = lat is not None and lng is not None
    if near:
        dlat = radius_km / 111.0
        dlng = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.01))
        query = query.filter(
            Spot.latitude.between(lat - dlat, lat + dlat),
            Spot.longitude.between(lng - dlng, lng + dlng),
        )

    query = query.order_by(Spot.featured.desc(), Spot.vouch_count.desc(), Spot.created_at.desc())

    if near:
        candidates = query.all()
        with_dist = []
        for s in candidates:
            d = haversine_km(lat, lng, s.latitude, s.longitude)
            if d <= radius_km:
                with_dist.append((s, d))
        with_dist.sort(key=lambda x: x[1])
        total = len(with_dist)
        page = with_dist[offset: offset + limit]
    else:
        total = query.count()
        page = [(s, None) for s in query.offset(offset).limit(limit).all()]

    spots = [s for s, _ in page]
    unlocked, vouched = _user_context(db, user, [s.id for s in spots])
    hubs = _hub_names(db, spots)
    items = []
    for s, d in page:
        visible = _can_see(s, user, unlocked)
        if d is not None and not visible:
            # Distance to the exact point would leak the location; use the teaser point.
            d = haversine_km(lat, lng, round(s.latitude, TEASER_DECIMALS), round(s.longitude, TEASER_DECIMALS))
        items.append(_serialize(
            s, visible=visible, hub_names=hubs, vouched=s.id in vouched, distance_km=d,
            mine=bool(user and s.submitted_by == user.id),
        ))
    return {"total": total, "items": items, "credits": user.unlock_credits if user else None}


@router.get("/spots/mine")
def my_spots(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    spots = db.query(Spot).filter(Spot.submitted_by == user.id).order_by(Spot.created_at.desc()).all()
    hubs = _hub_names(db, spots)
    unlocked_ids = [r[0] for r in db.query(SpotUnlock.spot_id).filter(SpotUnlock.user_id == user.id).all()]
    unlocked_spots = db.query(Spot).filter(Spot.id.in_(unlocked_ids)).all() if unlocked_ids else []
    hubs.update(_hub_names(db, unlocked_spots))
    return {
        "credits": user.unlock_credits,
        "submitted": [_serialize(s, visible=True, hub_names=hubs, mine=True) for s in spots],
        "unlocked": [_serialize(s, visible=True, hub_names=hubs) for s in unlocked_spots],
    }


@router.get("/spots/{spot_id}")
def get_spot(
    spot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    spot = _get_spot(db, spot_id)
    mine = bool(user and spot.submitted_by == user.id)
    if spot.status != "approved" and not (mine or (user and user.is_admin)):
        raise HTTPException(status_code=404, detail="Spot not found")
    unlocked, vouched = _user_context(db, user, [spot.id])
    return _serialize(
        spot, visible=_can_see(spot, user, unlocked), hub_names=_hub_names(db, [spot]),
        vouched=spot.id in vouched, mine=mine,
    )


# ── Contribute ────────────────────────────────────────────────────────────────

@router.post("/spots", status_code=201)
@limiter.limit("20/hour")
def submit_spot(
    request: Request,
    body: SpotSubmit,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    settings = get_settings()
    if not in_karnataka_bbox(body.latitude, body.longitude):
        raise HTTPException(status_code=422, detail="That pin is outside Karnataka. We're Karnataka-only for now.")
    district = normalize_district(body.district)
    if not district:
        raise HTTPException(status_code=422, detail="Pick one of Karnataka's districts")

    if not user.is_admin:
        pending = db.query(func.count(Spot.id)).filter(
            Spot.submitted_by == user.id, Spot.status == "pending"
        ).scalar()
        if pending >= settings.max_pending_submissions:
            raise HTTPException(
                status_code=429,
                detail=f"You already have {pending} spots waiting for review. Please wait for those first.",
            )

    # Duplicate check: same category within 150 m, or same name within 2 km.
    box = 0.02
    nearby = db.query(Spot).filter(
        Spot.status != "rejected",
        Spot.latitude.between(body.latitude - box, body.latitude + box),
        Spot.longitude.between(body.longitude - box, body.longitude + box),
    ).all()
    name_key = body.name.strip().lower()
    for s in nearby:
        d = haversine_km(body.latitude, body.longitude, s.latitude, s.longitude)
        if (s.category == body.category and d <= DUPLICATE_RADIUS_KM) or s.name.strip().lower() == name_key:
            raise HTTPException(
                status_code=409,
                detail="Someone has already shared this spot. Try a different one!",
            )

    hub = _nearest_hub(db, body.latitude, body.longitude)
    auto_approve = user.is_admin
    spot = Spot(
        name=body.name.strip(),
        description=body.description,
        category=body.category,
        latitude=body.latitude,
        longitude=body.longitude,
        district=district,
        destination_id=hub.id if hub else None,
        is_hidden=body.is_hidden,
        status="approved" if auto_approve else "pending",
        source="admin" if auto_approve else "community",
        best_months=body.best_months,
        access_notes=body.access_notes,
        permit_required=body.permit_required,
        photo_url=body.photo_url,
        tags=body.tags,
        submitted_by=user.id,
        reviewed_at=datetime.now(timezone.utc) if auto_approve else None,
    )
    db.add(spot)
    db.commit()
    db.refresh(spot)
    reward = settings.credits_per_hidden_spot if spot.is_hidden else settings.credits_per_public_spot
    return {
        "spot": _serialize(spot, visible=True, hub_names=_hub_names(db, [spot]), mine=True),
        "message": (
            "Added." if auto_approve else
            f"Thanks! Once it's reviewed you'll earn {reward} unlock credit{'s' if reward != 1 else ''}."
        ),
    }


@router.patch("/spots/{spot_id}")
def edit_spot(
    spot_id: uuid.UUID,
    body: SpotEdit,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    spot = _get_spot(db, spot_id)
    is_owner = spot.submitted_by == user.id
    if not (user.is_admin or (is_owner and spot.status == "pending")):
        raise HTTPException(status_code=403, detail="You can only edit your own spots while they're waiting for review")

    changes = body.model_dump(exclude_unset=True)
    lat = changes.get("latitude", spot.latitude)
    lng = changes.get("longitude", spot.longitude)
    if not in_karnataka_bbox(lat, lng):
        raise HTTPException(status_code=422, detail="That pin is outside Karnataka")
    if "district" in changes:
        district = normalize_district(changes["district"])
        if not district:
            raise HTTPException(status_code=422, detail="Pick one of Karnataka's districts")
        changes["district"] = district
    if "photo_url" in changes and changes["photo_url"] == "":
        changes["photo_url"] = None
    if "name" in changes:
        changes["name"] = changes["name"].strip()

    for key, value in changes.items():
        setattr(spot, key, value)
    if "latitude" in changes or "longitude" in changes:
        hub = _nearest_hub(db, lat, lng)
        spot.destination_id = hub.id if hub else None
    if user.is_admin and spot.source == "osm":
        # Stop the OSM loader from overwriting hand edits on the next deploy.
        spot.extra = {**(spot.extra or {}), "curated": True}
    db.commit()
    db.refresh(spot)
    return _serialize(spot, visible=True, hub_names=_hub_names(db, [spot]), mine=is_owner)


@router.post("/spots/{spot_id}/unlock")
def unlock_spot(
    spot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    spot = _get_spot(db, spot_id)
    if spot.status != "approved":
        raise HTTPException(status_code=404, detail="Spot not found")
    unlocked, _ = _user_context(db, user, [spot.id])
    if _can_see(spot, user, unlocked):
        return {"spot": _serialize(spot, visible=True, hub_names=_hub_names(db, [spot])),
                "credits": user.unlock_credits, "spent": 0}

    # Atomic spend: only succeeds if the user still has a credit.
    res = db.execute(
        update(User).where(User.id == user.id, User.unlock_credits >= 1)
        .values(unlock_credits=User.unlock_credits - 1)
    )
    if res.rowcount == 0:
        db.rollback()
        raise HTTPException(
            status_code=402,
            detail="No unlock credits left. Share a hidden spot you know to earn 3 more!",
        )
    db.add(SpotUnlock(user_id=user.id, spot_id=spot.id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # unlocked concurrently; the rollback also refunds the credit
    db.refresh(user)
    return {"spot": _serialize(spot, visible=True, hub_names=_hub_names(db, [spot])),
            "credits": user.unlock_credits, "spent": 1}


@router.post("/spots/{spot_id}/vouch")
def vouch_spot(
    spot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    spot = _get_spot(db, spot_id)
    if spot.status != "approved":
        raise HTTPException(status_code=404, detail="Spot not found")
    unlocked, _ = _user_context(db, user, [spot.id])
    if not _can_see(spot, user, unlocked):
        raise HTTPException(status_code=403, detail="Unlock this spot first")
    if spot.submitted_by == user.id:
        raise HTTPException(status_code=400, detail="You can't vouch for your own spot")
    db.add(SpotVouch(user_id=user.id, spot_id=spot.id))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return {"vouch_count": spot.vouch_count, "already": True}
    db.execute(update(Spot).where(Spot.id == spot.id).values(vouch_count=Spot.vouch_count + 1))
    db.commit()
    db.refresh(spot)
    return {"vouch_count": spot.vouch_count, "already": False}


# ── Moderation ────────────────────────────────────────────────────────────────

@router.get("/admin/spots/pending")
def pending_spots(db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    spots = db.query(Spot).filter(Spot.status == "pending").order_by(Spot.created_at).limit(200).all()
    hubs = _hub_names(db, spots)
    users = {
        u.id: u for u in db.query(User).filter(User.id.in_({s.submitted_by for s in spots if s.submitted_by})).all()
    } if spots else {}
    out = []
    for s in spots:
        item = _serialize(s, visible=True, hub_names=hubs, mine=True)
        u = users.get(s.submitted_by)
        item["submitted_by"] = u.display_name if u else None
        out.append(item)
    return {"items": out}


@router.post("/admin/spots/{spot_id}/review")
def review_spot(
    spot_id: uuid.UUID,
    body: ReviewRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    settings = get_settings()
    spot = _get_spot(db, spot_id)
    if body.action == "approve":
        if spot.status != "approved":
            was_pending = spot.status == "pending"
            spot.status = "approved"
            spot.reviewed_at = datetime.now(timezone.utc)
            spot.review_note = body.note
            if was_pending and spot.submitted_by and spot.source == "community":
                reward = settings.credits_per_hidden_spot if spot.is_hidden else settings.credits_per_public_spot
                db.execute(
                    update(User).where(User.id == spot.submitted_by)
                    .values(unlock_credits=User.unlock_credits + reward)
                )
    elif body.action == "reject":
        spot.status = "rejected"
        spot.reviewed_at = datetime.now(timezone.utc)
        spot.review_note = body.note
    elif body.action == "feature":
        spot.featured = True
    elif body.action == "unfeature":
        spot.featured = False
    elif body.action == "make_public":
        spot.is_hidden = False
    elif body.action == "make_hidden":
        spot.is_hidden = True
    db.commit()
    db.refresh(spot)
    return _serialize(spot, visible=True, hub_names=_hub_names(db, [spot]), mine=True)
