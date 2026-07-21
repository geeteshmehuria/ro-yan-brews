"""OTP via email. Provider interface: SmtpEmailProvider sends real mail through
Gmail SMTP when SMTP_USER/SMTP_PASS are set; otherwise DevOtpProvider logs the
code to the console (and code 1234 is accepted while OTP_DEV_MODE=true)."""
import logging
import os
import random
import smtplib
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import OtpCode

log = logging.getLogger("royan.otp")
logging.basicConfig(level=logging.INFO)

OTP_DEV_MODE = os.getenv("OTP_DEV_MODE", "true").lower() == "true"
OTP_TTL_MINUTES = 5
MAX_SENDS_PER_WINDOW = 3
SEND_WINDOW_MINUTES = 10
MAX_VERIFY_ATTEMPTS = 5

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))  # 465 = SSL, 587 = STARTTLS
SMTP_USER = os.getenv("SMTP_USER", "")           # your gmail address
SMTP_PASS = os.getenv("SMTP_PASS", "")           # 16-char Google App Password
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Ro-Yan Brews")


class OtpProvider(ABC):
    @abstractmethod
    def send(self, email: str, code: str) -> None: ...


class DevOtpProvider(OtpProvider):
    """Logs the OTP instead of emailing. Code '123456' always accepted in dev."""

    def send(self, email: str, code: str) -> None:
        log.info("DEV OTP for %s: %s (or use 123456)", email, code)


class SmtpEmailProvider(OtpProvider):
    """Real email via SMTP (Gmail: needs an App Password, not your normal one)."""

    def send(self, email: str, code: str) -> None:
        msg = MIMEText(
            f"Your Ro-Yan Brews login code is: {code}\n\n"
            f"It expires in {OTP_TTL_MINUTES} minutes. "
            "If you didn't request this, ignore this email."
        )
        msg["Subject"] = f"{code} is your Ro-Yan Brews code"
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
        msg["To"] = email
        try:
            if SMTP_PORT == 465:
                with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as s:
                    s.login(SMTP_USER, SMTP_PASS)
                    s.sendmail(SMTP_USER, [email], msg.as_string())
            else:
                with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
                    s.starttls()
                    s.login(SMTP_USER, SMTP_PASS)
                    s.sendmail(SMTP_USER, [email], msg.as_string())
        except smtplib.SMTPAuthenticationError:
            log.error("SMTP auth failed — is SMTP_PASS a Google App Password?")
            raise HTTPException(503, "Email service is misconfigured — try again later")
        except Exception as e:
            log.error("SMTP send failed: %s", e)
            raise HTTPException(503, "Could not send the email — try again in a minute")


def get_provider() -> OtpProvider:
    if SMTP_USER and SMTP_PASS:
        return SmtpEmailProvider()
    return DevOtpProvider()


provider: OtpProvider = get_provider()


def send_otp(db: Session, email: str) -> None:
    window_start = datetime.utcnow() - timedelta(minutes=SEND_WINDOW_MINUTES)
    recent = (
        db.query(OtpCode)
        .filter(OtpCode.email == email, OtpCode.created_at >= window_start)
        .count()
    )
    if recent >= MAX_SENDS_PER_WINDOW:
        raise HTTPException(429, "Too many OTP requests — please wait a few minutes")
    code = f"{random.randint(0, 999999):06d}"
    provider.send(email, code)  # send first — don't store a code that never went out
    db.add(OtpCode(
        email=email,
        code=code,
        expires_at=datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES),
    ))
    db.commit()


def verify_otp(db: Session, email: str, code: str) -> bool:
    row = (
        db.query(OtpCode)
        .filter(OtpCode.email == email, OtpCode.verified == False)  # noqa: E712
        .order_by(OtpCode.created_at.desc())
        .first()
    )
    if row is None:
        raise HTTPException(400, "Please request an OTP first")
    if row.attempt_count >= MAX_VERIFY_ATTEMPTS:
        raise HTTPException(429, "Too many wrong attempts — please request a new OTP")
    if datetime.utcnow() > row.expires_at:
        raise HTTPException(400, "OTP expired — please request a new one")

    row.attempt_count += 1
    ok = code == row.code or (OTP_DEV_MODE and code == "123456")
    if ok:
        row.verified = True
    db.commit()
    if not ok:
        raise HTTPException(400, "Wrong OTP — please check and try again")
    return True
