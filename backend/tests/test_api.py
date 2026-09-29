import os
import subprocess
import sys
from datetime import timedelta

import pytest
from starlette.websockets import WebSocketDisconnect

from app import auth, clock, mailer, otp_service
from app.clock import utcnow
from app.db import SessionLocal
from app.models import MenuItem, Order, OtpCode

from conftest import DEV_CODE, OWNER, bearer, place


# ---------------- menu ----------------

def test_menu_grouped_by_category(client, make_item):
    make_item("Oreo Shake", category="Shakes")
    make_item("Steam Momos", full=90, half=50, category="Momos")
    data = client.get("/api/menu").json()
    assert [g["category"] for g in data] == ["Shakes", "Momos"]
    assert data[1]["items"][0]["price_half"] == 50


# ---------------- otp ----------------

def test_email_validation(client):
    assert client.post("/api/otp/send", json={"email": "not-an-email"}).status_code == 422
    assert client.post("/api/otp/send", json={"email": "a@b"}).status_code == 422
    # uppercase is normalised to lowercase
    assert client.post("/api/otp/send", json={"email": "GOOD@Gmail.Com"}).status_code == 200
    with SessionLocal() as db:
        assert db.query(OtpCode).filter_by(email="good@gmail.com").count() == 1


def test_otp_is_six_digits(client):
    assert client.post("/api/otp/send", json={"email": "len@x.com"}).status_code == 200
    with SessionLocal() as db:
        row = db.query(OtpCode).filter_by(email="len@x.com").first()
        assert len(row.code) == 6 and row.code.isdigit()
    # a 4-digit code is rejected by validation before it reaches verify
    r = client.post("/api/otp/verify", json={"email": "len@x.com", "code": "1234"})
    assert r.status_code == 422


def test_real_code_works_without_dev_mode(client, monkeypatch):
    monkeypatch.setattr(otp_service, "OTP_DEV_MODE", False)
    client.post("/api/otp/send", json={"email": "real@x.com"})
    with SessionLocal() as db:
        code = db.query(OtpCode).filter_by(email="real@x.com").first().code
    assert client.post("/api/otp/verify", json={"email": "real@x.com", "code": DEV_CODE}).status_code == 400
    assert client.post("/api/otp/verify", json={"email": "real@x.com", "code": code}).status_code == 200


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
    assert r.status_code == 429  # attempts exhausted even with the right code


def test_attempt_cap_survives_resend(client):
    client.post("/api/otp/send", json={"email": "re@x.com"})
    for _ in range(5):
        client.post("/api/otp/verify", json={"email": "re@x.com", "code": "000000"})
    client.post("/api/otp/send", json={"email": "re@x.com"})  # fresh code, same window
    r = client.post("/api/otp/verify", json={"email": "re@x.com", "code": DEV_CODE})
    assert r.status_code == 429


def test_otp_expiry(client):
    client.post("/api/otp/send", json={"email": "exp@x.com"})
    with SessionLocal() as db:
        row = db.query(OtpCode).filter_by(email="exp@x.com").first()
        row.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    r = client.post("/api/otp/verify", json={"email": "exp@x.com", "code": DEV_CODE})
    assert r.status_code == 400 and "expired" in r.json()["detail"].lower()


def test_old_otp_rows_are_cleaned_up(client):
    client.post("/api/otp/send", json={"email": "old@x.com"})
    with SessionLocal() as db:
        db.query(OtpCode).update({"created_at": utcnow() - timedelta(days=2)})
        db.commit()
    client.post("/api/otp/send", json={"email": "new@x.com"})
    with SessionLocal() as db:
        assert db.query(OtpCode).filter_by(email="old@x.com").count() == 0


def test_auth_mode_reports_dev_mode(client, monkeypatch):
    assert client.get("/api/auth/mode").json() == {"dev_mode": True}
    monkeypatch.setattr(otp_service, "OTP_DEV_MODE", False)
    assert client.get("/api/auth/mode").json() == {"dev_mode": False}


def test_dev_mode_is_impossible_in_production():
    env = {**os.environ, "ENV": "production", "OTP_DEV_MODE": "true"}
    out = subprocess.run(
        [sys.executable, "-c", "from app import otp_service; print(otp_service.OTP_DEV_MODE)"],
        env=env, capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(__file__)),
    )
    assert out.stdout.strip().splitlines()[-1] == "False", out.stderr


def test_production_without_smtp_refuses_to_send(client, monkeypatch):
    monkeypatch.setattr(otp_service, "IS_PROD", True)
    monkeypatch.setattr(mailer, "SMTP_USER", "")
    assert client.post("/api/otp/send", json={"email": "p@x.com"}).status_code == 503


# ---------------- production config guard ----------------

def test_prod_guard_rejects_weak_secrets(monkeypatch):
    monkeypatch.setattr(auth, "IS_PROD", True)
    for bad in (auth.DEFAULT_JWT_SECRET, "short"):
        monkeypatch.setattr(auth, "JWT_SECRET", bad)
        with pytest.raises(RuntimeError):
            auth.check_prod_config()
    monkeypatch.setattr(auth, "JWT_SECRET", "y" * 32)
    auth.check_prod_config()  # strong secret is fine


def test_weak_secret_is_fine_in_dev(monkeypatch):
    monkeypatch.setattr(auth, "IS_PROD", False)
    monkeypatch.setattr(auth, "JWT_SECRET", "short")
    auth.check_prod_config()


# ---------------- clock ----------------

def test_today_starts_at_ist_midnight():
    start = clock.today_start()
    assert start.tzinfo is None
    ist_start = start + timedelta(hours=5, minutes=30)
    assert (ist_start.hour, ist_start.minute, ist_start.second) == (0, 0, 0)
    assert timedelta(0) <= utcnow() - start < timedelta(days=1)


