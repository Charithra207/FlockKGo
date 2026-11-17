"""Reports, safety notes, password reset, email verification, Google sign-in, spam checks."""

import pytest

from app.api import accounts
from app.config import get_settings
from tests.api.test_spots import _make_admin, _signup, _spot, ctx  # noqa: F401


def _approved(client, Session, **over):
    owner_h, _ = _signup(client, f"owner{len(over)}{over.get('name', '')[:3]}@example.com".replace(" ", ""))
    admin_h, _ = _signup(client, f"admin{len(over)}{over.get('name', '')[:3]}@example.com".replace(" ", ""))
    _make_admin(Session, f"admin{len(over)}{over.get('name', '')[:3]}@example.com".replace(" ", ""))
    spot = client.post("/v1/spots", json=_spot(**over), headers=owner_h).json()["spot"]
    client.post(f"/v1/admin/spots/{spot['id']}/review", json={"action": "approve"}, headers=admin_h)
    return spot, admin_h


def test_safety_notes_are_validated_and_shown_even_when_locked(ctx):
    client, Session = ctx
    h, _ = _signup(client, "s@example.com")
    bad = client.post("/v1/spots", json=_spot(safety=["dragons"]), headers=h)
    assert bad.status_code == 422
    spot, _ = _approved(client, Session, safety=["monsoon_danger", "no_network", "monsoon_danger"])
    teaser = client.get(f"/v1/spots/{spot['id']}").json()
    assert teaser["locked"] is True and teaser["safety"] == ["monsoon_danger", "no_network"]


def test_three_reports_hide_a_spot_until_reviewed(ctx):
    client, Session = ctx
    spot, admin_h = _approved(client, Session, is_hidden=False)
    for i in range(3):
        h, _ = _signup(client, f"r{i}@example.com")
        r = client.post(f"/v1/spots/{spot['id']}/report", json={"reason": "closed", "note": f"gate locked {i}"}, headers=h)
        assert r.status_code == 200
    assert r.json()["hidden_for_review"] is True
    assert client.get("/v1/spots").json()["total"] == 0

    q = client.get("/v1/admin/reports", headers=admin_h).json()["items"]
    assert q[0]["reasons"] == {"closed": 3} and len(q[0]["notes"]) == 3
    assert client.post(f"/v1/admin/reports/{spot['id']}/resolve", json={"action": "dismiss"}, headers=admin_h).json()["status"] == "approved"
    assert client.get("/v1/spots").json()["total"] == 1
    assert client.get("/v1/admin/reports", headers=admin_h).json()["items"] == []


def test_crowded_reports_dont_hide_but_admin_can_rehide(ctx):
    client, Session = ctx
    spot, admin_h = _approved(client, Session, is_hidden=False)
    for i in range(4):
        h, _ = _signup(client, f"c{i}@example.com")
        client.post(f"/v1/spots/{spot['id']}/report", json={"reason": "crowded"}, headers=h)
    assert client.get("/v1/spots").json()["total"] == 1  # still listed
    r = client.post(f"/v1/admin/reports/{spot['id']}/resolve", json={"action": "make_hidden"}, headers=admin_h).json()
    assert r == {"status": "approved", "is_hidden": True}
    assert client.post(f"/v1/spots/{spot['id']}/report", json={"reason": "nonsense"}, headers=h).status_code == 422


def test_password_reset_link_is_single_use(ctx, monkeypatch):
    client, Session = ctx
    sent = []
    monkeypatch.setattr(accounts, "send_email", lambda to, subj, text: sent.append(text) or True)
    _signup(client, "forgetful@example.com")
    assert client.post("/v1/auth/forgot", json={"email": "nobody@example.com"}).json()["ok"] is True
    assert sent == []  # no account: nothing sent, same answer
    client.post("/v1/auth/forgot", json={"email": "Forgetful@example.com"})
    token = sent[0].split("token=")[1].split()[0]

    r = client.post("/v1/auth/reset", json={"token": token, "password": "brand-new-pass"})
    assert r.status_code == 200 and r.json()["user"]["email_verified"] is True
    assert client.post("/v1/auth/login", json={"email": "forgetful@example.com", "password": "brand-new-pass"}).status_code == 200
    # Same link again: the password changed, so it no longer works
    assert client.post("/v1/auth/reset", json={"token": token, "password": "another-pass"}).status_code == 400
    # A reset token is not a login token
    assert client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_email_verification_and_admin_reset_link(ctx, monkeypatch):
    client, Session = ctx
    sent = []
    monkeypatch.setattr(accounts, "send_email", lambda to, subj, text: sent.append(text) or True)
    monkeypatch.setattr(accounts, "email_configured", lambda: True)
    h, user = _signup(client, "v@example.com")
    assert user["email_verified"] is False and len(sent) == 1
    token = sent[0].split("token=")[1].split()[0]
    assert client.post("/v1/auth/verify", json={"token": "x.y"}).status_code == 400
    assert client.post("/v1/auth/verify", json={"token": token}).json()["verified"] is True
    assert client.get("/v1/auth/me", headers=h).json()["email_verified"] is True

    admin_h, _ = _signup(client, "boss@example.com")
    _make_admin(Session, "boss@example.com")
    assert client.post("/v1/auth/admin/reset-link", json={"email": "v@example.com"}, headers=h).status_code == 403
    link = client.post("/v1/auth/admin/reset-link", json={"email": "v@example.com"}, headers=admin_h).json()["link"]
    assert "/reset-password?token=" in link


def test_google_sign_in_creates_and_links_accounts(ctx, monkeypatch):
    client, Session = ctx
    monkeypatch.setattr(get_settings(), "google_client_id", "cid")
    claims = {"sub": "g-123", "email": "Gina@example.com", "name": "Gina R", "email_verified": "true",
              "aud": "cid", "iss": "accounts.google.com"}

    class Resp:
        status_code = 200
        def json(self):
            return claims
    monkeypatch.setattr(accounts.httpx, "get", lambda *a, **k: Resp())

    r = client.post("/v1/auth/google", json={"credential": "x"}).json()
    assert r["user"]["email"] == "gina@example.com" and r["user"]["email_verified"] is True
    again = client.post("/v1/auth/google", json={"credential": "x"}).json()
    assert again["user"]["id"] == r["user"]["id"]

    # Existing password account with the same email gets linked, not duplicated
    _signup(client, "linda@example.com", name="Linda")
    claims.update(sub="g-456", email="linda@example.com")
    assert client.post("/v1/auth/google", json={"credential": "x"}).json()["user"]["username"] == "linda"

    claims.update(aud="someone-else")
    assert client.post("/v1/auth/google", json={"credential": "x"}).status_code == 401


def test_honeypot_blocks_bots(ctx):
    client, _ = ctx
    r = client.post("/v1/auth/register", json={"email": "bot@example.com", "password": "password123",
                                               "display_name": "Bot", "website": "http://spam"})
    assert r.status_code == 400
    assert client.get("/v1/auth/config").json()["google_client_id"] is None
