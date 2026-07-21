import os
from datetime import datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite:///./test_royan.db"
os.environ["OTP_DEV_MODE"] = "true"
os.environ["ADMIN_EMAIL"] = "owner@royan.test"

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine, SessionLocal
from app.main import app
from app.models import MenuItem, Order, OtpCode

EMAIL = "customer@gmail.com"
OWNER = "owner@royan.test"
DEV_CODE = "123456"


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as c:  # context manager triggers startup (create_all + seed)
        yield c


def login(client, email=EMAIL):
    assert client.post("/api/otp/send", json={"email": email}).status_code == 200
    r = client.post("/api/otp/verify", json={"email": email, "code": DEV_CODE})
    assert r.status_code == 200
    return r.json()["token"]


def bearer(token):
    return {"authorization": f"Bearer {token}"}


def admin_headers(client):
    """Log the owner in via email + OTP; their session token *is* admin."""
    return bearer(login(client, OWNER))


def place(client, token, items=None):
    items = items or [{"menu_item_id": 1, "size": "na", "qty": 2}]
    return client.post("/api/orders", json={"items": items}, headers=bearer(token))


def test_menu_seeded_and_grouped(client):
    data = client.get("/api/menu").json()
    cats = [g["category"] for g in data]
    assert cats == ["Shakes", "Burgers", "Sandwiches", "Momos", "Fries"]
    momo = data[3]["items"][0]
    assert momo["price_half"] is not None and momo["is_available"] is True


def test_email_validation(client):
    assert client.post("/api/otp/send", json={"email": "not-an-email"}).status_code == 422
    assert client.post("/api/otp/send", json={"email": "a@b"}).status_code == 422
    # uppercase is normalised to lowercase
    assert client.post("/api/otp/send", json={"email": "GOOD@Gmail.Com"}).status_code == 200
    db = SessionLocal()
    assert db.query(OtpCode).filter_by(email="good@gmail.com").count() == 1
    db.close()


def test_otp_is_six_digits(client):
    assert client.post("/api/otp/send", json={"email": "len@x.com"}).status_code == 200
    db = SessionLocal()
    row = db.query(OtpCode).filter_by(email="len@x.com").first()
    assert len(row.code) == 6 and row.code.isdigit()
    db.close()
    # a 4-digit code is now rejected by validation before it even reaches verify
    r = client.post("/api/otp/verify", json={"email": "len@x.com", "code": "1234"})
    assert r.status_code == 422


def test_otp_send_rate_limit(client):
    for _ in range(3):
        assert client.post("/api/otp/send", json={"email": "rl@x.com"}).status_code == 200
    assert client.post("/api/otp/send", json={"email": "rl@x.com"}).status_code == 429


def test_otp_wrong_code_and_attempt_cap(client):
    client.post("/api/otp/send", json={"email": "cap@x.com"})
    for _ in range(5):
        r = client.post("/api/otp/verify", json={"email": "cap@x.com", "code": "000000"})
        assert r.status_code == 400
    r = client.post("/api/otp/verify", json={"email": "cap@x.com", "code": DEV_CODE})
    assert r.status_code == 429  # attempts exhausted even with right code


def test_otp_expiry(client):
    client.post("/api/otp/send", json={"email": "exp@x.com"})
    db = SessionLocal()
    row = db.query(OtpCode).filter_by(email="exp@x.com").first()
    row.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db.commit(); db.close()
    r = client.post("/api/otp/verify", json={"email": "exp@x.com", "code": DEV_CODE})
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
    assert order["email_masked"] == "cu***@gmail.com"

    db = SessionLocal()
    db.query(MenuItem).filter_by(id=1).update({"price_full": 999})
    db.commit(); db.close()

    r2 = client.get(f"/api/orders/{order['id']}", headers=bearer(token))
    assert r2.json()["total"] == 160  # snapshot survives price change


def test_half_size_pricing(client):
    token = login(client)
    menu = client.get("/api/menu").json()
    momo = menu[3]["items"][0]
    r = place(client, token, [{"menu_item_id": momo["id"], "size": "half", "qty": 1}])
    assert r.json()["total"] == momo["price_half"]
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
    admin = admin_headers(client)
    token = login(client)
    oid = place(client, token).json()["id"]
    ok = client.patch(f"/api/admin/orders/{oid}/status",
                      json={"status": "preparing"}, headers=admin)
    assert ok.status_code == 200
    back = client.patch(f"/api/admin/orders/{oid}/status",
                        json={"status": "placed"}, headers=admin)
    assert back.status_code == 400


def test_admin_requires_owner_session(client):
    # anonymous
    assert client.get("/api/admin/orders").status_code == 401
    # a normal customer's token is not admin
    token = login(client)
    assert client.get("/api/admin/orders", headers=bearer(token)).status_code == 401
    # the owner's token is
    assert client.get("/api/admin/orders", headers=admin_headers(client)).status_code == 200


