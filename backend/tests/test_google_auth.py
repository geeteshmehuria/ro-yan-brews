import pytest

from app import auth
from app.db import SessionLocal
from app.models import Customer

from conftest import OWNER

CLIENT_ID = "our-client.apps.googleusercontent.com"


@pytest.fixture()
def google(monkeypatch):
    """Google login enabled; `google(**claims)` sets what the (faked) token verifies to."""
    monkeypatch.setattr(auth, "GOOGLE_CLIENT_ID", CLIENT_ID)
    seen = {}

    def _set(**claims):
        token = {"iss": "https://accounts.google.com", "aud": CLIENT_ID,
                 "email": "fan@gmail.com", "email_verified": True, "name": "Fan", **claims}

        def fake_verify(credential, request, audience):
            seen["audience"] = audience
            if audience != token["aud"]:  # what the real library does when an audience is given
                raise ValueError("Token has wrong audience")
            return token
        monkeypatch.setattr(auth.id_token, "verify_oauth2_token", fake_verify)
        return seen
    return _set


def sign_in(client):
    return client.post("/api/auth/google", json={"credential": "x" * 20})


def test_google_login_is_off_without_client_id(client, monkeypatch):
    monkeypatch.setattr(auth, "GOOGLE_CLIENT_ID", "")
    called = []
    monkeypatch.setattr(auth.id_token, "verify_oauth2_token", lambda *a: called.append(a) or
                        {"iss": "accounts.google.com", "email": OWNER, "email_verified": True})
    assert sign_in(client).status_code == 404
    assert called == []  # never verified with no audience
    assert client.get("/api/auth/mode").json()["google_client_id"] == ""


def test_google_token_for_another_site_is_rejected(client, google):
    seen = google(aud="someone-elses-site.apps.googleusercontent.com", email=OWNER)
    r = sign_in(client)
    assert r.status_code == 400 and "token" not in r.json()
    assert seen["audience"] == CLIENT_ID


@pytest.mark.parametrize("claims", [
    {"email_verified": "false"},
    {"email_verified": False},
    {"iss": "https://evil.example.com"},
    {"email": ""},
])
def test_unverified_or_foreign_google_tokens_are_rejected(client, google, claims):
    google(**claims)
    assert sign_in(client).status_code == 400


def test_missing_email_verified_counts_as_unverified(client, google, monkeypatch):
    google()
    real = auth.id_token.verify_oauth2_token

    def without_flag(*a):
        token = dict(real(*a))
        token.pop("email_verified")
        return token
    monkeypatch.setattr(auth.id_token, "verify_oauth2_token", without_flag)
    assert sign_in(client).status_code == 400


def test_google_error_details_are_not_shown_to_the_user(client, google, monkeypatch):
    google()

    def boom(*a):
        raise ValueError("internal detail: cert fetch to 10.0.0.1 failed")
    monkeypatch.setattr(auth.id_token, "verify_oauth2_token", boom)
    r = sign_in(client)
    assert r.status_code == 400 and "internal detail" not in r.text


def test_google_login_creates_customer_with_name(client, google):
    google(email="  Fan@Gmail.com ")
    r = sign_in(client)
    assert r.status_code == 200 and r.json()["is_admin"] is False
    me = client.get("/api/me", headers={"authorization": f"Bearer {r.json()['token']}"}).json()
    assert me == {"email": "fan@gmail.com", "name": "Fan"}


def test_google_login_reuses_existing_email_account(client, google, login):
    login("fan@gmail.com")  # first came in with an email code
    google()
    assert sign_in(client).status_code == 200
    with SessionLocal() as db:
        assert db.query(Customer).filter_by(email="fan@gmail.com").count() == 1


def test_google_login_as_owner_is_admin(client, google):
    google(email=OWNER)
    assert sign_in(client).json()["is_admin"] is True
