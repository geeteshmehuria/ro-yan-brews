"""Outgoing email over SMTP.

Gmail: SMTP_HOST=smtp.gmail.com, port 465/587, SMTP_PASS = a Google App Password.
Brevo: SMTP_HOST=smtp-relay.brevo.com, SMTP_USER = the Brevo SMTP login, SMTP_PASS = the
       Brevo SMTP key, MAIL_FROM = a sender verified in Brevo.
Render's free tier blocks outbound ports 25/465/587 — use port 2525 (Brevo supports it).
"""
import logging
import os
import smtplib
from email.mime.text import MIMEText

from fastapi import HTTPException

log = logging.getLogger("royan.mail")
logging.basicConfig(level=logging.INFO)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))  # 465 = SSL, anything else = STARTTLS
SMTP_USER = os.getenv("SMTP_USER", "")           # SMTP login
SMTP_PASS = os.getenv("SMTP_PASS", "")           # App Password / SMTP key
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Ro-Yan Brews")
MAIL_FROM = os.getenv("MAIL_FROM") or SMTP_USER  # the visible sender address


class MailError(Exception):
    """Carries the underlying failure plus where we tried to connect (for t_log)."""


def configured() -> bool:
    return bool(SMTP_USER and SMTP_PASS)


def send_mail(to: str, subject: str, body: str) -> None:
    """Send one plain-text email; raises HTTPException(503) with a friendly message on failure."""
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = f"{SMTP_FROM_NAME} <{MAIL_FROM}>"
    msg["To"] = to
    try:
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as s:
                s.login(SMTP_USER, SMTP_PASS)
                s.sendmail(MAIL_FROM, [to], msg.as_string())
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
                s.starttls()
                s.login(SMTP_USER, SMTP_PASS)
                s.sendmail(MAIL_FROM, [to], msg.as_string())
    except smtplib.SMTPAuthenticationError as e:
        log.error("SMTP login rejected — check SMTP_USER / SMTP_PASS (Gmail App Password or Brevo SMTP key)")
        raise HTTPException(503, "Email service is misconfigured — try again later") from _why(e)
    except Exception as e:
        log.error("SMTP send failed: %s (is MAIL_FROM a verified sender, and is the port allowed by the host?)", e)
        raise HTTPException(503, "Could not send the email — try again in a minute") from _why(e)


def _why(e: Exception) -> MailError:
    return MailError(f"{type(e).__name__}: {e} [SMTP {SMTP_HOST}:{SMTP_PORT}, from {MAIL_FROM}]")
