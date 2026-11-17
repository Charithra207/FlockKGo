"""Profiles + "been there" / "want to go" marks."""

from app.models.destination import Destination
from app.models.user import User
from tests.api.test_spots import _make_admin, _signup, _spot, ctx  # noqa: F401  (ctx is a fixture)


def _approved_hidden_spot(client, Session, owner_h, admin_h):
    spot = client.post("/v1/spots", json=_spot(), headers=owner_h).json()["spot"]
    client.post(f"/v1/admin/spots/{spot['id']}/review", json={"action": "approve"}, headers=admin_h)
    return spot


def _coorg_id(Session):
    db = Session()
    try:
        return str(db.query(Destination).filter(Destination.name == "Coorg").one().id)
    finally:
        db.close()


def test_signup_gets_username_and_profile_can_be_edited(ctx):
    client, _ = ctx
    h, user = _signup(client, "riya@example.com", name="Riya K")
    assert user["username"] == "riya_k"
    _, other = _signup(client, "riya2@example.com", name="Riya K")
    assert other["username"].startswith("riya_k") and other["username"] != "riya_k"

    r = client.patch("/v1/auth/me", json={"username": "Waterfall_Riya", "bio": "Monsoon chaser",
                                           "home_district": "coorg"}, headers=h)
    assert r.status_code == 200, r.text
    assert (r.json()["username"], r.json()["home_district"]) == ("waterfall_riya", "Kodagu")

    assert client.patch("/v1/auth/me", json={"username": other["username"]}, headers=h).status_code == 409
    assert client.patch("/v1/auth/me", json={"username": "a b"}, headers=h).status_code == 422
    assert client.patch("/v1/auth/me", json={"username": "admin"}, headers=h).status_code == 422
    assert client.patch("/v1/auth/me", json={"home_district": "Goa"}, headers=h).status_code == 422
    assert client.patch("/v1/auth/me", json={"avatar_url": "javascript:alert(1)"}, headers=h).status_code == 422


def test_marks_move_between_lists_and_show_on_profile(ctx):
    client, Session = ctx
    owner_h, _ = _signup(client, "owner@example.com")
    admin_h, _ = _signup(client, "admin@example.com")
    _make_admin(Session, "admin@example.com")
    spot = _approved_hidden_spot(client, Session, owner_h, admin_h)
    coorg = _coorg_id(Session)

    me_h, me = _signup(client, "me@example.com", name="Me Traveller")
    assert client.put("/v1/marks", json={"spot_id": spot["id"], "status": "want"}, headers=me_h).json()["counts"] == {"been": 0, "want": 1}
    assert client.get(f"/v1/spots/{spot['id']}", headers=me_h).json()["my_mark"] == "want"
    # Stamping a bucket-list place moves it to "been".
    r = client.put("/v1/marks", json={"spot_id": spot["id"], "status": "been"}, headers=me_h)
    assert r.json()["counts"] == {"been": 1, "want": 0}
    client.put("/v1/marks", json={"destination_id": coorg, "status": "want"}, headers=me_h)
    assert client.get("/v1/marks/mine", headers=me_h).json() == {
        "spots": {spot["id"]: "been"}, "destinations": {coorg: "want"},
    }

    prof = client.get(f"/v1/users/{me['username']}").json()
    assert prof["stats"]["been"] == 1 and prof["stats"]["want"] == 1
    assert prof["stats"]["districts_explored"] == 1
    assert next(d for d in prof["districts"] if d["name"] == "Kodagu")["count"] == 1
    assert prof["want"][0]["kind"] == "place" and prof["want"][0]["name"] == "Coorg"
    # A stranger sees the hidden spot on the profile, but still locked.
    been = prof["been"][0]
    assert been["locked"] is True and "latitude" not in been and been["name"].startswith("Hidden")
    assert "email" not in prof

    # Remove
    client.put("/v1/marks", json={"spot_id": spot["id"], "status": None}, headers=me_h)
    assert client.get(f"/v1/users/{me['username']}").json()["stats"]["been"] == 0


