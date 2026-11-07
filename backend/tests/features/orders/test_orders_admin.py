"""The owner's order queue: status ladder, cancel, not collected, the ready email."""
from datetime import timedelta

import pytest
from conftest import OWNER, bearer, place

from app.shared import mailer
from app.shared.clock import utcnow
from app.shared.database import SessionLocal
from app.shared.models import Order


def status(client, owner, oid, st):
    assert client.patch(f"/api/admin/orders/{oid}/status", json={"status": st}, headers=owner).status_code == 200


def stats(client, owner):
    return client.get("/api/admin/stats/today", headers=owner).json()


def set_status(client, owner_token, oid, status):
    return client.patch(f"/api/admin/orders/{oid}/status", json={"status": status},
                        headers=bearer(owner_token))


@pytest.fixture()
def smtp_on(monkeypatch):
    """Pretend SMTP is configured. Call it *after* logging in — login codes use the mailer too."""
    def enable(send):
        monkeypatch.setattr(mailer, "SMTP_USER", "stall@gmail.com")
        monkeypatch.setattr(mailer, "SMTP_PASS", "app-password")
        monkeypatch.setattr(mailer, "send_mail", send)
    return enable


def test_status_transitions(client, login, make_item):
    admin = bearer(login(OWNER))
    oid = place(client, login(), make_item()).json()["id"]
    ok = client.patch(f"/api/admin/orders/{oid}/status", json={"status": "preparing"}, headers=admin)
    assert ok.status_code == 200
    back = client.patch(f"/api/admin/orders/{oid}/status", json={"status": "placed"}, headers=admin)
    assert back.status_code == 400
    bad = client.patch(f"/api/admin/orders/{oid}/status", json={"status": "nope"}, headers=admin)
    assert bad.status_code == 422


def test_admin_requires_owner_session(client, login):
    assert client.get("/api/admin/orders").status_code == 401
    assert client.get("/api/admin/orders", headers=bearer(login())).status_code == 403  # logged in, not owner
    assert client.get("/api/admin/orders", headers=bearer(login(OWNER))).status_code == 200


def test_customer_cannot_use_admin_endpoints(client, login, make_item):
    token = login()
    oid = place(client, token, make_item()).json()["id"]
    r = client.patch(f"/api/admin/orders/{oid}/status", json={"status": "ready"}, headers=bearer(token))
    assert r.status_code == 403


def test_unfinished_orders_stay_in_the_queue_past_midnight(client, login, make_item):
    item, token, owner = make_item(), login(), bearer(login(OWNER))
    cooking, done, gone = (place(client, token, item).json()["id"] for _ in range(3))
    client.patch(f"/api/admin/orders/{cooking}/status", json={"status": "preparing"}, headers=owner)
    client.patch(f"/api/admin/orders/{done}/status", json={"status": "completed"}, headers=owner)
    client.post(f"/api/orders/{gone}/cancel", headers=bearer(token))
    with SessionLocal() as db:
        db.query(Order).update({"created_at": utcnow() - timedelta(days=1)})
        db.commit()
    today = place(client, token, item).json()["id"]
    queue = [o["id"] for o in client.get("/api/admin/orders", headers=owner).json()]
    assert queue == [today, cooking]  # yesterday's finished/cancelled ones are gone
    stats = client.get("/api/admin/stats/today", headers=owner).json()
    assert stats["orders"] == 1  # stats stay "today only"


def test_owner_sees_full_email_customer_sees_masked(client, login, make_item):
    token = login("someone@gmail.com")
    place(client, token, make_item())
    orders = client.get("/api/admin/orders", headers=bearer(login(OWNER))).json()
    assert orders[0]["email"] == "someone@gmail.com"


def test_owner_sees_name_when_set_else_email(client, login, make_item):
    item = make_item()
    token = login("someone@x.com")
    place(client, token, item)
    owner = bearer(login(OWNER))
    order = client.get("/api/admin/orders", headers=owner).json()[0]
    assert order["name"] is None and order["email"] == "someone@x.com"
    client.patch("/api/me", json={"name": "Sam"}, headers=bearer(token))
    order = client.get("/api/admin/orders", headers=owner).json()[0]
    assert order["name"] == "Sam" and order["email"] == "someone@x.com"


def test_owner_can_cancel_until_ready(client, login, make_item):
    owner, token = login(OWNER), login()
    item = make_item()
    preparing = place(client, token, item).json()["id"]
    set_status(client, owner, preparing, "preparing")
    assert set_status(client, owner, preparing, "cancelled").status_code == 200

    ready = place(client, token, item).json()["id"]
    set_status(client, owner, ready, "ready")
    assert set_status(client, owner, ready, "cancelled").status_code == 400


