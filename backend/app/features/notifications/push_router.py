"""Android app push-notification tokens: registered after login, removed on logout."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.features.notifications import push_service
from app.features.notifications.push_schemas import PushTokenIn
from app.shared import auth
from app.shared.database import get_db
from app.shared.models import PushToken

router = APIRouter(tags=["notifications"])


@router.post("/api/push-token")
def register_push_token(body: PushTokenIn, request: Request, db: Session = Depends(get_db)) -> dict:
    """The Android app registers its FCM token after login: the owner then gets order alerts,
    a customer gets their own orders' progress."""
    push_service.save_push_token(db, body.token, auth.current_customer(request))
    return {"registered": True, "enabled": push_service.configured()}


@router.post("/api/push-token/remove")
def remove_push_token(body: PushTokenIn, request: Request, db: Session = Depends(get_db)) -> dict:
    """Called on logout, so a logged-out phone stops getting notifications."""
    auth.current_customer(request)
    db.query(PushToken).filter_by(token=body.token).delete()
    db.commit()
    return {"removed": True}