def test_stock_toggle_blocks_order_and_shows_in_menu(client):
    admin = admin_headers(client)
    token = login(client)
    r = client.patch("/api/admin/menu/1/availability",
                     json={"is_available": False}, headers=admin)
    assert r.status_code == 200
    menu = client.get("/api/menu").json()
    assert menu[0]["items"][0]["is_available"] is False
    r = place(client, token)
    assert r.status_code == 400 and "out of stock" in r.json()["detail"].lower()


def test_ws_admin_receives_new_order(client):
    admin_token = login(client, OWNER)
    token = login(client)
    with client.websocket_connect(f"/ws/admin?token={admin_token}") as ws:
        place(client, token)
        msg = ws.receive_json()
        assert msg["type"] == "new_order" and msg["order"]["order_number"] == 1


def test_ws_admin_non_owner_rejected(client):
    token = login(client)  # ordinary customer token
    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/admin?token={token}") as ws:
            ws.receive_json()


def test_ws_customer_gets_status_update(client):
    admin = admin_headers(client)
    token = login(client)
    oid = place(client, token).json()["id"]
    with client.websocket_connect(f"/ws/orders/{oid}") as ws:
        client.patch(f"/api/admin/orders/{oid}/status",
                     json={"status": "preparing"}, headers=admin)
        msg = ws.receive_json()
        assert msg == {"type": "status", "status": "preparing"}


def test_order_isolation_between_customers(client):
    """Customer B must never be able to read customer A's order."""
    token_a = login(client, "aa@x.com")
    order_a = place(client, token_a).json()
    token_b = login(client, "bb@x.com")
    r = client.get(f"/api/orders/{order_a['id']}", headers=bearer(token_b))
    assert r.status_code == 404  # not 403 - don't even confirm the order exists
    client.cookies.clear()  # drop session cookie -> truly anonymous
    r = client.get(f"/api/orders/{order_a['id']}")
    assert r.status_code == 401  # anonymous gets nothing either


def test_customer_cannot_use_admin_endpoints(client):
    token = login(client)
    oid = place(client, token).json()["id"]
    r = client.patch(f"/api/admin/orders/{oid}/status", json={"status": "ready"},
                     headers=bearer(token))
    assert r.status_code == 401  # customer session is not admin


def test_stats_today(client):
    admin = admin_headers(client)
    token = login(client)
    place(client, token)
    stats = client.get("/api/admin/stats/today", headers=admin).json()
    assert stats["orders"] == 1 and stats["revenue"] == 160
    assert stats["top_item"] == "Oreo Shake"


# ---------------- SMTP provider (mocked — no real email sent) ----------------

class _FakeSMTP:
    sent = []
    def __init__(self, *a, **k): pass
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def login(self, user, pw): _FakeSMTP.last_login = (user, pw)
    def sendmail(self, frm, to, body): _FakeSMTP.sent.append((frm, to, body))


def test_smtp_provider_sends_mail(monkeypatch):
    import smtplib
    from app import otp_service
    monkeypatch.setattr(otp_service, "SMTP_USER", "stall@gmail.com")
    monkeypatch.setattr(otp_service, "SMTP_PASS", "app-password")
    monkeypatch.setattr(otp_service, "SMTP_PORT", 465)
    monkeypatch.setattr(smtplib, "SMTP_SSL", _FakeSMTP)
    _FakeSMTP.sent = []
    otp_service.SmtpEmailProvider().send("dest@x.com", "567890")
    assert _FakeSMTP.last_login == ("stall@gmail.com", "app-password")
    frm, to, body = _FakeSMTP.sent[0]
    assert to == ["dest@x.com"] and "567890" in body


def test_smtp_auth_failure_gives_friendly_503(monkeypatch):
    import smtplib
    from app import otp_service
    class _AuthFail(_FakeSMTP):
        def login(self, u, p): raise smtplib.SMTPAuthenticationError(535, b"bad creds")
    monkeypatch.setattr(otp_service, "SMTP_USER", "stall@gmail.com")
    monkeypatch.setattr(otp_service, "SMTP_PASS", "wrong")
    monkeypatch.setattr(otp_service, "SMTP_PORT", 465)
    monkeypatch.setattr(smtplib, "SMTP_SSL", _AuthFail)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as e:
        otp_service.SmtpEmailProvider().send("dest@x.com", "567890")
    assert e.value.status_code == 503


def test_provider_selection(monkeypatch):
    from app import otp_service
    monkeypatch.setattr(otp_service, "SMTP_USER", "")
    monkeypatch.setattr(otp_service, "SMTP_PASS", "")
    assert isinstance(otp_service.get_provider(), otp_service.DevOtpProvider)
    monkeypatch.setattr(otp_service, "SMTP_USER", "a@gmail.com")
    monkeypatch.setattr(otp_service, "SMTP_PASS", "x")
    assert isinstance(otp_service.get_provider(), otp_service.SmtpEmailProvider)
