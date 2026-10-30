"""Push notifications to the Android app through Firebase Cloud Messaging (HTTP v1).

Off unless FIREBASE_SERVICE_ACCOUNT holds a Firebase service-account key (the whole JSON).
Each row in push_tokens is one phone, owned by whoever last logged in on it there:
- the owner's phones (email in ADMIN_EMAILS) get new / cancelled orders (`notify_admins`);
- a customer's phones (customer_id) get their own order's progress (`notify_customer`).
Both run as background tasks and never raise: a failed push must not break an order — the
WebSocket updates and the "ready" email still work.
"""
import json
import logging
import os

from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

from . import auth, request_log
from .db import SessionLocal
from .models import PushToken

log = logging.getLogger("royan.push")

_KEY = os.getenv("FIREBASE_SERVICE_ACCOUNT", "")
CHANNEL_ID = "orders"         # owner: new/cancelled orders. Created by the app (src/push.js)
CUSTOMER_CHANNEL_ID = "status"  # customer: their order's progress
_session = None

# What the customer is told when the owner moves their order (status -> title, body).
CUSTOMER_MESSAGES = {
    "preparing": ("👨‍🍳 Order #{n} is being prepared", "We'll let you know the moment it's ready."),
    "ready": ("🎉 Order #{n} is ready!", "Collect it at the counter and pay ₹{total} cash."),
    "completed": ("Thanks for your order #{n}", "How was your food? Tap to rate it."),
    "cancelled": ("Order #{n} was cancelled", "Sorry — the stall couldn't make it. Please ask at the counter."),
}


def configured() -> bool:
    return bool(_KEY)


def _client() -> tuple:
    global _session
    info = json.loads(_KEY)
    if _session is None:
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/firebase.messaging"])
        _session = AuthorizedSession(creds)
    return _session, f"https://fcm.googleapis.com/v1/projects/{info['project_id']}/messages:send"


def _send(pick, title: str, body: str, data: dict, channel: str, tag: str) -> None:
    """Send to every registered phone `pick(row)` accepts. Never raises."""
    if not configured():
        return
    try:
        with SessionLocal() as db:
            rows = [r for r in db.query(PushToken).all() if pick(r)]
            if not rows:
                return
            session, url = _client()
            for row in rows:
                r = session.post(url, timeout=10, json={"message": {
                    "token": row.token,
                    "notification": {"title": title, "body": body},
                    "data": {k: str(v) for k, v in data.items()},  # FCM data values must be strings
                    "android": {"priority": "high", "notification": {
                        "channel_id": channel, "sound": "default", "tag": tag}},
                }})
                if r.status_code == 404 or (r.status_code == 400 and "registration token" in r.text):
                    db.delete(row)  # app uninstalled / token rotated: stop sending to it
                elif r.status_code >= 400:
                    request_log.record("TASK", "push", status=r.status_code, error=r.text[:500])
            db.commit()
    except Exception as exc:
        log.error("push failed: %s", exc)
        request_log.record("TASK", "push", error=request_log.describe(exc))


def notify_admins(title: str, body: str, order_id: int, kind: str = "new_order") -> None:
    """The owner's phones: a new order, or a customer cancelled one."""
    _send(lambda r: auth.is_admin_email(r.email), title, body,
          {"order_id": order_id, "kind": kind}, CHANNEL_ID, f"order-{order_id}")


def notify_customer(customer_id: int, order_id: int, order_number: int, total: int, status: str) -> None:
    """The customer's phones: the owner moved their order to `status`."""
    if status not in CUSTOMER_MESSAGES:
        return
    title, body = (t.format(n=order_number, total=total) for t in CUSTOMER_MESSAGES[status])
    # one notification per order, replaced as it progresses (tag), so the shade doesn't fill up
    _send(lambda r: r.customer_id == customer_id and not auth.is_admin_email(r.email), title, body,
          {"order_id": order_id, "kind": status}, CUSTOMER_CHANNEL_ID, f"my-order-{order_id}")
