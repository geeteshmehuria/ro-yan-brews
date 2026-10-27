import time

import pytest
from sqlalchemy import create_engine, inspect, text
from starlette.websockets import WebSocketDisconnect

from app import mailer
from app.db import add_missing_columns
from app.ws import manager

from conftest import OWNER, bearer, place


def set_status(client, owner_token, oid, status):
    return client.patch(f"/api/admin/orders/{oid}/status", json={"status": status},
                        headers=bearer(owner_token))


# ---------------- profile ----------------

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


# ---------------- note ----------------

def test_order_note_reaches_owner(client, login, make_item):
    item = make_item()
    body = {"items": [{"menu_item_id": item["id"], "qty": 1}], "note": "  less spicy  "}
    r = client.post("/api/orders", json=body, headers=bearer(login()))
    assert r.status_code == 201 and r.json()["note"] == "less spicy"
    assert client.get("/api/admin/orders", headers=bearer(login(OWNER))).json()[0]["note"] == "less spicy"


def test_order_note_is_optional_and_bounded(client, login, make_item):
    item = make_item()
    token = login()
    assert place(client, token, item).json()["note"] is None
    too_long = {"items": [{"menu_item_id": item["id"], "qty": 1}], "note": "x" * 201}
    assert client.post("/api/orders", json=too_long, headers=bearer(token)).status_code == 422


# ---------------- my orders ----------------

def test_my_orders_are_own_newest_first_and_capped(client, login, make_item):
    item = make_item()
    mine, other = login("mine@x.com"), login("other@x.com")
    place(client, other, item)
    ids = [place(client, mine, item).json()["id"] for _ in range(22)]
    orders = client.get("/api/orders/mine", headers=bearer(mine)).json()
    assert [o["id"] for o in orders] == ids[::-1][:20]
    assert client.get("/api/orders/mine").status_code == 401


# ---------------- cancel ----------------

def test_customer_can_cancel_only_while_placed(client, login, make_item):
    owner, token = login(OWNER), login()
    oid = place(client, token, make_item()).json()["id"]
    r = client.post(f"/api/orders/{oid}/cancel", headers=bearer(token))
    assert r.status_code == 200 and r.json()["status"] == "cancelled"

    oid2 = place(client, token, make_item("Burger")).json()["id"]
    set_status(client, owner, oid2, "preparing")
    r = client.post(f"/api/orders/{oid2}/cancel", headers=bearer(token))
    assert r.status_code == 400 and "already being prepared" in r.json()["detail"]


def test_cancel_is_only_for_the_orders_owner(client, login, make_item):
    oid = place(client, login("aa@x.com"), make_item()).json()["id"]
    assert client.post(f"/api/orders/{oid}/cancel", headers=bearer(login("bb@x.com"))).status_code == 404
    assert client.post(f"/api/orders/{oid}/cancel").status_code == 401


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


def test_cancelled_orders_are_excluded_from_stats(client, login, make_item):
    owner, token = login(OWNER), login()
    item = make_item(full=80)
    place(client, token, item)  # 160, kept
    oid = place(client, token, item).json()["id"]
    client.post(f"/api/orders/{oid}/cancel", headers=bearer(token))
    stats = client.get("/api/admin/stats/today", headers=bearer(owner)).json()
    assert stats["orders"] == 1 and stats["revenue"] == 160


# ---------------- /ws/me ----------------

def test_ws_me_needs_a_token(client):
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect("/ws/me"):
            pass
    assert e.value.code == 4401


def test_ws_me_gets_status_updates_for_all_own_orders(client, login, make_item):
    owner, token = login(OWNER), login()
    item = make_item()
    first = place(client, token, item).json()["id"]
    second = place(client, token, item).json()["id"]
    with client.websocket_connect(f"/ws/me?token={token}") as ws:
        set_status(client, owner, first, "preparing")
        set_status(client, owner, second, "preparing")
        assert ws.receive_json() == {"type": "status", "order_id": first, "status": "preparing"}
        assert ws.receive_json() == {"type": "status", "order_id": second, "status": "preparing"}


def test_ws_me_does_not_leak_other_customers_updates(client, login, make_item):
    owner, other = login(OWNER), login("other@x.com")
    oid = place(client, login("aa@x.com"), make_item()).json()["id"]
    with client.websocket_connect(f"/ws/me?token={other}") as ws:
        set_status(client, owner, oid, "preparing")
        place(client, other, make_item("Burger"))  # nothing for `other` yet...
        client.post(f"/api/orders/{oid}/cancel", headers=bearer(login("aa@x.com")))
        mine = place(client, other, make_item("Fries")).json()["id"]
        set_status(client, owner, mine, "preparing")
        assert ws.receive_json()["order_id"] == mine  # first message is for their own order


def test_ws_me_reports_cancellation_to_customer_and_owner(client, login, make_item):
    token, owner = login(), login(OWNER)
    oid = place(client, token, make_item()).json()["id"]
    with client.websocket_connect(f"/ws/me?token={token}") as mine, \
            client.websocket_connect(f"/ws/admin?token={owner}") as admin:
        client.post(f"/api/orders/{oid}/cancel", headers=bearer(token))
        expected = {"type": "status", "order_id": oid, "status": "cancelled"}
        assert mine.receive_json() == expected
        assert admin.receive_json() == expected


def test_ws_me_pool_is_cleaned_up(client, login):
    token = login()
    cid = client.get("/api/me", headers=bearer(token)) and __import__("jwt").decode(
        token, options={"verify_signature": False})["cid"]
    with client.websocket_connect(f"/ws/me?token={token}"):
        assert cid in manager.customers
    for _ in range(50):  # the server side notices the disconnect asynchronously
        if cid not in manager.customers:
            break
        time.sleep(0.02)
    assert cid not in manager.customers


# ---------------- "ready" email ----------------

@pytest.fixture()
def smtp_on(monkeypatch):
    """Pretend SMTP is configured. Call it *after* logging in — login codes use the mailer too."""
    def enable(send):
        monkeypatch.setattr(mailer, "SMTP_USER", "stall@gmail.com")
        monkeypatch.setattr(mailer, "SMTP_PASS", "app-password")
        monkeypatch.setattr(mailer, "send_mail", send)
    return enable


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


# ---------------- lightweight migration ----------------

def test_add_missing_columns_upgrades_old_tables_and_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    with engine.begin() as conn:  # the schema as it was before name/note existed
        conn.execute(text("CREATE TABLE customers (id INTEGER PRIMARY KEY, email VARCHAR(255) NOT NULL)"))
        conn.execute(text("INSERT INTO customers (email) VALUES ('old@x.com')"))
    add_missing_columns(engine)
    add_missing_columns(engine)  # second run is a no-op
    columns = {c["name"] for c in inspect(engine).get_columns("customers")}
    assert "name" in columns
    with engine.connect() as conn:
        assert conn.execute(text("SELECT name FROM customers")).scalar() is None
    engine.dispose()
