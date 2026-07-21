import os
import time

import jwt
from fastapi import HTTPException, Request

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
# The one account that gets the admin dashboard. Log in with this email (email +
# OTP, same as any customer) and you are the owner; every other email is a normal
# customer. There is no separate admin password — being this email *is* being admin.
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "geeteshmaihuria@gmail.com").strip().lower()
IS_PROD = os.getenv("ENV", "dev") == "production"


def is_admin_email(email: str) -> bool:
    return (email or "").strip().lower() == ADMIN_EMAIL


def create_session_token(customer_id: int, email: str) -> str:
    payload = {
        "cid": customer_id,
        "email": email,
        "is_admin": is_admin_email(email),
        "exp": int(time.time()) + 60 * 60 * 24 * 30,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _decode(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])


def _token_from_request(request: Request) -> str:
    # Bearer header wins over the cookie: the frontend authenticates with the
    # localStorage token, and an explicit Authorization header should never be
    # shadowed by a stale session cookie from another tab/account.
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.cookies.get("session") or ""


def current_customer(request: Request) -> dict:
    token = _token_from_request(request)
    if not token:
        raise HTTPException(401, "Please log in first")
    try:
        return _decode(token)
    except jwt.PyJWTError:
        raise HTTPException(401, "Session expired — please log in again")


def require_admin(request: Request) -> dict:
    session = current_customer(request)
    if not is_admin_email(session.get("email", "")):
        raise HTTPException(401, "Admin access only")
    return session


def token_is_admin(token: str) -> bool:
    """For the admin WebSocket, which passes the JWT as a ?token= query param."""
    if not token:
        return False
    try:
        session = _decode(token)
    except jwt.PyJWTError:
        return False
    return is_admin_email(session.get("email", ""))
