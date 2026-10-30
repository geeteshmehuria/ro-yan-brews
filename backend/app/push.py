"""Push notifications to the owner's Android app through Firebase Cloud Messaging (HTTP v1).

Off unless FIREBASE_SERVICE_ACCOUNT holds a Firebase service-account key (the whole JSON).
Only phones registered by an admin email get pushes. `notify_admins` runs as a background
task and never raises: a failed push must not break an order — the WebSocket alert still works.
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
CHANNEL_ID = "orders"  # created by the app (src/admin/push.js) with sound + vibration
_session = None


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


def notify_admins(title: str, body: str, order_id: int) -> None:
    if not configured():
        return
    try:
        with SessionLocal() as db:
            rows = [r for r in db.query(PushToken).all() if auth.is_admin_email(r.email)]
            if not rows:
                return
            session, url = _client()
            for row in rows:
                r = session.post(url, timeout=10, json={"message": {
                    "token": row.token,
                    "notification": {"title": title, "body": body},
                    "data": {"order_id": str(order_id)},
                    "android": {"priority": "high", "notification": {
                        "channel_id": CHANNEL_ID, "sound": "default", "tag": f"order-{order_id}"}},
                }})
                if r.status_code == 404 or (r.status_code == 400 and "registration token" in r.text):
                    db.delete(row)  # app uninstalled / token rotated: stop sending to it
                elif r.status_code >= 400:
                    request_log.record("TASK", "push", status=r.status_code, error=r.text[:500])
            db.commit()
    except Exception as exc:
        log.error("push failed: %s", exc)
        request_log.record("TASK", "push", error=request_log.describe(exc))
