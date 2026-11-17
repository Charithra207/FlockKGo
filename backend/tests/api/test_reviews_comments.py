"""Spot reviews (with photos) and trip notes."""

from tests.api.test_connect import _trip_with_pick
from tests.api.test_spots import _make_admin, _signup, _spot, ctx  # noqa: F401


def _photo(client, h):
    return client.post("/v1/photos", files={"file": ("a.jpg", bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"0" * 200, "image/jpeg")},
                       headers=h).json()["url"]


def test_reviews_need_access_and_average(ctx):
    client, Session = ctx
    owner_h, _ = _signup(client, "owner@example.com")
    admin_h, _ = _signup(client, "admin@example.com")
    _make_admin(Session, "admin@example.com")
    spot = client.post("/v1/spots", json=_spot(), headers=owner_h).json()["spot"]  # hidden
    client.post(f"/v1/admin/spots/{spot['id']}/review", json={"action": "approve"}, headers=admin_h)

    a_h, _ = _signup(client, "a@example.com", name="Anu")
    # Locked: can't read or write reviews
    assert client.get(f"/v1/spots/{spot['id']}/reviews", headers=a_h).status_code == 403
    assert client.put(f"/v1/spots/{spot['id']}/reviews", json={"rating": 5}, headers=a_h).status_code == 403
    client.post(f"/v1/spots/{spot['id']}/unlock", headers=a_h)

    r = client.put(f"/v1/spots/{spot['id']}/reviews", json={"rating": 5, "text": " Magic at sunrise ",
                   "photos": [_photo(client, a_h)], "visited_month": "2026-10"}, headers=a_h)
    assert r.status_code == 200 and r.json()["text"] == "Magic at sunrise" and len(r.json()["photos"]) == 1
    client.put(f"/v1/spots/{spot['id']}/reviews", json={"rating": 4}, headers=a_h)  # update, not duplicate
    out = client.get(f"/v1/spots/{spot['id']}/reviews", headers=a_h).json()
    assert out["count"] == 1 and out["average"] == 4.0 and out["items"][0]["mine"] is True
    assert "email" not in str(out)

    assert client.put(f"/v1/spots/{spot['id']}/reviews", json={"rating": 6}, headers=a_h).status_code == 422
    assert client.put(f"/v1/spots/{spot['id']}/reviews", json={"rating": 3, "photos": ["http://evil"]}, headers=a_h).status_code == 422
    assert client.put(f"/v1/spots/{spot['id']}/reviews", json={"rating": 3, "visited_month": "July"}, headers=a_h).status_code == 422
    assert client.put(f"/v1/spots/{spot['id']}/reviews", json={"rating": 5}, headers=owner_h).status_code == 400
    client.delete(f"/v1/spots/{spot['id']}/reviews", headers=a_h)
    assert client.get(f"/v1/spots/{spot['id']}/reviews", headers=a_h).json()["count"] == 0


def test_trip_comments(ctx):
    client, Session = ctx
    tid = _trip_with_pick(Session)
    assert client.post(f"/v1/trips/{tid}/comments", json={"text": "hi"}).status_code == 422  # needs a name
    client.post(f"/v1/trips/{tid}/comments", json={"text": "Who's driving?", "author_name": "Ravi"})
    h, _ = _signup(client, "m@example.com", name="Meera")
    client.post(f"/v1/trips/{tid}/comments", json={"text": "Me!", "author_name": "ignored"}, headers=h)
    items = client.get(f"/v1/trips/{tid}/comments").json()["items"]
    assert [(i["author_name"], i["text"]) for i in items] == [("Ravi", "Who's driving?"), ("Meera", "Me!")]
    assert items[1]["username"] == "meera"
    newer = client.get(f"/v1/trips/{tid}/comments?after={items[0]['id']}").json()["items"]
    assert [i["text"] for i in newer] == ["Me!"]