# ---------------- orders ----------------

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
    r = client.get(f"/api/orders/{order['id']}", headers=bearer(token))
    assert r.json()["total"] == 160  # snapshot survives price change


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
    """Customer B must never be able to read customer A's order."""
    order_a = place(client, login("aa@x.com"), make_item()).json()
    r = client.get(f"/api/orders/{order_a['id']}", headers=bearer(login("bb@x.com")))
    assert r.status_code == 404  # not 403 - don't even confirm the order exists
    assert client.get(f"/api/orders/{order_a['id']}").status_code == 401


# ---------------- admin ----------------

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
    assert client.get("/api/admin/orders", headers=bearer(login())).status_code == 401
    assert client.get("/api/admin/orders", headers=bearer(login(OWNER))).status_code == 200


def test_customer_cannot_use_admin_endpoints(client, login, make_item):
    token = login()
    oid = place(client, token, make_item()).json()["id"]
    r = client.patch(f"/api/admin/orders/{oid}/status", json={"status": "ready"}, headers=bearer(token))
    assert r.status_code == 401


def test_owner_sees_full_email_customer_sees_masked(client, login, make_item):
    token = login("someone@gmail.com")
    place(client, token, make_item())
    orders = client.get("/api/admin/orders", headers=bearer(login(OWNER))).json()
    assert orders[0]["email"] == "someone@gmail.com"


def test_stock_toggle_blocks_order_and_shows_in_menu(client, login, make_item):
    item = make_item()
    admin = bearer(login(OWNER))
    r = client.patch(f"/api/admin/menu/{item['id']}/availability", json={"is_available": False}, headers=admin)
    assert r.status_code == 200
    assert client.get("/api/menu").json()[0]["items"][0]["is_available"] is False
    r = place(client, login(), item)
    assert r.status_code == 400 and "out of stock" in r.json()["detail"].lower()


def test_stats_today(client, login, make_item):
    admin = bearer(login(OWNER))
    place(client, login(), make_item("Oreo Shake", full=80))
    stats = client.get("/api/admin/stats/today", headers=admin).json()
    assert stats == {"orders": 1, "revenue": 160, "top_item": "Oreo Shake"}


# ---------------- websockets ----------------

def test_ws_admin_receives_new_order_with_full_email(client, login, make_item):
    admin_token = login(OWNER)
    with client.websocket_connect(f"/ws/admin?token={admin_token}") as ws:
        place(client, login("buyer@gmail.com"), make_item())
        msg = ws.receive_json()
        assert msg["type"] == "new_order" and msg["order"]["order_number"] == 1
        assert msg["order"]["email"] == "buyer@gmail.com"


def test_ws_admin_non_owner_rejected(client, login):
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect(f"/ws/admin?token={login()}"):
            pass
    assert e.value.code == 4401



# ---------------- SMTP delivery (mocked — no real email sent) ----------------

class _FakeSMTP:
    sent = []

    def __init__(self, *a, **k): pass
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def login(self, user, pw): _FakeSMTP.last_login = (user, pw)
    def sendmail(self, frm, to, body): _FakeSMTP.sent.append((frm, to, body))


def test_deliver_sends_mail_over_smtp(monkeypatch):
    import smtplib
    monkeypatch.setattr(mailer, "SMTP_USER", "stall@gmail.com")
    monkeypatch.setattr(mailer, "SMTP_PASS", "app-password")
    monkeypatch.setattr(mailer, "SMTP_PORT", 465)
    monkeypatch.setattr(smtplib, "SMTP_SSL", _FakeSMTP)
    _FakeSMTP.sent = []
    otp_service.deliver("dest@x.com", "567890")
    assert _FakeSMTP.last_login == ("stall@gmail.com", "app-password")
    _, to, body = _FakeSMTP.sent[0]
    assert to == ["dest@x.com"] and "567890" in body


def test_smtp_auth_failure_gives_friendly_503(monkeypatch):
    import smtplib
    from fastapi import HTTPException

    class _AuthFail(_FakeSMTP):
        def login(self, u, p): raise smtplib.SMTPAuthenticationError(535, b"bad creds")

    monkeypatch.setattr(mailer, "SMTP_USER", "stall@gmail.com")
    monkeypatch.setattr(mailer, "SMTP_PASS", "wrong")
    monkeypatch.setattr(mailer, "SMTP_PORT", 465)
    monkeypatch.setattr(smtplib, "SMTP_SSL", _AuthFail)
    with pytest.raises(HTTPException) as e:
        otp_service.deliver("dest@x.com", "567890")
    assert e.value.status_code == 503



def test_mail_from_is_the_sender_and_starttls_is_used_off_465(monkeypatch):
    import smtplib

    class _StartTLS(_FakeSMTP):
        started = False
        def starttls(self): _StartTLS.started = True

    monkeypatch.setattr(mailer, "SMTP_USER", "login@smtp-brevo.com")
    monkeypatch.setattr(mailer, "SMTP_PASS", "key")
    monkeypatch.setattr(mailer, "SMTP_PORT", 2525)
    monkeypatch.setattr(mailer, "MAIL_FROM", "stall@gmail.com")
    monkeypatch.setattr(mailer, "SMTP_FROM_NAME", "Ro-Yan Brews")
    monkeypatch.setattr(smtplib, "SMTP", _StartTLS)
    _FakeSMTP.sent = []
    mailer.send_mail("dest@x.com", "Hi", "Body")
    frm, to, body = _FakeSMTP.sent[0]
    assert _StartTLS.started and _FakeSMTP.last_login == ("login@smtp-brevo.com", "key")
    assert frm == "stall@gmail.com" and "From: Ro-Yan Brews <stall@gmail.com>" in body
