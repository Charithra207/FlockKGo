"""
Tests for accounts + the "give a spot, get a spot" economy.

Uses an in-memory SQLite DB and a minimal app with just the two routers.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api import accounts, photos, profiles, spots
from app.api.trips import limiter
from app.db.database import Base
from app.dependencies import get_db
from app.models.destination import Destination
from app.models.user import User

COORG = (12.42149, 75.73875)


@pytest.fixture
def ctx():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    db = Session()
    db.add(Destination(
        name="Coorg", country="India", state="Karnataka", district="Kodagu",
        latitude=COORG[0], longitude=COORG[1], budget_midpoint=8000,
        budget_flexibility=0.7, vibes=["nature"], climate="warm", activity_level="relaxed",
    ))
    db.commit()
    db.close()

    api = FastAPI()
    api.state.limiter = limiter
    limiter.enabled = False
    api.include_router(accounts.router, prefix="/v1")
    api.include_router(spots.router, prefix="/v1")
    api.include_router(photos.router, prefix="/v1")
    api.include_router(profiles.router, prefix="/v1")

    def _db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    api.dependency_overrides[get_db] = _db
    yield TestClient(api), Session
    limiter.enabled = True


def _signup(client, email, name="A"):
    r = client.post("/v1/auth/register", json={"email": email, "password": "password123", "display_name": name})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user"]


def _make_admin(Session, email):
    db = Session()
    u = db.query(User).filter(User.email == email).first()
    u.is_admin = True
    db.commit()
    db.close()


def _spot(**over):
    body = {
        "name": "Secret Coffee Estate Viewpoint", "category": "viewpoint",
        "latitude": 12.45, "longitude": 75.70, "district": "Coorg",
        "description": "Sunrise over the mist", "access_notes": "Ask at the estate gate",
        "best_months": [10, 11, 12], "is_hidden": True,
    }
    body.update(over)
    return body


def test_register_login_me(ctx):
    client, _ = ctx
    headers, user = _signup(client, "a@example.com")
    assert user["unlock_credits"] == 1  # signup bonus
    assert client.get("/v1/auth/me", headers=headers).json()["email"] == "a@example.com"
    assert client.post("/v1/auth/login", json={"email": "A@example.com", "password": "password123"}).status_code == 200
    assert client.post("/v1/auth/login", json={"email": "a@example.com", "password": "nope-nope"}).status_code == 401
    assert client.post("/v1/auth/register", json={
        "email": "a@example.com", "password": "password123", "display_name": "x"}).status_code == 409


def test_bad_token_is_rejected(ctx):
    client, _ = ctx
    assert client.get("/v1/auth/me", headers={"Authorization": "Bearer abc.def"}).status_code == 401


def test_full_give_to_get_loop(ctx):
    client, Session = ctx
    giver_h, _ = _signup(client, "giver@example.com")
    taker_h, _ = _signup(client, "taker@example.com")
    admin_h, _ = _signup(client, "admin@example.com")
    _make_admin(Session, "admin@example.com")

    # Giver submits a hidden spot -> pending, linked to the Coorg hub, district normalised
    r = client.post("/v1/spots", json=_spot(), headers=giver_h)
    assert r.status_code == 201, r.text
    spot = r.json()["spot"]
    assert spot["status"] == "pending"
    assert spot["district"] == "Kodagu"
    assert spot["destination"] == "Coorg"

    # Pending spots aren't listed publicly
    assert client.get("/v1/spots").json()["total"] == 0

    # Admin approves -> giver earns 3 credits (1 signup + 3)
    assert client.get("/v1/admin/spots/pending", headers=admin_h).json()["items"][0]["id"] == spot["id"]
    assert client.get("/v1/admin/spots/pending", headers=giver_h).status_code == 403
    r = client.post(f"/v1/admin/spots/{spot['id']}/review", json={"action": "approve"}, headers=admin_h)
    assert r.json()["status"] == "approved"
    assert client.get("/v1/auth/me", headers=giver_h).json()["unlock_credits"] == 4
    # Approving twice doesn't pay twice
    client.post(f"/v1/admin/spots/{spot['id']}/review", json={"action": "approve"}, headers=admin_h)
    assert client.get("/v1/auth/me", headers=giver_h).json()["unlock_credits"] == 4

    # Taker sees only a teaser: no name, exact coords, description or directions
    teaser = client.get("/v1/spots", headers=taker_h).json()["items"][0]
    assert teaser["locked"] is True
    assert teaser["name"] == "Hidden viewpoint near Coorg"
    for secret in ("latitude", "longitude", "description", "access_notes", "photo_url"):
        assert secret not in teaser
    assert teaser["approx_latitude"] == 12.4
    # Anonymous visitors also get the teaser
    assert client.get(f"/v1/spots/{spot['id']}").json()["locked"] is True
    # Hidden names are not searchable
    assert client.get("/v1/spots", params={"q": "Secret"}).json()["total"] == 0

    # Giver always sees their own spot
    assert client.get(f"/v1/spots/{spot['id']}", headers=giver_h).json()["locked"] is False

    # Can't vouch before unlocking
    assert client.post(f"/v1/spots/{spot['id']}/vouch", headers=taker_h).status_code == 403

    # Taker spends the signup credit
    r = client.post(f"/v1/spots/{spot['id']}/unlock", headers=taker_h)
    assert r.status_code == 200
    assert r.json()["credits"] == 0 and r.json()["spent"] == 1
    assert r.json()["spot"]["name"] == "Secret Coffee Estate Viewpoint"
    assert r.json()["spot"]["latitude"] == 12.45
    # Unlocking again is free
    assert client.post(f"/v1/spots/{spot['id']}/unlock", headers=taker_h).json()["spent"] == 0

    # Vouch once; second vouch is a no-op; can't vouch own spot
    assert client.post(f"/v1/spots/{spot['id']}/vouch", headers=taker_h).json() == {"vouch_count": 1, "already": False}
    assert client.post(f"/v1/spots/{spot['id']}/vouch", headers=taker_h).json()["already"] is True
    assert client.post(f"/v1/spots/{spot['id']}/vouch", headers=giver_h).status_code == 400

    mine = client.get("/v1/spots/mine", headers=taker_h).json()
    assert [s["id"] for s in mine["unlocked"]] == [spot["id"]]


def test_unlock_without_credits_is_402(ctx):
    client, Session = ctx
    admin_h, _ = _signup(client, "admin@example.com")
    _make_admin(Session, "admin@example.com")
    ids = [
        client.post("/v1/spots", json=_spot(name=f"Spot {i}", latitude=12.45 + i * 0.01), headers=admin_h).json()["spot"]["id"]
        for i in range(2)
    ]
    user_h, _ = _signup(client, "u@example.com")
    assert client.post(f"/v1/spots/{ids[0]}/unlock", headers=user_h).status_code == 200
    r = client.post(f"/v1/spots/{ids[1]}/unlock", headers=user_h)
    assert r.status_code == 402
    assert "Share a hidden spot" in r.json()["detail"]


def test_submission_validation(ctx):
    client, _ = ctx
    h, _ = _signup(client, "v@example.com")
    # Outside Karnataka (Chennai)
    assert client.post("/v1/spots", json=_spot(latitude=13.08, longitude=80.27), headers=h).status_code == 422
    assert client.post("/v1/spots", json=_spot(district="Goa"), headers=h).status_code == 422
    assert client.post("/v1/spots", json=_spot(category="nightclub"), headers=h).status_code == 422
    assert client.post("/v1/spots", json=_spot(best_months=[13]), headers=h).status_code == 422
    assert client.post("/v1/spots", json=_spot(photo_url="http://x.com/a.jpg"), headers=h).status_code == 422
    assert client.post("/v1/spots", json=_spot()).status_code == 401  # must log in


def test_duplicates_and_pending_limit(ctx):
    client, _ = ctx
    h, _ = _signup(client, "d@example.com")
    assert client.post("/v1/spots", json=_spot(), headers=h).status_code == 201
    # ~50 m away, same category -> duplicate
    assert client.post("/v1/spots", json=_spot(name="Other", latitude=12.4504), headers=h).status_code == 409
    # Same name nearby -> duplicate
    assert client.post("/v1/spots", json=_spot(category="trek", latitude=12.455), headers=h).status_code == 409
    for i in range(4):
        r = client.post("/v1/spots", json=_spot(name=f"N{i}", latitude=12.5 + i * 0.05), headers=h)
        assert r.status_code == 201, r.text
    # 6th pending submission is refused (max 5)
    assert client.post("/v1/spots", json=_spot(name="N9", latitude=13.2), headers=h).status_code == 429


def test_public_spots_are_visible_and_near_search(ctx):
    client, Session = ctx
    admin_h, _ = _signup(client, "admin@example.com")
    _make_admin(Session, "admin@example.com")
    client.post("/v1/spots", json=_spot(name="Ainmane Cafe", category="cafe", is_hidden=False,
                                        latitude=12.4243, longitude=75.7373), headers=admin_h)
    client.post("/v1/spots", json=_spot(name="Far cafe", category="cafe", is_hidden=False,
                                        latitude=15.33, longitude=76.46, district="Vijayanagara"), headers=admin_h)
    r = client.get("/v1/spots", params={"category": "cafe", "lat": COORG[0], "lng": COORG[1], "radius_km": 10}).json()
    assert r["total"] == 1
    item = r["items"][0]
    assert item["locked"] is False and item["name"] == "Ainmane Cafe"
    assert item["distance_km"] < 1
    assert client.get("/v1/spots", params={"q": "ainmane"}).json()["total"] == 1

    meta = client.get("/v1/spots/meta").json()
    assert meta["counts"]["cafe"] == 2
    assert meta["hubs"][0]["name"] == "Coorg"


JPEG = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"0" * 200


def test_photo_upload_and_serve(ctx):
    client, _ = ctx
    h, _ = _signup(client, "p@example.com")
    assert client.post("/v1/photos", files={"file": ("a.jpg", JPEG, "image/jpeg")}).status_code == 401
    r = client.post("/v1/photos", files={"file": ("a.jpg", JPEG, "image/jpeg")}, headers=h)
    assert r.status_code == 201
    url = r.json()["url"]
    got = client.get(url)
    assert got.status_code == 200 and got.content == JPEG
    assert got.headers["content-type"] == "image/jpeg"
    # Not an image, even though it claims to be
    bad = client.post("/v1/photos", files={"file": ("x.jpg", b"<script>", "image/jpeg")}, headers=h)
    assert bad.status_code == 415
    big = client.post("/v1/photos", files={"file": ("b.jpg", JPEG + b"0" * 1_600_000, "image/jpeg")}, headers=h)
    assert big.status_code == 413
    # Uploaded photo can be attached to a spot; random http links can't
    assert client.post("/v1/spots", json=_spot(photo_url=url), headers=h).status_code == 201
    assert client.post("/v1/spots", json=_spot(name="Z", latitude=13.0, photo_url="/v1/photos/../etc"), headers=h).status_code == 422


def test_edit_rules(ctx):
    client, Session = ctx
    owner_h, _ = _signup(client, "o@example.com")
    other_h, _ = _signup(client, "x@example.com")
    admin_h, _ = _signup(client, "admin@example.com")
    _make_admin(Session, "admin@example.com")
    sid = client.post("/v1/spots", json=_spot(), headers=owner_h).json()["spot"]["id"]

    # Owner can edit while pending; partial update keeps other fields
    r = client.patch(f"/v1/spots/{sid}", json={"description": "Better words", "best_months": [12, 1]}, headers=owner_h)
    assert r.status_code == 200
    assert r.json()["description"] == "Better words" and r.json()["best_months"] == [1, 12]
    assert r.json()["name"] == "Secret Coffee Estate Viewpoint"
    # Others can't
    assert client.patch(f"/v1/spots/{sid}", json={"name": "Mine now"}, headers=other_h).status_code == 403
    # Validation still applies
    assert client.patch(f"/v1/spots/{sid}", json={"latitude": 13.08, "longitude": 80.27}, headers=owner_h).status_code == 422
    assert client.patch(f"/v1/spots/{sid}", json={"category": "nightclub"}, headers=owner_h).status_code == 422

    client.post(f"/v1/admin/spots/{sid}/review", json={"action": "approve"}, headers=admin_h)
    # After approval only admins can edit
    assert client.patch(f"/v1/spots/{sid}", json={"name": "New"}, headers=owner_h).status_code == 403
    r = client.patch(f"/v1/spots/{sid}", json={"name": "Renamed by admin", "photo_url": ""}, headers=admin_h)
    assert r.status_code == 200 and r.json()["name"] == "Renamed by admin" and r.json()["photo_url"] is None


def test_admin_emails_setting_promotes_on_signup_and_admin_request(ctx, monkeypatch):
    from app.config import get_settings

    client, _ = ctx
    regular_h, _ = _signup(client, "early@example.com")  # signed up before being listed
    monkeypatch.setattr(get_settings(), "admin_emails", " Boss@Example.com , early@example.com")

    _, boss = _signup(client, "boss@example.com")
    assert boss["is_admin"] is True
    # Existing account: promoted on its first admin request, no re-login needed.
    assert client.get("/v1/admin/spots/pending", headers=regular_h).status_code == 200
    assert client.get("/v1/auth/me", headers=regular_h).json()["is_admin"] is True

    _, other = _signup(client, "someone@example.com")
    assert other["is_admin"] is False
