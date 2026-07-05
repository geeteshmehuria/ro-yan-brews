import os
import time

import jwt
from fastapi import HTTPException, Request

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
ADMIN_PIN = os.getenv("ADMIN_PIN", "4321")
IS_PROD = os.getenv("ENV", "dev") == "production"


def create_session_token(customer_id: int, phone: str) -> str:
    payload = {"cid": customer_id, "phone": phone, "exp": int(time.time()) + 60 * 60 * 24 * 30}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def current_customer(request: Request) -> dict:
    token = request.cookies.get("session")
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(401, "Please verify your phone number first")
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Session expired — please verify your phone number again")


def require_admin(request: Request) -> None:
    pin = request.headers.get("x-admin-pin") or request.query_params.get("pin")
    if pin != ADMIN_PIN:
        raise HTTPException(401, "Wrong admin PIN")