def test_cancelled_orders_never_move_again(client, login, make_item):
    owner, token = login(OWNER), login()
    oid = place(client, token, make_item()).json()["id"]
    set_status(client, owner, oid, "cancelled")
    for status in ("placed", "preparing", "ready", "completed", "cancelled"):
        assert set_status(client, owner, oid, status).status_code == 400


def test_ready_email_is_sent_once_with_name(client, login, make_item, smtp_on):
    owner, token = login(OWNER), login("buyer@x.com")
    client.patch("/api/me", json={"name": "Sam"}, headers=bearer(token))
    oid = place(client, token, make_item()).json()["id"]
    outbox = []
    smtp_on(lambda to, subject, body: outbox.append((to, subject, body)))
    set_status(client, owner, oid, "preparing")
    assert outbox == []  # only "ready" sends mail
    set_status(client, owner, oid, "ready")
    assert len(outbox) == 1
    to, subject, body = outbox[0]
    assert to == "buyer@x.com" and "#1" in subject and "Hi Sam" in body


def test_failed_ready_email_does_not_break_the_status_change(client, login, make_item, smtp_on):
    owner, token = login(OWNER), login()
    oid = place(client, token, make_item()).json()["id"]

    def boom(*a, **k):
        raise RuntimeError("smtp down")
    smtp_on(boom)
    assert set_status(client, owner, oid, "ready").status_code == 200
    assert client.get("/api/orders/mine", headers=bearer(token)).json()[0]["status"] == "ready"


def test_no_ready_email_without_smtp(client, login, make_item, monkeypatch):
    owner, token = login(OWNER), login()
    oid = place(client, token, make_item()).json()["id"]
    sent = []  # SMTP stays unconfigured (conftest blanks it), so nothing may be sent
    monkeypatch.setattr(mailer, "send_mail", lambda *a: sent.append(a))
    assert set_status(client, owner, oid, "ready").status_code == 200
    assert sent == []


def test_not_collected_closes_a_ready_order_without_cash(client, login, make_item):
    owner, token = bearer(login(OWNER)), login()
    oid = place(client, token, make_item(full=150), qty=1).json()["id"]
    status(client, owner, oid, "ready")
    assert stats(client, owner)["to_collect"] == 150
    status(client, owner, oid, "not_collected")
    s = stats(client, owner)
    assert (s["cash_collected"], s["to_collect"], s["not_collected"]) == (0, 0, 1)
    assert s["active"]["ready"] == 0
    mine = client.get("/api/orders/mine", headers=bearer(token)).json()
    assert mine[0]["status"] == "not_collected"  # the customer sees it too


def test_only_a_ready_order_can_be_not_collected(client, login, make_item):
    owner, token, item = bearer(login(OWNER)), login(), make_item()
    oid = place(client, token, item).json()["id"]
    r = client.patch(f"/api/admin/orders/{oid}/status", json={"status": "not_collected"}, headers=owner)
    assert r.status_code == 400  # still placed
    status(client, owner, oid, "ready")
    status(client, owner, oid, "not_collected")
    for st in ("completed", "ready", "cancelled", "not_collected"):  # closed: never moves again
        r = client.patch(f"/api/admin/orders/{oid}/status", json={"status": st}, headers=owner)
        assert r.status_code == 400, st


def test_customers_cannot_mark_not_collected(client, login, make_item):
    token = login()
    oid = place(client, token, make_item()).json()["id"]
    r = client.patch(f"/api/admin/orders/{oid}/status", json={"status": "not_collected"}, headers=bearer(token))
    assert r.status_code == 403


def test_not_collected_frees_the_customers_order_slot(client, login, make_item, monkeypatch):
    owner, token, item = bearer(login(OWNER)), login(), make_item()
    ids = [place(client, token, item).json()["id"] for _ in range(3)]
    assert place(client, token, item).status_code == 429  # 3 in progress
    status(client, owner, ids[0], "ready")
    status(client, owner, ids[0], "not_collected")
    assert place(client, token, item).status_code == 201


def test_not_collected_sends_the_customer_no_notification(client, login, make_item, monkeypatch):
    from app.features.notifications import push_service
    sent = []
    monkeypatch.setattr(push_service, "_send", lambda *a, **k: sent.append(a))
    owner, token = bearer(login(OWNER)), login()
    oid = place(client, token, make_item()).json()["id"]
    status(client, owner, oid, "ready")
    sent.clear()
    status(client, owner, oid, "not_collected")
    assert sent == []
