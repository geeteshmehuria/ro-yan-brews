from app import auth, push
from app.db import SessionLocal
from app.models import PushToken, TLog

from conftest import OWNER, bearer, place

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


def test_no_push_without_firebase_key(client, login, make_item, monkeypatch):
    fcm = fake_fcm(monkeypatch)
    monkeypatch.setattr(push, "_KEY", "")
    client.post("/api/admin/push-token", json={"token": TOKEN}, headers=bearer(login(OWNER)))
    assert place(client, login(), make_item()).status_code == 201
    assert fcm.sent == []


def test_phone_of_a_removed_owner_gets_no_push(client, login, make_item, monkeypatch):
    fcm = fake_fcm(monkeypatch)
    client.post("/api/admin/push-token", json={"token": TOKEN}, headers=bearer(login(OWNER)))
    monkeypatch.setattr(auth, "ADMIN_EMAILS", {"new-owner@royan.test"})  # ADMIN_EMAIL changed
    place(client, login(), make_item())
    assert fcm.sent == []


def test_fcm_outage_is_logged_and_never_breaks_the_order(client, login, make_item, monkeypatch):
    session = fake_fcm(monkeypatch)

    def down(url, json, timeout):
        raise ConnectionError("fcm unreachable")
    session.post = down
    client.post("/api/admin/push-token", json={"token": TOKEN}, headers=bearer(login(OWNER)))
    assert place(client, login(), make_item()).status_code == 201
    with SessionLocal() as db:
        row = db.query(TLog).filter_by(method="TASK", path="push").one()
        assert "fcm unreachable" in row.error
        assert db.query(PushToken).count() == 1  # an outage is not a dead token


# ---------------- customers ----------------

PHONE = "fcm-phone-" + "b" * 40


def register(client, token, phone=PHONE):
    r = client.post("/api/push-token", json={"token": phone}, headers=bearer(token))
    assert r.status_code == 200
    return r


def test_customer_gets_their_order_progress(client, login, make_item, monkeypatch):
    fcm = fake_fcm(monkeypatch)
    owner, customer = bearer(login(OWNER)), login("ravi@gmail.com")
    register(client, customer)
    order = place(client, customer, make_item(full=85), qty=2).json()
    assert fcm.sent == []  # placing it: no push to the customer (and no owner phone registered)
    titles = []
    for status in ("preparing", "ready", "completed"):
        client.patch(f"/api/admin/orders/{order['id']}/status", json={"status": status}, headers=owner)
        msg = fcm.sent[-1]
        assert msg["token"] == PHONE and msg["data"] == {"order_id": str(order["id"]), "kind": status}
        assert msg["android"]["notification"]["channel_id"] == push.CUSTOMER_CHANNEL_ID
        assert msg["android"]["notification"]["tag"] == f"my-order-{order['id']}"  # replaces the last one
        titles.append(msg["notification"]["title"])
    assert len(fcm.sent) == 3
    assert titles[1] == f"🎉 Order #{order['order_number']} is ready!"
    assert "₹170" in fcm.sent[1]["notification"]["body"]


def test_customer_is_told_when_the_stall_cancels(client, login, make_item, monkeypatch):
    fcm = fake_fcm(monkeypatch)
    owner, customer = bearer(login(OWNER)), login()
    register(client, customer)
    order = place(client, customer, make_item()).json()
    client.patch(f"/api/admin/orders/{order['id']}/status", json={"status": "cancelled"}, headers=owner)
    assert fcm.sent[-1]["data"]["kind"] == "cancelled"
    assert "cancelled" in fcm.sent[-1]["notification"]["title"]


def test_customer_cancelling_themselves_only_alerts_the_owner(client, login, make_item, monkeypatch):
    fcm = fake_fcm(monkeypatch)
    owner, customer = login(OWNER), login()
    register(client, owner, TOKEN)
    register(client, customer)
    order = place(client, customer, make_item()).json()
    client.post(f"/api/orders/{order['id']}/cancel", headers=bearer(customer))
    assert [m["token"] for m in fcm.sent] == [TOKEN, TOKEN]  # new order + cancelled, owner only
    assert fcm.sent[1]["data"]["kind"] == "cancelled"


def test_customers_only_get_their_own_orders(client, login, make_item, monkeypatch):
    fcm = fake_fcm(monkeypatch)
    owner, a, b = bearer(login(OWNER)), login("aa@x.com"), login("bb@x.com")
    register(client, a, "fcm-phone-a" + "a" * 40)
    register(client, b, "fcm-phone-b" + "b" * 40)
    order = place(client, a, make_item()).json()
    client.patch(f"/api/admin/orders/{order['id']}/status", json={"status": "ready"}, headers=owner)
    assert [m["token"] for m in fcm.sent] == ["fcm-phone-a" + "a" * 40]


def test_owner_phone_gets_no_customer_messages_and_customer_phone_no_owner_alerts(
        client, login, make_item, monkeypatch):
    fcm = fake_fcm(monkeypatch)
    owner, customer = login(OWNER), login()
    register(client, owner, TOKEN)  # the owner's app uses the new endpoint too
    register(client, customer)
    order = place(client, customer, make_item()).json()
    assert [m["token"] for m in fcm.sent] == [TOKEN]  # "New order" only to the owner
    client.patch(f"/api/admin/orders/{order['id']}/status", json={"status": "ready"}, headers=bearer(owner))
    assert [m["token"] for m in fcm.sent] == [TOKEN, PHONE]  # "Ready" only to the customer


def test_a_phone_follows_whoever_logs_in(client, login, make_item, monkeypatch):
    fcm = fake_fcm(monkeypatch)
    owner, first, second = bearer(login(OWNER)), login("first@x.com"), login("second@x.com")
    register(client, first)
    order = place(client, first, make_item()).json()
    register(client, second)  # same phone, someone else logged in
    client.patch(f"/api/admin/orders/{order['id']}/status", json={"status": "ready"}, headers=owner)
    assert fcm.sent == []  # first's order no longer goes to this phone


def test_customer_logout_stops_their_notifications(client, login, make_item, monkeypatch):
    fcm = fake_fcm(monkeypatch)
    owner, customer = bearer(login(OWNER)), login()
    register(client, customer)
    order = place(client, customer, make_item()).json()
    assert client.post("/api/push-token/remove", json={"token": PHONE}, headers=bearer(customer)).status_code == 200
    client.patch(f"/api/admin/orders/{order['id']}/status", json={"status": "ready"}, headers=owner)
    assert fcm.sent == []


def test_push_token_endpoints_need_a_login(client):
    assert client.post("/api/push-token", json={"token": PHONE}).status_code == 401
    assert client.post("/api/push-token/remove", json={"token": PHONE}).status_code == 401
