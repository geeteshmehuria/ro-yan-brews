import os
import time
from typing import Optional

import jwt
from fastapi import HTTPException, Request
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

DEFAULT_JWT_SECRET = "dev-secret-change-me"
JWT_SECRET = os.getenv("JWT_SECRET", DEFAULT_JWT_SECRET)
# Owner account(s) that get the admin dashboard. Configured strictly via ADMIN_EMAIL env var (comma-separated).
ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.getenv("ADMIN_EMAIL", "").split(",")
    if e.strip()
}

IS_PROD = os.getenv("ENV", "dev") == "production"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()

DAY = 60 * 60 * 24


GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


def verify_google_token(credential: str) -> dict:
    """Verify a Google ID token *issued for our client ID*; returns {email, name}.
    Without GOOGLE_CLIENT_ID, Google login is off: verifying with no audience would accept
    a token Google issued to any other site, letting that site log in as its users here."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(404, "Google sign-in is not enabled")
    try:
        idinfo = id_token.verify_oauth2_token(credential, google_requests.Request(), GOOGLE_CLIENT_ID)
    except Exception as e:  # bad signature, expired, wrong audience, Google certs unreachable
        raise HTTPException(400, "Google sign-in failed — please try again") from e
    email = (idinfo.get("email") or "").strip().lower()
    if idinfo.get("iss") not in GOOGLE_ISSUERS or not email or idinfo.get("email_verified") not in (True, "true"):
        raise HTTPException(400, "Google sign-in failed — please try again")
    return {"email": email, "name": idinfo.get("name")}


def check_prod_config() -> None:
    """Refuse to start in production with a forgeable JWT secret."""
    if IS_PROD and (JWT_SECRET == DEFAULT_JWT_SECRET or len(JWT_SECRET) < 32):
        raise RuntimeError("JWT_SECRET must be set to a random string of 32+ characters in production")


def is_admin_email(email: str) -> bool:
    clean = (email or "").strip().lower()
    return bool(clean) and clean in ADMIN_EMAILS


def create_session_token(customer_id: int, email: str) -> str:
    admin = is_admin_email(email)
    payload = {
        "cid": customer_id,
        "email": email,
        "is_admin": admin,
        "exp": int(time.time()) + DAY * (7 if admin else 30),  # owner re-logs in weekly
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _decode(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])


def current_customer(request: Request) -> dict:
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(401, "Please log in first")
    try:
        return _decode(header[7:])
    except jwt.PyJWTError:
        raise HTTPException(401, "Session expired — please log in again")


def require_admin(request: Request) -> dict:
    session = current_customer(request)
    if not is_admin_email(session.get("email", "")):
        raise HTTPException(403, "Admin access only")
    return session


def _ws_session(token: str) -> Optional[dict]:
    """WebSockets can't send headers, so they pass the JWT as ?token=."""
    try:
        return _decode(token) if token else None
    except jwt.PyJWTError:
        return None


def token_is_admin(token: str) -> bool:
    session = _ws_session(token)
    return bool(session) and is_admin_email(session.get("email", ""))


def token_customer_id(token: str) -> Optional[int]:
    session = _ws_session(token)
    return session["cid"] if session else None