def test_mark_validation_and_private_profiles(ctx):
    client, Session = ctx
    h, me = _signup(client, "p@example.com", name="Private Person")
    assert client.put("/v1/marks", json={"status": "been"}, headers=h).status_code == 422
    assert client.put("/v1/marks", json={"destination_id": _coorg_id(Session), "status": "nope"}, headers=h).status_code == 422
    assert client.put("/v1/marks", json={"destination_id": _coorg_id(Session), "status": "been"}).status_code == 401
    assert client.put("/v1/marks", json={"spot_id": "00000000-0000-0000-0000-000000000000", "status": "been"},
                      headers=h).status_code == 404

    client.put("/v1/marks", json={"destination_id": _coorg_id(Session), "status": "been"}, headers=h)
    client.patch("/v1/auth/me", json={"profile_public": False}, headers=h)
    stranger = client.get(f"/v1/users/{me['username']}").json()
    assert stranger["private"] is True and "been" not in stranger
    mine = client.get(f"/v1/users/{me['username']}", headers=h).json()
    assert mine["is_me"] is True and mine["stats"]["been"] == 1
    assert client.get("/v1/users/nobody_here").status_code == 404


def test_pending_spots_cannot_be_marked_by_others(ctx):
    client, Session = ctx
    owner_h, _ = _signup(client, "o2@example.com")
    spot = client.post("/v1/spots", json=_spot(), headers=owner_h).json()["spot"]  # pending
    other_h, _ = _signup(client, "x@example.com")
    assert client.put("/v1/marks", json={"spot_id": spot["id"], "status": "want"}, headers=other_h).status_code == 404
    assert client.put("/v1/marks", json={"spot_id": spot["id"], "status": "want"}, headers=owner_h).status_code == 200


def test_old_accounts_get_a_username_on_login(ctx):
    client, Session = ctx
    _signup(client, "old@example.com", name="Old Timer")
    db = Session()
    db.query(User).filter(User.email == "old@example.com").update({"username": None})
    db.commit()
    db.close()
    r = client.post("/v1/auth/login", json={"email": "old@example.com", "password": "password123"})
    assert r.json()["user"]["username"] == "old_timer"


def test_stamp_with_photo_date_and_gps_verification(ctx):
    client, Session = ctx
    h, me = _signup(client, "snap@example.com", name="Snap Happy")
    photo = client.post("/v1/photos", files={"file": ("a.jpg", bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"0" * 200, "image/jpeg")},
                        headers=h).json()["url"]
    coorg = _coorg_id(Session)
    r = client.put("/v1/marks", json={"destination_id": coorg, "status": "been", "visited_on": "2026-03-14",
                                      "photo_url": photo, "photo_lat": 12.43, "photo_lng": 75.74}, headers=h)
    assert r.status_code == 200, r.text
    assert (r.json()["visited_on"], r.json()["photo_verified"]) == ("2026-03-14", True)
    # Far-away photo: stamped, but not verified
    r = client.put("/v1/marks", json={"destination_id": coorg, "status": "been", "photo_url": photo,
                                      "photo_lat": 15.0, "photo_lng": 76.0}, headers=h)
    assert r.json()["photo_verified"] is False
    # Future date and bad photo URL are rejected
    assert client.put("/v1/marks", json={"destination_id": coorg, "status": "been", "visited_on": "2999-01-01"},
                      headers=h).status_code == 422
    assert client.put("/v1/marks", json={"destination_id": coorg, "status": "been", "photo_url": "http://x"},
                      headers=h).status_code == 422
    # Moving to the bucket list clears the visit details
    r = client.put("/v1/marks", json={"destination_id": coorg, "status": "want", "visited_on": "2026-01-01"}, headers=h)
    assert (r.json()["visited_on"], r.json()["trip_photo_url"]) == (None, None)


