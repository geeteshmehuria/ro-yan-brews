from datetime import timedelta

from app.clock import utcnow
from app.db import SessionLocal
from app.models import Order

from conftest import OWNER, bearer, place


def status(client, owner, oid, st):
    assert client.patch(f"/api/admin/orders/{oid}/status", json={"status": st}, headers=owner).status_code == 200


def stats(client, owner):
    return client.get("/api/admin/stats/today", headers=owner).json()


# ---------------- numbers ----------------

def test_cash_is_only_counted_once_an_order_is_done(client, login, make_item):
    owner, token = bearer(login(OWNER)), login()
    item = make_item(full=100)
    done, ready, new = (place(client, token, item, qty=1).json()["id"] for _ in range(3))
    status(client, owner, done, "completed")
    status(client, owner, ready, "ready")
    s = stats(client, owner)
    assert s["cash_collected"] == 100 and s["completed"] == 1
    assert s["to_collect"] == 200  # ready + placed: not paid yet
    assert s["active"] == {"placed": 1, "preparing": 0, "ready": 1}
    assert s["orders"] == 3 and s["revenue"] == 100


def test_yesterdays_unfinished_order_is_still_to_collect(client, login, make_item):
    owner, token = bearer(login(OWNER)), login()
    oid = place(client, token, make_item(full=90), qty=1).json()["id"]
    with SessionLocal() as db:
        db.get(Order, oid).created_at = utcnow() - timedelta(days=1)
        db.commit()
    s = stats(client, owner)
    assert s["orders"] == 0 and s["to_collect"] == 90 and s["active"]["placed"] == 1


def test_out_of_stock_count_ignores_removed_items(client, login, make_item):
    owner = bearer(login(OWNER))
    make_item("A", available=False)
    gone = make_item("B", available=False)
    make_item("C")
    client.post(f"/api/admin/menu/{gone['id']}/remove", headers=owner)
    assert stats(client, owner)["out_of_stock"] == 1


# ---------------- open / paused ----------------

def test_store_is_open_by_default(client):
    assert client.get("/api/store").json() == {"accepting_orders": True, "message": None}


def test_paused_store_refuses_new_orders_until_reopened(client, login, make_item):
    owner, token, item = bearer(login(OWNER)), login(), make_item()
    r = client.patch("/api/admin/store", json={"accepting_orders": False}, headers=owner)
    assert r.status_code == 200 and r.json()["accepting_orders"] is False
    assert client.get("/api/store").json()["message"].startswith("We're not taking orders")
    refused = place(client, token, item)
    assert refused.status_code == 409 and "not taking orders" in refused.json()["detail"]
    assert stats(client, owner)["accepting_orders"] is False
    client.patch("/api/admin/store", json={"accepting_orders": True}, headers=owner)
    assert place(client, token, item).status_code == 201


def test_pausing_does_not_touch_orders_already_placed(client, login, make_item):
    owner, token = bearer(login(OWNER)), login()
    oid = place(client, token, make_item()).json()["id"]
    client.patch("/api/admin/store", json={"accepting_orders": False}, headers=owner)
    status(client, owner, oid, "ready")  # the owner can still finish it
    assert client.post(f"/api/orders/{oid}/cancel", headers=bearer(token)).status_code == 400  # ready: as before


def test_only_the_owner_can_pause(client, login):
    assert client.patch("/api/admin/store", json={"accepting_orders": False}).status_code == 401
    r = client.patch("/api/admin/store", json={"accepting_orders": False}, headers=bearer(login()))
    assert r.status_code == 403
    assert client.get("/api/store").json()["accepting_orders"] is True


def test_pause_is_pushed_live_to_menus_and_the_owner(client, login):
    owner_token = login(OWNER)
    with client.websocket_connect("/ws/menu") as menu, \
            client.websocket_connect(f"/ws/admin?token={owner_token}") as admin:
        client.patch("/api/admin/store", json={"accepting_orders": False}, headers=bearer(owner_token))
        assert menu.receive_json()["type"] == "store"
        msg = admin.receive_json()
        assert msg["type"] == "store" and msg["accepting_orders"] is False
