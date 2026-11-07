"""Android app push-notification tokens (register on login, remove on logout)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...core import auth
from ...db.session import get_db
from ...models import PushToken
from ...schemas import PushTokenIn
from ...services import push

router = APIRouter(tags=["push"])


def _save_push_token(db: Session, token: str, session: dict) -> None:
    """A phone belongs to whoever logged in on it last: re-registering moves it to them."""
    row = db.query(PushToken).filter_by(token=token).first()
    if row is None:
        db.add(PushToken(token=token, email=session["email"], customer_id=session["cid"]))
    else:
        row.email, row.customer_id = session["email"], session["cid"]
    try:
        db.commit()
    except IntegrityError:  # registered twice at once
        db.rollback()


@router.post("/api/push-token")
def register_push_token(body: PushTokenIn, request: Request, db: Session = Depends(get_db)) -> dict:
    """The Android app registers its FCM token after login: the owner then gets order alerts,
    a customer gets their own orders' progress."""
    _save_push_token(db, body.token, auth.current_customer(request))
    return {"registered": True, "enabled": push.configured()}


@router.post("/api/push-token/remove")
def remove_push_token(body: PushTokenIn, request: Request, db: Session = Depends(get_db)) -> dict:
    """Called on logout, so a logged-out phone stops getting notifications."""
    auth.current_customer(request)
    db.query(PushToken).filter_by(token=body.token).delete()
    db.commit()
    return {"removed": True}
