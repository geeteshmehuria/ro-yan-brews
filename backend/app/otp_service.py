"""OTP behind a provider interface — swap DevOtpProvider for MSG91/Twilio later
by implementing OtpProvider.send() in one new class. Nothing else changes."""
import logging
import os
import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta

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


class OtpProvider(ABC):
    @abstractmethod
    def send(self, phone: str, code: str) -> None: ...


class DevOtpProvider(OtpProvider):
    """Logs the OTP instead of sending an SMS. Code '1234' always accepted in dev."""

    def send(self, phone: str, code: str) -> None:
        log.info("DEV OTP for %s: %s (or use 1234)", phone, code)


provider: OtpProvider = DevOtpProvider()


def send_otp(db: Session, phone: str) -> None:
    window_start = datetime.utcnow() - timedelta(minutes=SEND_WINDOW_MINUTES)
    recent = (
        db.query(OtpCode)
        .filter(OtpCode.phone_number == phone, OtpCode.created_at >= window_start)
        .count()
    )
    if recent >= MAX_SENDS_PER_WINDOW:
        raise HTTPException(429, "Too many OTP requests — please wait a few minutes")
    code = f"{random.randint(0, 9999):04d}"
    db.add(OtpCode(
        phone_number=phone,
        code=code,
        expires_at=datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES),
    ))
    db.commit()
    provider.send(phone, code)


def verify_otp(db: Session, phone: str, code: str) -> bool:
    row = (
        db.query(OtpCode)
        .filter(OtpCode.phone_number == phone, OtpCode.verified == False)  # noqa: E712
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
    ok = code == row.code or (OTP_DEV_MODE and code == "1234")
    if ok:
        row.verified = True
    db.commit()
    if not ok:
        raise HTTPException(400, "Wrong OTP — please check and try again")
    return True
