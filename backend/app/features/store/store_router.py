"""Open / Paused: anyone can read it, only the owner can change it."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.features.store.store_schemas import StoreIn
from app.features.store.store_service import PAUSED_MESSAGE, accepting_orders
from app.shared import auth
from app.shared.database import get_db
from app.shared.models import Setting
from app.shared.ws_manager import manager

router = APIRouter(tags=["store"])


@router.get("/api/store")
def store_status(db: Session = Depends(get_db)) -> dict:
    """Is the stall taking orders? Changes are pushed as {type: "store"} on /ws/menu."""
    open_ = accepting_orders(db)
    return {"accepting_orders": open_, "message": None if open_ else PAUSED_MESSAGE}


@router.patch("/api/admin/store")
async def set_store(body: StoreIn, request: Request, db: Session = Depends(get_db)) -> dict:
    """Open / pause new orders. Orders already placed carry on as normal."""
    auth.require_admin(request)
    row = db.get(Setting, "accepting_orders")
    if row is None:
        db.add(Setting(key="accepting_orders", value="1" if body.accepting_orders else "0"))
    else:
        row.value = "1" if body.accepting_orders else "0"
    db.commit()
    status = {"accepting_orders": body.accepting_orders,
              "message": None if body.accepting_orders else PAUSED_MESSAGE}
    await manager.broadcast_menu({"type": "store", **status})
    await manager.broadcast_admin({"type": "store", **status})  # the owner's other devices
    return status