def test_locked_hidden_spot_never_verifies(ctx):
    client, Session = ctx
    owner_h, _ = _signup(client, "own@example.com")
    admin_h, _ = _signup(client, "adm@example.com")
    _make_admin(Session, "adm@example.com")
    spot = _approved_hidden_spot(client, Session, owner_h, admin_h)
    h, _ = _signup(client, "prober@example.com")
    photo = client.post("/v1/photos", files={"file": ("a.jpg", bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"0" * 200, "image/jpeg")},
                        headers=h).json()["url"]
    r = client.put("/v1/marks", json={"spot_id": spot["id"], "status": "been", "photo_url": photo,
                                      "photo_lat": 12.45, "photo_lng": 75.70}, headers=h)
    assert r.json()["photo_verified"] is False


def test_wrapped_recap(ctx):
    client, Session = ctx
    owner_h, _ = _signup(client, "own2@example.com")
    admin_h, _ = _signup(client, "adm2@example.com")
    _make_admin(Session, "adm2@example.com")
    spot = _approved_hidden_spot(client, Session, owner_h, admin_h)
    h, me = _signup(client, "wrap@example.com", name="Wrap Star")
    coorg = _coorg_id(Session)
    client.put("/v1/marks", json={"destination_id": coorg, "status": "been", "visited_on": "2026-02-10"}, headers=h)
    client.put("/v1/marks", json={"spot_id": spot["id"], "status": "been", "visited_on": "2026-07-01"}, headers=h)

    y = client.get(f"/v1/users/{me['username']}/wrapped?year=2026").json()
    assert y["stamps"] == 2 and y["period"]["label"] == "2026"
    assert y["new_districts"] == ["Kodagu"] and y["km"] >= 1
    assert y["first"]["name"] == "Coorg"
    assert y["latest"]["locked"] is True and y["latest"]["name"] == "A hidden viewpoint"
    assert "lat" not in str(y["top_places"]) and "_ll" not in str(y)
    assert y["busiest_month"]["count"] == 1

    feb = client.get(f"/v1/users/{me['username']}/wrapped?year=2026&month=2").json()
    assert feb["stamps"] == 1 and feb["period"]["label"] == "February 2026"
    jul = client.get(f"/v1/users/{me['username']}/wrapped?year=2026&month=7").json()
    assert jul["new_districts"] == []  # Kodagu was already stamped in February
    assert client.get(f"/v1/users/{me['username']}/wrapped?year=2025").json()["stamps"] == 0


def test_trip_photo_of_locked_spot_is_hidden_from_strangers(ctx):
    client, Session = ctx
    owner_h, _ = _signup(client, "own3@example.com")
    admin_h, _ = _signup(client, "adm3@example.com")
    _make_admin(Session, "adm3@example.com")
    spot = _approved_hidden_spot(client, Session, owner_h, admin_h)
    h, me = _signup(client, "pic@example.com", name="Pic Taker")
    photo = client.post("/v1/photos", files={"file": ("a.jpg", bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"0" * 200, "image/jpeg")},
                        headers=h).json()["url"]
    client.put("/v1/marks", json={"spot_id": spot["id"], "status": "been", "photo_url": photo}, headers=h)
    stranger = client.get(f"/v1/users/{me['username']}").json()["been"][0]
    assert stranger["locked"] is True and stranger["trip_photo_url"] is None
    mine = client.get(f"/v1/users/{me['username']}", headers=h).json()["been"][0]
    assert mine["trip_photo_url"] == photo
    from datetime import date
    year = client.get(f"/v1/users/{me['username']}/wrapped?year={date.today().year}").json()
    assert year["stamps"] == 1 and year["photos"] == 0  # stranger can't see the trip photo
    assert client.get(f"/v1/users/{me['username']}/wrapped?year=2026&month=13").status_code == 422
