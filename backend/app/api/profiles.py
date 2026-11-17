"""
profiles.py — public traveller profiles + "been there" / "want to go" marks.

PUT  /v1/marks                    {spot_id | destination_id, status: been|want|null,
                                   visited_on?, photo_url?, photo_lat?, photo_lng?}
GET  /v1/marks/mine               my marks, as {spots: {id: status}, destinations: {id: status}}
GET  /v1/places/destinations      the Karnataka hubs you can stamp (Coorg, Hampi...)
GET  /v1/users/{username}         public profile: stats, districts explored, passport, bucket list
GET  /v1/users/{username}/wrapped?year=2026[&month=11]   Spotify-Wrapped-style recap

Hidden spots on someone's profile stay locked for viewers who haven't
unlocked them: the same redaction as the map.
"""

import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.spots import _can_see, _check_photo_url, _hub_names, _serialize, _user_context
from app.api.trips import limiter
from app.core.karnataka import KARNATAKA_DISTRICTS, haversine_km
from app.dependencies import get_db
from app.models.destination import Destination
from app.models.place_mark import PlaceMark
from app.models.spot import Spot, SpotVouch
from app.models.user import User
from app.services.user_auth import get_current_user, get_optional_user

router = APIRouter(tags=["profiles"])


class MarkRequest(BaseModel):
    spot_id: Optional[uuid.UUID] = None
    destination_id: Optional[uuid.UUID] = None
    status: Optional[Literal["been", "want"]] = None  # null = remove
    # "been" extras
    visited_on: Optional[date] = None
    photo_url: Optional[str] = Field(default=None, max_length=500)
    # GPS from the photo's EXIF, read in the browser. Used once to decide
    # "verified" and then thrown away: never stored.
    photo_lat: Optional[float] = Field(default=None, ge=-90, le=90)
    photo_lng: Optional[float] = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def _check(self):
        if (self.spot_id is None) == (self.destination_id is None):
            raise ValueError("Send exactly one of spot_id or destination_id")
        if self.visited_on:
            today = datetime.now(timezone.utc).date()
            if self.visited_on > today + timedelta(days=1):
                raise ValueError("visited_on can't be in the future")
            if self.visited_on.year < 1950:
                raise ValueError("visited_on is too far in the past")
        self.photo_url = _check_photo_url(self.photo_url)
        return self


VERIFY_RADIUS_KM = 25.0  # photo taken this close to the place = verified stamp


def _dest_out(d: Destination) -> dict:
    return {
        "id": str(d.id),
        "name": d.name,
        "district": d.district,
        "quick_info": d.quick_info,
        "vibes": d.vibes or [],
        "latitude": d.latitude,
        "longitude": d.longitude,
    }


def _mark_extras(m: Optional[PlaceMark]) -> dict:
    if not m:
        return {"visited_on": None, "trip_photo_url": None, "photo_verified": False}
    return {
        "visited_on": m.visited_on.isoformat() if m.visited_on else None,
        "trip_photo_url": m.photo_url,
        "photo_verified": bool(m.photo_verified),
        "marked_at": m.updated_at.isoformat() if m.updated_at else None,
    }


def _mark_day(m: PlaceMark) -> date:
    """The day a stamp counts for: the visit date, else when it was stamped."""
    if m.visited_on:
        return m.visited_on
    ts = m.created_at or datetime.now(timezone.utc)
    return ts.date()


def _counts(db: Session, user_id) -> dict:
    rows = db.query(PlaceMark.status).filter(PlaceMark.user_id == user_id).all()
    c = Counter(r[0] for r in rows)
    return {"been": c.get("been", 0), "want": c.get("want", 0)}


# ── Marks ─────────────────────────────────────────────────────────────────────

