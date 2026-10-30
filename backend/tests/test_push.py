from app import push
from tests.conftest import OWNER, bearer, place

TOKEN = "fcm-token-" + "a" * 40


class FakeResponse:
    def __init__(self, status_code=200, text="{}"):
        self.status_code, self.text = status_code, text


class FakeSession:
    def __init__(self, response=None):
        self.sent, self.response = [], response or FakeResponse()

    def post(self, url, json, timeout):
        self.sent.append(json["message"])
        return self.response


def fake_fcm(monkeypatch, response=None) -> FakeSession:
    session = FakeSession(response)
    monkeypatch.setattr(push, "_KEY", "{}")
    monkeypatch.setattr(push, "_client", lambda: (session, "https://fcm.test"))
    return session


def test_only_owner_can_register_a_phone(client, login):
    r = client.post("/api/admin/push-token", json={"token": TOKEN}, headers=bearer(login()))
    assert r.status_code == 403
    r = client.post("/api/admin/push-token", json={"token": TOKEN}, headers=bearer(login(OWNER)))
    assert r.status_code == 200
    # registering again is fine (the app does it on every launch)
    assert client.post("/api/admin/push-token", json={"token": TOKEN}, headers=bearer(login(OWNER))).status_code == 200


def test_new_order_and_cancel_push_to_owner(client, login, make_item, monkeypatch):
    fcm = fake_fcm(monkeypatch)
    client.post("/api/admin/push-token", json={"token": TOKEN}, headers=bearer(login(OWNER)))
    customer = login()
    order = place(client, customer, make_item(full=80), qty=2).json()

    assert len(fcm.sent) == 1
    msg = fcm.sent[0]
    assert msg["token"] == TOKEN
    assert msg["notification"]["title"] == f"New order #{order['order_number']} · ₹160"
    assert "Oreo Shake ×2" in msg["notification"]["body"]
    assert msg["android"]["priority"] == "high"

    client.post(f"/api/orders/{order['id']}/cancel", headers=bearer(customer))
    assert fcm.sent[1]["notification"]["title"] == f"Order #{order['order_number']} cancelled"


def test_logged_out_phone_gets_no_push(client, login, make_item, monkeypatch):
    fcm = fake_fcm(monkeypatch)
    owner = login(OWNER)
    client.post("/api/admin/push-token", json={"token": TOKEN}, headers=bearer(owner))
    client.post("/api/admin/push-token/remove", json={"token": TOKEN}, headers=bearer(owner))
    place(client, login(), make_item())
    assert fcm.sent == []


def test_dead_token_is_dropped_and_order_still_works(client, login, make_item, monkeypatch):
    fcm = fake_fcm(monkeypatch, FakeResponse(404, '{"error": {"status": "NOT_FOUND"}}'))
    client.post("/api/admin/push-token", json={"token": TOKEN}, headers=bearer(login(OWNER)))
    item = make_item()
    assert place(client, login(), item).status_code == 201
    assert place(client, login("other@gmail.com"), item).status_code == 201
    assert len(fcm.sent) == 1  # the token was deleted after the first 404
