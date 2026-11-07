"""Owner: the order queue, status changes, stock toggles and the Open / Paused switch."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ...core import auth
from ...core.clock import today_start, utcnow
from ...db.session import get_db
from ...models import CANCELLED, CLOSED, NOT_COLLECTED, ORDER_STATUSES, MenuItem, Order, Setting
from ...schemas import AvailabilityIn, StatusIn, StoreIn
from ...services import push
from ...services.orders import ORDER_LOAD, PAUSED_MESSAGE, announce, notify_ready, order_payload
from ...services.ws_manager import manager

router = APIRouter(tags=["admin"])


@router.get("/api/admin/orders")
def admin_orders(request: Request, db: Session = Depends(get_db)) -> list:
    auth.require_admin(request)
    # Today's orders plus any older one still in progress, so an order placed just before
    # midnight doesn't drop out of the queue while it's being made.
    unfinished = Order.status.notin_(CLOSED)
    orders = (db.query(Order).options(*ORDER_LOAD)
              .filter(or_(Order.created_at >= today_start(), unfinished))
              .order_by(Order.created_at.desc()).all())
    return [order_payload(o, admin=True) for o in orders]


@router.patch("/api/admin/orders/{order_id}/status")
async def set_status(order_id: int, body: StatusIn, request: Request, background: BackgroundTasks,
                     db: Session = Depends(get_db)) -> dict:
    auth.require_admin(request)
    order = db.get(Order, order_id, options=ORDER_LOAD)
    if order is None:
        raise HTTPException(404, "Order not found")
    if body.status == CANCELLED:  # the owner can reject an order until it's ready
        allowed = order.status in ORDER_STATUSES[:2]
    elif body.status == NOT_COLLECTED:  # ready, but the customer never came: closed, no cash
        allowed = order.status == "ready"
    else:  # otherwise strictly forward; cancelled/completed orders never move again
        allowed = order.status in ORDER_STATUSES and \
            ORDER_STATUSES.index(body.status) > ORDER_STATUSES.index(order.status)
    if not allowed:
        raise HTTPException(400, f"Cannot move order from {order.status} to {body.status}")
    order.status = body.status
    if order.status == "completed":
        order.completed_at = utcnow()
    db.commit()
    await announce(order)
    background.add_task(push.notify_customer, order.customer_id, order.id, order.order_number,
                        order.total, order.status)
    if order.status == "ready":
        background.add_task(notify_ready, order.order_number, order.customer.email, order.customer.name)
    return {"id": order.id, "status": order.status}


@router.patch("/api/admin/menu/{item_id}/availability")
async def set_availability(item_id: int, body: AvailabilityIn, request: Request,
                           db: Session = Depends(get_db)) -> dict:
    auth.require_admin(request)
    item = db.get(MenuItem, item_id)
    if item is None:
        raise HTTPException(404, "Menu item not found")
    item.is_available = body.is_available
    db.commit()
    await manager.broadcast_menu({"type": "availability", "item_id": item.id,
                                  "is_available": item.is_available})
    return {"id": item.id, "is_available": item.is_available}


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
