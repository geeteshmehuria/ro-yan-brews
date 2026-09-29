"""Outgoing email over SMTP (Gmail: needs an App Password, not your normal one)."""
import logging
import os
import smtplib
from email.mime.text import MIMEText

from fastapi import HTTPException

log = logging.getLogger("royan.mail")
logging.basicConfig(level=logging.INFO)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))  # 465 = SSL, 587 = STARTTLS
SMTP_USER = os.getenv("SMTP_USER", "")           # your gmail address
SMTP_PASS = os.getenv("SMTP_PASS", "")           # 16-char Google App Password
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Ro-Yan Brews")


def configured() -> bool:
    return bool(SMTP_USER and SMTP_PASS)


def send_mail(to: str, subject: str, body: str) -> None:
    """Send one plain-text email; raises HTTPException(503) with a friendly message on failure."""
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
    msg["To"] = to
    try:
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as s:
                s.login(SMTP_USER, SMTP_PASS)
                s.sendmail(SMTP_USER, [to], msg.as_string())
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
                s.starttls()
                s.login(SMTP_USER, SMTP_PASS)
                s.sendmail(SMTP_USER, [to], msg.as_string())
    except smtplib.SMTPAuthenticationError:
        log.error("SMTP auth failed — is SMTP_PASS a Google App Password?")
        raise HTTPException(503, "Email service is misconfigured — try again later")
    except Exception as e:
        log.error("SMTP send failed: %s", e)
        raise HTTPException(503, "Could not send the email — try again in a minute")
