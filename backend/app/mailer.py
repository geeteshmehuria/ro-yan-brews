"""Outgoing email. Two transports, chosen by which env vars are set:

* BREVO_API_KEY  -> Brevo's HTTPS API (port 443). Use this on hosts that block SMTP,
                    e.g. Render's free tier (ports 25/465/587 are blocked there).
* SMTP_USER/PASS -> plain SMTP (Gmail: needs an App Password, not your normal one).
"""
import json
import logging
import os
import smtplib
import urllib.error
import urllib.request
from email.mime.text import MIMEText

from fastapi import HTTPException

log = logging.getLogger("royan.mail")
logging.basicConfig(level=logging.INFO)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))  # 465 = SSL, 587 = STARTTLS
SMTP_USER = os.getenv("SMTP_USER", "")           # your gmail address
SMTP_PASS = os.getenv("SMTP_PASS", "")           # 16-char Google App Password
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Ro-Yan Brews")
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
MAIL_FROM = os.getenv("MAIL_FROM") or SMTP_USER  # must be a sender verified in Brevo


def configured() -> bool:
    return bool(BREVO_API_KEY or (SMTP_USER and SMTP_PASS))


def _via_smtp(to: str, subject: str, body: str) -> None:
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
    msg["To"] = to
    if SMTP_PORT == 465:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as s:
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_USER, [to], msg.as_string())
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_USER, [to], msg.as_string())


def _via_brevo(to: str, subject: str, body: str) -> None:
    payload = {"sender": {"name": SMTP_FROM_NAME, "email": MAIL_FROM}, "to": [{"email": to}],
               "subject": subject, "textContent": body}
    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email", data=json.dumps(payload).encode(), method="POST",
        headers={"api-key": BREVO_API_KEY, "content-type": "application/json", "accept": "application/json"})
    urllib.request.urlopen(req, timeout=15).close()


def send_mail(to: str, subject: str, body: str) -> None:
    """Send one plain-text email; raises HTTPException(503) with a friendly message on failure."""
    try:
        (_via_brevo if BREVO_API_KEY else _via_smtp)(to, subject, body)
    except (smtplib.SMTPAuthenticationError, urllib.error.HTTPError) as e:
        if isinstance(e, urllib.error.HTTPError) and e.code not in (401, 403):
            log.error("Brevo rejected the email (%s): %s", e.code, e.read()[:300])
            raise HTTPException(503, "Could not send the email — try again in a minute")
        log.error("Email credentials rejected — check SMTP_PASS (Google App Password) / BREVO_API_KEY "
                  "and that MAIL_FROM is a verified sender")
        raise HTTPException(503, "Email service is misconfigured — try again later")
    except Exception as e:
        log.error("Email send failed: %s", e)
        raise HTTPException(503, "Could not send the email — try again in a minute")
