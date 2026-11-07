"""Login with an emailed code: validation, rate limits, expiry, dev mode."""
import os
import subprocess
import sys
from datetime import timedelta

from conftest import BACKEND_DIR, DEV_CODE

from app.features.auth import otp_service
from app.shared import mailer
from app.shared.clock import utcnow
from app.shared.database import SessionLocal
from app.shared.models import OtpCode


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
    assert client.get("/api/auth/mode").json()["dev_mode"] is True
    monkeypatch.setattr(otp_service, "OTP_DEV_MODE", False)
    assert client.get("/api/auth/mode").json()["dev_mode"] is False


def test_dev_mode_is_impossible_in_production():
    env = {**os.environ, "ENV": "production", "OTP_DEV_MODE": "true"}
    out = subprocess.run(
        [sys.executable, "-c", "from app.features.auth import otp_service; print(otp_service.OTP_DEV_MODE)"],
        env=env, capture_output=True, text=True, cwd=BACKEND_DIR,
    )
    assert out.stdout.strip().splitlines()[-1] == "False", out.stderr


def test_production_without_smtp_refuses_to_send(client, monkeypatch):
    monkeypatch.setattr(otp_service, "IS_PROD", True)
    monkeypatch.setattr(mailer, "SMTP_USER", "")
    assert client.post("/api/otp/send", json={"email": "p@x.com"}).status_code == 503
