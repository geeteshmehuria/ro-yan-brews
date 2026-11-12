"""Owner: the order queue and status changes."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.features.notifications import push_service
from app.features.orders.orders_schemas import StatusIn
from app.features.orders.orders_service import ORDER_LOAD, announce, notify_ready, order_payload
from app.shared import auth
from app.shared.clock import today_start, utcnow
from app.shared.database import get_db
from app.shared.models import CANCELLED, CLOSED, NOT_COLLECTED, ORDER_STATUSES, Order

router = APIRouter(tags=["orders (owner)"])


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
    background.add_task(push_service.notify_customer, order.customer_id, order.id, order.order_number,
                        order.total, order.status)
    if order.status == "ready":
        background.add_task(notify_ready, order.order_number, order.customer.email, order.customer.name,
                            order_payload(order)["items"], order.total)
    return {"id": order.id, "status": order.status}
