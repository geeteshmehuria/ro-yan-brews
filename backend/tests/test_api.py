import os
from datetime import datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite:///./test_royan.db"
os.environ["OTP_DEV_MODE"] = "true"
os.environ["ADMIN_PIN"] = "4321"

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine, SessionLocal
from app.main import app
from app.models import MenuItem, Order, OtpCode

ADMIN = {"x-admin-pin": "4321"}


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as c:  # context manager triggers startup (create_all + seed)
        yield c


def login(client, phone="9876543210"):
    assert client.post("/api/otp/send", json={"phone": phone}).status_code == 200
    r = client.post("/api/otp/verify", json={"phone": phone, "code": "1234"})
    assert r.status_code == 200
    return r.json()["token"]


def place(client, token, items=None):
    items = items or [{"menu_item_id": 1, "size": "na", "qty": 2}]
    return client.post("/api/orders", json={"items": items},
                       headers={"authorization": f"Bearer {token}"})


def test_menu_seeded_and_grouped(client):
    data = client.get("/api/menu").json()
    cats = [g["category"] for g in data]
    assert cats == ["Shakes", "Burgers", "Sandwiches", "Momos", "Fries"]
    momo = data[3]["items"][0]
    assert momo["price_half"] is not None and momo["is_available"] is True


def test_otp_send_rate_limit(client):
    for _ in range(3):
        assert client.post("/api/otp/send", json={"phone": "9000000001"}).status_code == 200
    assert client.post("/api/otp/send", json={"phone": "9000000001"}).status_code == 429


def test_otp_wrong_code_and_attempt_cap(client):
    client.post("/api/otp/send", json={"phone": "9000000002"})
    for _ in range(5):
        r = client.post("/api/otp/verify", json={"phone": "9000000002", "code": "0000"})
        assert r.status_code == 400
    r = client.post("/api/otp/verify", json={"phone": "9000000002", "code": "1234"})
    assert r.status_code == 429  # attempts exhausted even with right code


def test_otp_expiry(client):
    client.post("/api/otp/send", json={"phone": "9000000003"})
    db = SessionLocal()
    row = db.query(OtpCode).filter_by(phone_number="9000000003").first()
    row.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db.commit(); db.close()
    r = client.post("/api/otp/verify", json={"phone": "9000000003", "code": "1234"})
    assert r.status_code == 400 and "expired" in r.json()["detail"].lower()


def test_order_requires_auth(client):
    r = client.post("/api/orders", json={"items": [{"menu_item_id": 1, "qty": 1}]})
    assert r.status_code == 401


def test_order_price_snapshot(client):
    token = login(client)
    r = place(client, token)  # Oreo Shake x2 @80
    assert r.status_code == 201
    order = r.json()
    assert order["total"] == 160 and order["order_number"] == 1

    db = SessionLocal()
    db.query(MenuItem).filter_by(id=1).update({"price_full": 999})
    db.commit(); db.close()

    r2 = client.get(f"/api/orders/{order['id']}",
                    headers={"authorization": f"Bearer {token}"})
    assert r2.json()["total"] == 160  # snapshot survives price change


def test_half_size_pricing(client):
    token = login(client)
    menu = client.get("/api/menu").json()
    momo = menu[3]["items"][0]
    r = place(client, token, [{"menu_item_id": momo["id"], "size": "half", "qty": 1}])
    assert r.json()["total"] == momo["price_half"]
    # half size on an item without one is rejected
    r = place(client, token, [{"menu_item_id": 1, "size": "half", "qty": 1}])
    assert r.status_code == 400


def test_daily_order_number_reset(client):
    token = login(client)
    o1 = place(client, token).json()
    assert o1["order_number"] == 1
    db = SessionLocal()
    db.query(Order).filter_by(id=o1["id"]).update(
        {"created_at": datetime.utcnow() - timedelta(days=1)})
    db.commit(); db.close()
    o2 = place(client, token).json()
    assert o2["order_number"] == 1  # yesterday's order doesn't count


def test_status_transitions(client):
    token = login(client)
    oid = place(client, token).json()["id"]
    ok = client.patch(f"/api/admin/orders/{oid}/status",
                      json={"status": "preparing"}, headers=ADMIN)
    assert ok.status_code == 200
    back = client.patch(f"/api/admin/orders/{oid}/status",
                        json={"status": "placed"}, headers=ADMIN)
    assert back.status_code == 400


def test_admin_auth_rejected(client):
    assert client.get("/api/admin/orders").status_code == 401
    assert client.get("/api/admin/orders",
                      headers={"x-admin-pin": "0000"}).status_code == 401


def test_stock_toggle_blocks_order_and_shows_in_menu(client):
    token = login(client)
    r = client.patch("/api/admin/menu/1/availability",
                     json={"is_available": False}, headers=ADMIN)
    assert r.status_code == 200
    menu = client.get("/api/menu").json()
    assert menu[0]["items"][0]["is_available"] is False
    r = place(client, token)
    assert r.status_code == 400 and "out of stock" in r.json()["detail"].lower()


def test_ws_admin_receives_new_order(client):
    token = login(client)
    with client.websocket_connect("/ws/admin?pin=4321") as ws:
        place(client, token)
        msg = ws.receive_json()
        assert msg["type"] == "new_order" and msg["order"]["order_number"] == 1


def test_ws_admin_wrong_pin_rejected(client):
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/admin?pin=0000") as ws:
            ws.receive_json()


def test_ws_customer_gets_status_update(client):
    token = login(client)
    oid = place(client, token).json()["id"]
    with client.websocket_connect(f"/ws/orders/{oid}") as ws:
        client.patch(f"/api/admin/orders/{oid}/status",
                     json={"status": "preparing"}, headers=ADMIN)
        msg = ws.receive_json()
        assert msg == {"type": "status", "status": "preparing"}


def test_order_isolation_between_customers(client):
    """Customer B must never be able to read customer A's order."""
    token_a = login(client, "9111111111")
    order_a = place(client, token_a).json()
    token_b = login(client, "9222222222")
    r = client.get(f"/api/orders/{order_a['id']}",
                   headers={"authorization": f"Bearer {token_b}"})
    assert r.status_code == 404  # not 403 - don't even confirm the order exists
    client.cookies.clear()  # drop session cookie -> truly anonymous
    r = client.get(f"/api/orders/{order_a['id']}")
    assert r.status_code == 401  # anonymous gets nothing either


def test_customer_cannot_use_admin_endpoints(client):
    token = login(client)
    oid = place(client, token).json()["id"]
    r = client.patch(f"/api/admin/orders/{oid}/status", json={"status": "ready"},
                     headers={"authorization": f"Bearer {token}"})
    assert r.status_code == 401  # customer JWT is not admin


def test_stats_today(client):
    token = login(client)
    place(client, token)
    stats = client.get("/api/admin/stats/today", headers=ADMIN).json()
    assert stats["orders"] == 1 and stats["revenue"] == 160
    assert stats["top_item"] == "Oreo Shake"
