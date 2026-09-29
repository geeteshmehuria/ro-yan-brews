"""Email OTP. `deliver` sends real mail through SMTP (Gmail: needs an App Password)
when SMTP_USER/SMTP_PASS are set; otherwise, outside production only, it logs the
code to the console. The fixed code 123456 is accepted only when OTP_DEV_MODE=true
*and* ENV is not production."""
import hmac
import logging
import os
import secrets
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import mailer
from .auth import IS_PROD
from .clock import utcnow
from .models import OtpCode

log = logging.getLogger("royan.otp")
logging.basicConfig(level=logging.INFO)

OTP_DEV_MODE = os.getenv("OTP_DEV_MODE", "false").lower() == "true" and not IS_PROD
DEV_CODE = "123456"
OTP_TTL_MINUTES = 5
MAX_SENDS_PER_WINDOW = 3
SEND_WINDOW_MINUTES = 10
MAX_VERIFY_ATTEMPTS = 5  # shared by every code sent in the window, so resending doesn't reset it

def deliver(email: str, code: str) -> None:
    if not mailer.configured():
        if IS_PROD:
            log.error("SMTP_USER/SMTP_PASS are not set — cannot send login codes")
            raise HTTPException(503, "Email service is not configured — try again later")
        log.info("DEV OTP for %s: %s", email, code)
        return
    mailer.send_mail(
        email,
        f"{code} is your Ro-Yan Brews code",
        f"Your Ro-Yan Brews login code is: {code}\n\n"
        f"It expires in {OTP_TTL_MINUTES} minutes. "
        "If you didn't request this, ignore this email.",
    )


def _recent(db: Session, email: str):
    window_start = utcnow() - timedelta(minutes=SEND_WINDOW_MINUTES)
    return db.query(OtpCode).filter(OtpCode.email == email, OtpCode.created_at >= window_start)


def send_otp(db: Session, email: str) -> None:
    db.query(OtpCode).filter(OtpCode.created_at < utcnow() - timedelta(days=1)).delete()
    if _recent(db, email).count() >= MAX_SENDS_PER_WINDOW:
        raise HTTPException(429, "Too many OTP requests — please wait a few minutes")
    code = f"{secrets.randbelow(10**6):06d}"
    deliver(email, code)  # send first — don't store a code that never went out
    db.add(OtpCode(email=email, code=code, expires_at=utcnow() + timedelta(minutes=OTP_TTL_MINUTES)))
    db.commit()


def _matches(given: str, expected: str) -> bool:
    return hmac.compare_digest(given.encode(), expected.encode())


def verify_otp(db: Session, email: str, code: str) -> None:
    row = (
        db.query(OtpCode)
        .filter(OtpCode.email == email, OtpCode.verified == False)  # noqa: E712
        .order_by(OtpCode.created_at.desc())
        .first()
    )
    if row is None:
        raise HTTPException(400, "Please request an OTP first")
    if sum(r.attempt_count for r in _recent(db, email)) >= MAX_VERIFY_ATTEMPTS:
        raise HTTPException(429, "Too many wrong attempts — please wait a few minutes and request a new OTP")
    if utcnow() > row.expires_at:
        raise HTTPException(400, "OTP expired — please request a new one")

    row.attempt_count += 1
    ok = _matches(code, row.code) or (OTP_DEV_MODE and _matches(code, DEV_CODE))
    row.verified = ok
    db.commit()
    if not ok:
        raise HTTPException(400, "Wrong OTP — please check and try again")
