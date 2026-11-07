"""The customer's profile name."""
from conftest import bearer


def test_profile_requires_login(client):
    assert client.get("/api/me").status_code == 401
    assert client.patch("/api/me", json={"name": "A"}).status_code == 401


def test_profile_name_roundtrip(client, login):
    h = bearer(login("me@x.com"))
    assert client.get("/api/me", headers=h).json() == {"email": "me@x.com", "name": None}
    r = client.patch("/api/me", json={"name": "  Alex  "}, headers=h)
    assert r.json() == {"email": "me@x.com", "name": "Alex"}
    assert client.get("/api/me", headers=h).json()["name"] == "Alex"
    assert client.patch("/api/me", json={"name": "   "}, headers=h).json()["name"] is None  # cleared
    assert client.patch("/api/me", json={"name": "x" * 61}, headers=h).status_code == 422
