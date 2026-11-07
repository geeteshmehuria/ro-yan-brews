"""Customer orders: placing (prices, limits, checkout keys), listing, cancelling."""
from datetime import timedelta

import pytest
from conftest import OWNER, bearer, my_order, place

from app.features.orders import orders_router
from app.shared.clock import utcnow
from app.shared.database import SessionLocal
from app.shared.models import MenuItem, Order


def set_status(client, owner_token, oid, status):
    return client.patch(f"/api/admin/orders/{oid}/status", json={"status": status},
                        headers=bearer(owner_token))


def place_keyed(client, token, item, key, qty=1):
    body = {"items": [{"menu_item_id": item["id"], "size": "na", "qty": qty}], "client_key": key}
    return client.post("/api/orders", json=body, headers=bearer(token))


def test_order_requires_auth(client, make_item):
    item = make_item()
    r = client.post("/api/orders", json={"items": [{"menu_item_id": item["id"], "qty": 1}]})
    assert r.status_code == 401


def test_cookie_is_not_an_auth_method(client, login, make_item):
    token = login()
    client.cookies.set("session", token)
    r = client.post("/api/orders", json={"items": [{"menu_item_id": make_item()["id"], "qty": 1}]})
    assert r.status_code == 401


def test_order_price_snapshot(client, login, make_item):
    item = make_item(full=80)
    token = login()
    order = place(client, token, item).json()
    assert order["total"] == 160 and order["order_number"] == 1
    assert order["email"] == "cu***@gmail.com"

    with SessionLocal() as db:
        db.query(MenuItem).filter_by(id=item["id"]).update({"price_full": 999})
        db.commit()
    assert my_order(client, token, order["id"])["total"] == 160  # snapshot survives price change


def test_half_size_pricing(client, login, make_item):
    momo = make_item("Steam Momos", full=90, half=50, category="Momos")
    plain = make_item("Oreo Shake")
    token = login()
    assert place(client, token, momo, "half", 1).json()["total"] == 50
    assert place(client, token, plain, "half", 1).status_code == 400


def test_order_numbers_are_sequential_and_reset_daily(client, login, make_item):
    item = make_item()
    token = login()
    o1 = place(client, token, item).json()
    o2 = place(client, token, item).json()
    assert (o1["order_number"], o2["order_number"]) == (1, 2)
    with SessionLocal() as db:
        db.query(Order).update({"created_at": utcnow() - timedelta(days=1)})
        db.commit()
    assert place(client, token, item).json()["order_number"] == 1  # earlier days don't count


def test_order_isolation_between_customers(client, login, make_item):
    """Customer B must never be able to see or touch customer A's order."""
    order_a = place(client, login("aa@x.com"), make_item()).json()
    token_b = login("bb@x.com")
    assert client.get("/api/orders/mine", headers=bearer(token_b)).json() == []
    r = client.post(f"/api/orders/{order_a['id']}/cancel", headers=bearer(token_b))
    assert r.status_code == 404  # not 403 - don't even confirm the order exists
    assert client.get("/api/orders/mine").status_code == 401


def test_order_size_is_capped(client, login, make_item):
    token = login()
    items = [make_item(f"Item {n}") for n in range(31)]
    body = lambda its: {"items": [{"menu_item_id": i["id"], "qty": 1} for i in its]}
    assert client.post("/api/orders", json=body(items), headers=bearer(token)).status_code == 422
    assert client.post("/api/orders", json=body(items[:30]), headers=bearer(token)).status_code == 201


def test_repeated_order_lines_are_rejected(client, login, make_item):
    item = make_item()
    line = {"menu_item_id": item["id"], "qty": 1}
    r = client.post("/api/orders", json={"items": [line, line]}, headers=bearer(login()))
    assert r.status_code == 422


def test_active_orders_per_customer_are_capped(client, login, make_item):
    item = make_item()
    token, owner = login(), bearer(login(OWNER))
    ids = [place(client, token, item).json()["id"] for _ in range(3)]
    assert place(client, token, item).status_code == 429
    assert place(client, login("other@x.com"), item).status_code == 201  # per customer, not global
    client.post(f"/api/orders/{ids[0]}/cancel", headers=bearer(token))
    assert place(client, token, item).status_code == 201  # cancelled ones free a slot
    client.patch(f"/api/admin/orders/{ids[1]}/status", json={"status": "completed"}, headers=owner)
    assert place(client, token, item).status_code == 201  # and so do completed ones


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


def test_my_orders_are_own_newest_first_and_capped(client, login, make_item, monkeypatch):
    monkeypatch.setattr(orders_router, "MAX_ACTIVE_ORDERS", 100)  # this test is about the list, not the order cap
    item = make_item()
    mine, other = login("mine@x.com"), login("other@x.com")
    place(client, other, item)
    ids = [place(client, mine, item).json()["id"] for _ in range(22)]
    orders = client.get("/api/orders/mine", headers=bearer(mine)).json()
    assert [o["id"] for o in orders] == ids[::-1][:20]
    assert client.get("/api/orders/mine").status_code == 401


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


def test_same_checkout_key_returns_the_same_order(client, login, make_item):
    tok, item = login(), make_item()
    first = place_keyed(client, tok, item, "key-aaaaaaaa")
    again = place_keyed(client, tok, item, "key-aaaaaaaa")
    assert first.status_code == again.status_code == 201
    assert again.json()["id"] == first.json()["id"]
    assert first.json()["client_key"] == "key-aaaaaaaa"
    mine = client.get("/api/orders/mine", headers=bearer(tok)).json()
    assert len(mine) == 1 and mine[0]["client_key"] == "key-aaaaaaaa"


def test_retry_succeeds_even_if_store_paused_or_limit_reached_since(client, login, make_item):
    owner, tok, item = login(OWNER), login(), make_item()
    placed = place_keyed(client, tok, item, "key-retry-001").json()
    for k in ("key-fill-0002", "key-fill-0003"):
        assert place_keyed(client, tok, item, k).status_code == 201
    assert place_keyed(client, tok, item, "key-new-00004").status_code == 429  # 3 active: full
    client.patch("/api/admin/store", json={"accepting_orders": False}, headers=bearer(owner))
    assert place_keyed(client, tok, item, "key-retry-001").json()["id"] == placed["id"]


def test_different_keys_and_no_key_make_separate_orders(client, login, make_item):
    tok, item = login(), make_item()
    a = place_keyed(client, tok, item, "key-one-00001").json()
    b = place_keyed(client, tok, item, "key-two-00002").json()
    c = place(client, tok, item).json()
    d = place(client, tok, item)  # 4th active order: blocked by the limit, not by a NULL key clash
    assert len({a["id"], b["id"], c["id"]}) == 3 and c["client_key"] is None
    assert d.status_code == 429


def test_checkout_keys_are_per_customer(client, login, make_item):
    item = make_item()
    a = place_keyed(client, login("a@gmail.com"), item, "shared-key-01").json()
    b = place_keyed(client, login("b@gmail.com"), item, "shared-key-01").json()
    assert a["id"] != b["id"]


@pytest.mark.parametrize("key", ["short", "has space!", "x" * 65])
def test_bad_checkout_keys_are_rejected(client, login, make_item, key):
    assert place_keyed(client, login(), make_item(), key).status_code == 422
