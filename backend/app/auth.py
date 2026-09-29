import os
import time
from typing import Optional

import jwt
from fastapi import HTTPException, Request

DEFAULT_JWT_SECRET = "dev-secret-change-me"
JWT_SECRET = os.getenv("JWT_SECRET", DEFAULT_JWT_SECRET)
# The one account that gets the admin dashboard. Log in with this email (email +
# OTP, same as any customer) and you are the owner; every other email is a normal
# customer. There is no separate admin password — being this email *is* being admin.
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "geeteshmaihuria@gmail.com").strip().lower()
IS_PROD = os.getenv("ENV", "dev") == "production"

DAY = 60 * 60 * 24


def check_prod_config() -> None:
    """Refuse to start in production with a forgeable JWT secret."""
    if IS_PROD and (JWT_SECRET == DEFAULT_JWT_SECRET or len(JWT_SECRET) < 32):
        raise RuntimeError("JWT_SECRET must be set to a random string of 32+ characters in production")


def is_admin_email(email: str) -> bool:
    return (email or "").strip().lower() == ADMIN_EMAIL


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
        raise HTTPException(401, "Admin access only")
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
