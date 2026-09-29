from datetime import timedelta

from app import mailer, otp_service, request_log
from app.clock import utcnow
from app.db import SessionLocal
from app.models import TLog

from conftest import bearer


def rows():
    with SessionLocal() as db:
        return db.query(TLog).order_by(TLog.id).all()


def test_successful_requests_are_not_logged(client):
    client.get("/api/menu")
    client.get("/api/health")
    assert rows() == []


def test_failed_request_is_logged_with_request_info(client, login):
    token = login("someone@x.com")
    r = client.get("/api/orders/999", headers={**bearer(token), "user-agent": "pytest-agent",
                                               "x-forwarded-for": "203.0.113.9, 10.0.0.1"})
    assert r.status_code == 404
    (row,) = rows()
    assert (row.method, row.path, row.status) == ("GET", "/api/orders/999", 404)
    assert row.error == "Order not found"
    assert row.user_email == "someone@x.com" and row.user_agent == "pytest-agent"
    assert row.client_ip == "203.0.113.9" and row.duration_ms is not None


def test_query_string_and_tokens_are_never_stored(client):
    client.get("/api/orders/mine?token=SECRET123", headers=bearer("not-a-real-token"))
    (row,) = rows()
    assert row.path == "/api/orders/mine" and "SECRET123" not in (row.error or "")


def test_validation_errors_keep_field_names_but_not_values(client):
    r = client.post("/api/otp/send", json={"email": "private-not-an-email"})
    assert r.status_code == 422
    (row,) = rows()
    assert "email" in row.error and "private-not-an-email" not in row.error


def test_email_failure_records_the_real_reason(client, monkeypatch):
    import smtplib

    def boom(*a, **k):
        raise TimeoutError("timed out")
    monkeypatch.setattr(mailer, "SMTP_USER", "stall@gmail.com")
    monkeypatch.setattr(mailer, "SMTP_PASS", "app-password")
    monkeypatch.setattr(mailer, "SMTP_PORT", 465)
    monkeypatch.setattr(smtplib, "SMTP_SSL", boom)
    r = client.post("/api/otp/send", json={"email": "who@x.com"})
    assert r.status_code == 503 and r.json()["detail"] == "Could not send the email — try again in a minute"
    (row,) = rows()
    assert row.status == 503 and "TimeoutError: timed out" in row.error
    assert "[SMTP " in row.error  # where we tried to connect
    assert "app-password" not in row.error


def test_unhandled_exception_is_logged_with_traceback_and_returns_500(client, monkeypatch):
    def broken(*a, **k):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(otp_service, "send_otp", broken)
    r = client.post("/api/otp/send", json={"email": "who@x.com"})
    assert r.status_code == 500 and r.json() == {"detail": "Internal Server Error"}
    (row,) = rows()
    assert row.status == 500 and row.error.rstrip().endswith("RuntimeError: kaboom") and "File " in row.error


def test_rejected_cors_preflight_is_logged_with_its_origin(client):
    r = client.options("/api/menu", headers={"Origin": "https://evil.example",
                                            "Access-Control-Request-Method": "GET"})
    assert r.status_code == 400
    (row,) = rows()
    assert row.method == "OPTIONS" and row.origin == "https://evil.example"


def test_background_task_failure_is_logged(client, login, make_item, monkeypatch):
    from conftest import place
    owner, token = login("owner@royan.test"), login()
    oid = place(client, token, make_item()).json()["id"]

    def boom(*a, **k):
        raise RuntimeError("smtp down")
    monkeypatch.setattr(mailer, "SMTP_USER", "stall@gmail.com")
    monkeypatch.setattr(mailer, "SMTP_PASS", "app-password")
    monkeypatch.setattr(mailer, "send_mail", boom)
    client.patch(f"/api/admin/orders/{oid}/status", json={"status": "ready"}, headers=bearer(owner))
    (row,) = rows()
    assert (row.method, row.path) == ("TASK", "notify_ready") and "smtp down" in row.error


def test_old_rows_are_pruned(client):
    request_log.record("GET", "/old")
    request_log.record("GET", "/new")
    with SessionLocal() as db:
        db.query(TLog).filter_by(path="/old").update({"created_at": utcnow() - timedelta(days=31)})
        db.commit()
    request_log.prune()
    assert [r.path for r in rows()] == ["/new"]


def test_logging_never_breaks_a_request(client, monkeypatch):
    def down():
        raise RuntimeError("database down")
    monkeypatch.setattr(request_log, "SessionLocal", down)
    assert client.get("/api/orders/mine").status_code == 401  # still answers normally