@router.put("/marks")
@limiter.limit("120/minute")
def set_mark(
    request: Request,
    body: MarkRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.spot_id:
        spot = db.get(Spot, body.spot_id)
        allowed = spot and (spot.status == "approved" or spot.submitted_by == user.id or user.is_admin)
        if not allowed:
            raise HTTPException(status_code=404, detail="Spot not found")
        q = db.query(PlaceMark).filter(PlaceMark.user_id == user.id, PlaceMark.spot_id == body.spot_id)
        unlocked, _ = _user_context(db, user, [spot.id])
        # A locked hidden spot never verifies: otherwise fake photo GPS could be
        # used to find its location without unlocking it.
        place_ll = (spot.latitude, spot.longitude) if _can_see(spot, user, unlocked) else (None, None)
    else:
        dest = db.get(Destination, body.destination_id)
        if not dest or not dest.is_active:
            raise HTTPException(status_code=404, detail="Place not found")
        q = db.query(PlaceMark).filter(
            PlaceMark.user_id == user.id, PlaceMark.destination_id == body.destination_id,
        )
        place_ll = (dest.latitude, dest.longitude)

    fields = {"status": body.status, "visited_on": None, "photo_url": None, "photo_verified": False}
    if body.status == "been":
        verified = (
            body.photo_url is not None and body.photo_lat is not None and body.photo_lng is not None
            and place_ll[0] is not None
            and haversine_km(body.photo_lat, body.photo_lng, place_ll[0], place_ll[1]) <= VERIFY_RADIUS_KM
        )
        fields.update(visited_on=body.visited_on, photo_url=body.photo_url, photo_verified=verified)

    mark = q.first()
    if body.status is None:
        if mark:
            db.delete(mark)
            db.commit()
    elif mark:
        for k, v in fields.items():
            setattr(mark, k, v)
        db.commit()
    else:
        db.add(PlaceMark(user_id=user.id, spot_id=body.spot_id, destination_id=body.destination_id, **fields))
        try:
            db.commit()
        except IntegrityError:  # double click: the other request already created it
            db.rollback()
            q.update(fields)
            db.commit()
    return {**_mark_extras(q.first()), "status": body.status, "counts": _counts(db, user.id)}


@router.get("/marks/mine")
def my_marks(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(PlaceMark).filter(PlaceMark.user_id == user.id).all()
    return {
        "spots": {str(m.spot_id): m.status for m in rows if m.spot_id},
        "destinations": {str(m.destination_id): m.status for m in rows if m.destination_id},
    }


@router.get("/places/destinations")
def list_destinations(db: Session = Depends(get_db)):
    dests = (
        db.query(Destination)
        .filter(Destination.is_active == True, Destination.state == "Karnataka")  # noqa: E712
        .order_by(Destination.name)
        .all()
    )
    return {"items": [_dest_out(d) for d in dests]}


# ── Profiles ──────────────────────────────────────────────────────────────────

@router.get("/users/{username}")
def get_profile(
    username: str,
    db: Session = Depends(get_db),
    viewer: Optional[User] = Depends(get_optional_user),
):
    user = db.query(User).filter(User.username == username.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="No traveller with that username")
    is_me = bool(viewer and viewer.id == user.id)

    head = {
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "is_me": is_me,
        "is_admin": user.is_admin,
    }
    if not user.profile_public and not is_me:
        return {**head, "private": True}

    marks = (
        db.query(PlaceMark).filter(PlaceMark.user_id == user.id)
        .order_by(PlaceMark.updated_at.desc(), PlaceMark.id.desc()).all()
    )
    spot_ids = [m.spot_id for m in marks if m.spot_id]
    dest_ids = [m.destination_id for m in marks if m.destination_id]
    spots = {s.id: s for s in db.query(Spot).filter(Spot.id.in_(spot_ids)).all()} if spot_ids else {}
    dests = {d.id: d for d in db.query(Destination).filter(Destination.id.in_(dest_ids)).all()} if dest_ids else {}

    shared = (
        db.query(Spot).filter(Spot.submitted_by == user.id, Spot.status == "approved")
        .order_by(Spot.created_at.desc()).all()
    )
    all_spots = list(spots.values()) + shared
    hubs = _hub_names(db, all_spots)
    unlocked, _ = _user_context(db, viewer, [s.id for s in all_spots])
    viewer_marks = {}
    if viewer and not is_me and all_spots:
        viewer_marks = {
            sid: st for sid, st in db.query(PlaceMark.spot_id, PlaceMark.status).filter(
                PlaceMark.user_id == viewer.id, PlaceMark.spot_id.in_([s.id for s in all_spots]),
            ).all()
        }

    def spot_item(s: Spot, mark: Optional[PlaceMark]) -> dict:
        visible = _can_see(s, viewer, unlocked)
        out = _serialize(s, visible=visible, hub_names=hubs)
        out["kind"] = "spot"
        out["my_mark"] = mark.status if (is_me and mark) else viewer_marks.get(s.id)
        if mark:
            out.update(_mark_extras(mark))
            if not visible and not is_me:  # a trip photo would give a hidden spot away
                out["trip_photo_url"] = None
        return out

    lists = {"been": [], "want": []}
    districts: Counter = Counter()
    marks.sort(key=_mark_day, reverse=True)  # newest trips first
    for m in marks:
        if m.spot_id and m.spot_id in spots:
            s = spots[m.spot_id]
            if s.status != "approved" and not is_me:
                continue
            lists[m.status].append(spot_item(s, m))
            if m.status == "been":
                districts[s.district] += 1
        elif m.destination_id and m.destination_id in dests:
            d = dests[m.destination_id]
            item = {**_dest_out(d), "kind": "place", **_mark_extras(m)}
            if is_me:
                item["my_mark"] = m.status
            lists[m.status].append(item)
            if m.status == "been" and d.district:
                districts[d.district] += 1

    vouches = db.query(SpotVouch).filter(SpotVouch.user_id == user.id).count()
    return {
        **head,
        "private": False,
        "bio": user.bio,
        "home_district": user.home_district,
        "member_since": user.created_at.isoformat() if user.created_at else None,
        "profile_public": user.profile_public,
        "stats": {
            "been": len(lists["been"]),
            "want": len(lists["want"]),
            "districts_explored": len(districts),
            "districts_total": len(KARNATAKA_DISTRICTS),
            "spots_shared": len(shared),
            "vouches": vouches,
        },
        "districts": [{"name": d, "count": districts.get(d, 0)} for d in KARNATAKA_DISTRICTS],
        "been": lists["been"],
        "want": lists["want"],
        "shared": [spot_item(s, None) for s in shared],
    }


# ── Wrapped: a monthly / yearly recap you can share ───────────────────────────

PERSONALITIES = {
    "waterfall": ("Waterfall Chaser", "If it roars and it's wet, you've been there."),
    "trek": ("Peak Bagger", "Summits over sofas. Always."),
    "viewpoint": ("Sunrise Hunter", "You know where the light hits first."),
    "cafe": ("Cafe Hopper", "Filter coffee is a lifestyle, not a drink."),
    "food": ("Local Food Detective", "You eat where the locals eat."),
    "temple": ("Temple Trail Walker", "Stone, silence and stories."),
    "heritage": ("Heritage Hunter", "Every ruin has a secret, and you find it."),
    "lake": ("Lake Whisperer", "Still water, quiet mind."),
    "beach": ("Coastal Soul", "Salt in the air, sand everywhere."),
    "wildlife": ("Jungle Scout", "Quiet footsteps, wide eyes."),
    "stay": ("Homestay Connoisseur", "You travel for the hosts as much as the hills."),
    "place": ("Karnataka Explorer", "One district at a time."),
}
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December"]


def _period(year: int, month: Optional[int]) -> tuple[date, date, str]:
    if month:
        start = date(year, month, 1)
        end = date(year + (month == 12), (month % 12) + 1, 1)
        return start, end, f"{MONTH_NAMES[month - 1]} {year}"
    return date(year, 1, 1), date(year + 1, 1, 1), str(year)


@router.get("/users/{username}/wrapped")
def wrapped(
    username: str,
    year: int = Query(ge=2000, le=2100),
    month: Optional[int] = Query(default=None, ge=1, le=12),
    db: Session = Depends(get_db),
    viewer: Optional[User] = Depends(get_optional_user),
):
    user = db.query(User).filter(User.username == username.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="No traveller with that username")
    is_me = bool(viewer and viewer.id == user.id)
    if not user.profile_public and not is_me:
        raise HTTPException(status_code=403, detail="This passport is private")

    start, end, label = _period(year, month)
    all_been = db.query(PlaceMark).filter(PlaceMark.user_id == user.id, PlaceMark.status == "been").all()
    in_period = sorted([m for m in all_been if start <= _mark_day(m) < end], key=_mark_day)
    before = [m for m in all_been if _mark_day(m) < start]

    spot_ids = [m.spot_id for m in all_been if m.spot_id]
    dest_ids = [m.destination_id for m in all_been if m.destination_id]
    spots = {s.id: s for s in db.query(Spot).filter(Spot.id.in_(spot_ids)).all()} if spot_ids else {}
    dests = {d.id: d for d in db.query(Destination).filter(Destination.id.in_(dest_ids)).all()} if dest_ids else {}
    unlocked, _ = _user_context(db, viewer, list(spots))
    hubs = _hub_names(db, list(spots.values()))

    def place(m: PlaceMark) -> Optional[dict]:
        if m.spot_id in spots:
            s = spots[m.spot_id]
            visible = _can_see(s, viewer, unlocked)
            name = s.name if visible else f"A hidden {s.category}"
            extras = _mark_extras(m)
            if not visible and not is_me:  # a trip photo would give a hidden spot away
                extras["trip_photo_url"] = None
            return {"name": name, "district": s.district, "category": s.category, "locked": not visible,
                    "_ll": (s.latitude, s.longitude), "id": str(s.id), "kind": "spot", **extras}
        if m.destination_id in dests:
            d = dests[m.destination_id]
            return {"name": d.name, "district": d.district, "category": "place", "locked": False,
                    "_ll": (d.latitude, d.longitude), "id": str(d.id), "kind": "place", **_mark_extras(m)}
        return None

    places = [p for p in (place(m) for m in in_period) if p]
    seen_before = {p["district"] for p in (place(m) for m in before) if p and p["district"]}
    districts = Counter(p["district"] for p in places if p["district"])
    new_districts = sorted(d for d in districts if d not in seen_before)

    # Distance: hop from one stamped place to the next, in date order.
    km = 0.0
    pts = [p["_ll"] for p in places if p["_ll"][0] is not None]
    for a, b in zip(pts, pts[1:]):
        km += haversine_km(a[0], a[1], b[0], b[1])
    for p in places:  # exact coordinates never leave the server (hidden spots!)
        p.pop("_ll", None)

    cats = Counter(p["category"] for p in places)
    top_cat = cats.most_common(1)[0][0] if cats else None
    title, tagline = PERSONALITIES.get(top_cat or "place", PERSONALITIES["place"])

    months = Counter(_mark_day(m).month for m in in_period)
    busiest = None
    if not month and months:
        mnum, n = months.most_common(1)[0]
        busiest = {"month": MONTH_NAMES[mnum - 1], "count": n}

    # "Top X% of explorers" this period, among everyone who stamped anything.
    counts: Counter = Counter()
    for uid, sid, did, vis, created in db.query(
        PlaceMark.user_id, PlaceMark.spot_id, PlaceMark.destination_id, PlaceMark.visited_on, PlaceMark.created_at,
    ).filter(PlaceMark.status == "been").all():
        day = vis or (created.date() if created else None)
        if day and start <= day < end:
            counts[uid] += 1
    mine = counts.get(user.id, 0)
    top_percent = None
    if mine and len(counts) >= 5:
        better = sum(1 for c in counts.values() if c > mine)
        top_percent = max(1, round(100 * (better + 1) / len(counts)))

    shared = db.query(Spot).filter(
        Spot.submitted_by == user.id, Spot.status == "approved",
        Spot.created_at >= datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc),
        Spot.created_at < datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc),
    ).count()

    photos = [p for p in places if p.get("trip_photo_url")]
    return {
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "is_me": is_me,
        "period": {"year": year, "month": month, "label": label,
                   "start": start.isoformat(), "end": (end - timedelta(days=1)).isoformat()},
        "stamps": len(places),
        "verified": sum(1 for p in places if p["photo_verified"]),
        "photos": len(photos),
        "km": round(km),
        "districts": [{"name": d, "count": n} for d, n in districts.most_common()],
        "new_districts": new_districts,
        "districts_total_explored": len(seen_before | set(districts)),
        "districts_in_state": len(KARNATAKA_DISTRICTS),
        "categories": [{"category": c, "count": n} for c, n in cats.most_common()],
        "personality": {"category": top_cat, "title": title, "tagline": tagline},
        "busiest_month": busiest,
        "first": places[0] if places else None,
        "latest": places[-1] if places else None,
        "top_places": (photos + [p for p in places if not p.get("trip_photo_url")])[:9],
        "top_percent": top_percent,
        "spots_shared": shared,
    }
