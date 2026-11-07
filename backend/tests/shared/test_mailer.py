"""Sending mail over SMTP."""
import pytest

from app.features.auth import otp_service
from app.shared import mailer


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
