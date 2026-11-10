"""Open / Paused and the stall's phone number: anyone can read them, only the owner can change them."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.features.store import store_service
from app.features.store.store_schemas import PhoneIn, StoreIn
from app.shared import auth
from app.shared.database import get_db
from app.shared.models import Setting
from app.shared.ws_manager import manager

router = APIRouter(tags=["store"])


def _save(db: Session, key: str, value: Optional[str]) -> None:
    """Set one setting; None removes it (back to the default)."""
    row = db.get(Setting, key)
    if value is None:
        if row is not None:
            db.delete(row)
    elif row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value
    db.commit()


async def _broadcast(db: Session) -> dict:
    status = store_service.store_status(db)
    await manager.broadcast_menu({"type": "store", **status})
    await manager.broadcast_admin({"type": "store", **status})  # the owner's other devices
    return status


@router.get("/api/store")
def store_status(db: Session = Depends(get_db)) -> dict:
    """Is the stall taking orders, and its phone number. Changes are pushed as {type: "store"} on /ws/menu."""
    return store_service.store_status(db)


@router.patch("/api/admin/store")
async def set_store(body: StoreIn, request: Request, db: Session = Depends(get_db)) -> dict:
    """Open / pause new orders. Orders already placed carry on as normal."""
    auth.require_admin(request)
    _save(db, "accepting_orders", "1" if body.accepting_orders else "0")
    return await _broadcast(db)


@router.patch("/api/admin/store/phone")
async def set_phone(body: PhoneIn, request: Request, db: Session = Depends(get_db)) -> dict:
    """The number customers see as "Call the stall" on their orders. Blank removes it."""
    auth.require_admin(request)
    try:
        phone = store_service.clean_phone(body.phone)
    except ValueError as exc:  # a plain 400, so the owner sees the reason (422s show a generic message)
        raise HTTPException(400, str(exc)) from exc
    _save(db, "stall_phone", phone)
    return await _broadcast(db)
