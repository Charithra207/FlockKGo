"""Trip <-> spots <-> passport: group stamps, local's picks, seasons, multi filters."""

from app.models.destination import Destination
from app.models.recommendation import Recommendation
from app.models.spot import Spot
from app.models.trip import Trip
from app.models.user import User
from tests.api.test_spots import _make_admin, _signup, _spot, ctx  # noqa: F401


def _trip_with_pick(Session, name="Coorg"):
    db = Session()
    trip = Trip(name="Gang trip", organizer_name="O", organizer_email="o@example.com", trip_month="Jul", duration_days=3)
    db.add(trip)
    db.flush()
    db.add(Recommendation(trip_id=trip.id, destination_name=name, rank=1, ml_score=0.9))
    db.add(Recommendation(trip_id=trip.id, destination_name="Nowhere", rank=2, ml_score=0.5))
    db.commit()
    tid = str(trip.id)
    db.close()
    return tid


def test_trip_destination_join_and_group_stamp(ctx):
    client, Session = ctx
    tid = _trip_with_pick(Session)
    d = client.get(f"/v1/trips/{tid}/destination").json()
    assert d["name"] == "Coorg" and d["destination"]["district"] == "Kodagu" and d["decided_by_vote"] is False

    a_h, a = _signup(client, "a@example.com", name="Asha")
    b_h, b = _signup(client, "b@example.com", name="Bhavya")
    assert client.post(f"/v1/trips/{tid}/join").status_code == 401
    client.post(f"/v1/trips/{tid}/join", headers=a_h)
    assert client.post(f"/v1/trips/{tid}/join", headers=a_h).json()["members"] == 1  # idempotent
    client.post(f"/v1/trips/{tid}/join", headers=b_h)

    client.put("/v1/marks", json={"destination_id": d["destination"]["id"], "status": "been", "visited_on": "2026-07-20"}, headers=a_h)
    mem = client.get(f"/v1/trips/{tid}/memories", headers=a_h).json()
    assert mem["me_joined"] is True and mem["stamped_count"] == 1
    by = {m["username"]: m for m in mem["members"]}
    assert by[a["username"]]["stamped"] and by[a["username"]]["visited_on"] == "2026-07-20"
    assert not by[b["username"]]["stamped"]
    assert "email" not in str(mem)

    client.delete(f"/v1/trips/{tid}/join", headers=b_h)
    assert len(client.get(f"/v1/trips/{tid}/memories").json()["members"]) == 1
    assert client.get("/v1/trips/00000000-0000-0000-0000-000000000000/memories").status_code == 404


def test_locals_pick_ranks_first_and_filters(ctx):
    client, Session = ctx
    admin_h, _ = _signup(client, "adm@example.com")
    _make_admin(Session, "adm@example.com")
    local_h, _ = _signup(client, "local@example.com", name="Kodagu Local")
    client.patch("/v1/auth/me", json={"home_district": "Kodagu"}, headers=local_h)
    tourist_h, _ = _signup(client, "tour@example.com", name="Tourist")

    t = client.post("/v1/spots", json=_spot(name="Tourist Falls", category="waterfall", is_hidden=False, latitude=12.30, longitude=75.80), headers=tourist_h).json()["spot"]
    l = client.post("/v1/spots", json=_spot(name="Local Falls", category="waterfall", is_hidden=False, latitude=12.60, longitude=75.60), headers=local_h).json()["spot"]
    for s in (t, l):
        client.post(f"/v1/admin/spots/{s['id']}/review", json={"action": "approve"}, headers=admin_h)

    items = client.get("/v1/spots?category=waterfall").json()["items"]
    assert [i["name"] for i in items] == ["Local Falls", "Tourist Falls"]
    assert items[0]["locals_pick"] is True and items[1]["locals_pick"] is False
    assert client.get(f"/v1/spots/{l['id']}").json()["locals_pick"] is True

    # Seasons: waterfalls default to Jun-Oct; this one has best_months Oct-Dec from _spot()
    assert client.get("/v1/spots?in_season=7").json()["total"] == 0
    assert client.get("/v1/spots?in_season=11").json()["total"] == 2
    db = Session()
    db.query(Spot).filter(Spot.name == "Local Falls").update({"best_months": []})
    db.commit(); db.close()
    assert [i["name"] for i in client.get("/v1/spots?in_season=7").json()["items"]] == ["Local Falls"]

    # Several categories / districts at once
    assert client.get("/v1/spots?category=waterfall,cafe").json()["total"] == 2
    assert client.get("/v1/spots?district=Kodagu,Hassan").json()["total"] == 2
    assert client.get("/v1/spots?district=Hassan").json()["total"] == 0
