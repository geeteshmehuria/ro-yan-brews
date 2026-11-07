"""Customer orders: place, list, cancel."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.features.notifications import push_service
from app.features.orders.orders_schemas import OrderIn
from app.features.orders.orders_service import ORDER_LOAD, announce, order_payload
from app.features.store.store_service import PAUSED_MESSAGE, accepting_orders
from app.shared import auth
from app.shared.clock import today_start
from app.shared.database import get_db
from app.shared.models import CANCELLED, CLOSED, MenuItem, Order, OrderItem
from app.shared.ws_manager import manager

router = APIRouter(tags=["orders"])


MAX_ACTIVE_ORDERS = 3  # per customer: cash on pickup makes prank orders free, so cap the damage


# Deliberately `async def` with no `await` between the count and the commit: the
# whole numbering step runs uninterrupted on the event loop, so two orders can never
# get the same number. That only holds for a single worker (render.yaml pins one —
# the in-process WebSocket manager needs that anyway). Don't change to `def`.
@router.post("/api/orders", status_code=201)
async def create_order(body: OrderIn, request: Request, background: BackgroundTasks,
                       db: Session = Depends(get_db)) -> dict:
    session = auth.current_customer(request)
    if body.client_key:  # a retry of a checkout that already went through: same order, no new one
        placed = (db.query(Order).options(*ORDER_LOAD)
                  .filter(Order.customer_id == session["cid"], Order.client_key == body.client_key)
                  .first())
        if placed is not None:
            return order_payload(placed)
    if not accepting_orders(db):  # checked here, not just hidden in the UI: old tabs and apps too
        raise HTTPException(409, PAUSED_MESSAGE)
    active = db.query(func.count(Order.id)).filter(
        Order.customer_id == session["cid"], Order.status.notin_(CLOSED)).scalar()
    if active >= MAX_ACTIVE_ORDERS:
        raise HTTPException(429, f"You already have {active} orders in progress — "
                                 "please collect them before ordering more")
    total = 0
    lines = []
    for line in body.items:
        item = db.get(MenuItem, line.menu_item_id)
        if item is None:
            raise HTTPException(400, "That item is not on the menu")
        if item.archived_at is not None:
            raise HTTPException(400, f"Sorry, {item.name} is not on the menu any more")
        if not item.is_available:
            raise HTTPException(400, f"Sorry, {item.name} is out of stock right now")
        if line.size == "half":
            if item.price_half is None:
                raise HTTPException(400, f"{item.name} has no half size")
            price = item.price_half
        else:
            price = item.price_full
        total += price * line.qty
        lines.append((item, line, price))

    todays = db.query(func.count(Order.id)).filter(Order.created_at >= today_start()).scalar() or 0

    order = Order(order_number=todays + 1, customer_id=session["cid"], total=total, note=body.note,
                  client_key=body.client_key)
    db.add(order)
    db.flush()
    for item, line, price in lines:
        db.add(OrderItem(order_id=order.id, menu_item_id=item.id,
                         size=line.size, qty=line.qty, price_at_order=price))
    db.commit()
    db.refresh(order)

    payload = order_payload(order, admin=True)
    await manager.broadcast_admin({"type": "new_order", "order": payload})
    summary = ", ".join(f"{i['name']} ×{i['qty']}" for i in payload["items"])
    background.add_task(push_service.notify_admins, f"New order #{order.order_number} · ₹{order.total}",
                        f"{payload['name'] or payload['email']}: {summary}", order.id)
    return order_payload(order)


@router.get("/api/orders/mine")  # must stay above /api/orders/{order_id}
def my_orders(request: Request, db: Session = Depends(get_db)) -> list:
    session = auth.current_customer(request)
    orders = (db.query(Order).options(*ORDER_LOAD).filter(Order.customer_id == session["cid"])
              .order_by(Order.id.desc()).limit(20).all())
    return [order_payload(o) for o in orders]


@router.post("/api/orders/{order_id}/cancel")
async def cancel_order(order_id: int, request: Request, background: BackgroundTasks,
                       db: Session = Depends(get_db)) -> dict:
    session = auth.current_customer(request)
    order = db.get(Order, order_id)
    if order is None or order.customer_id != session["cid"]:
        raise HTTPException(404, "Order not found")
    if order.status != "placed":
        raise HTTPException(400, "Your order is already being prepared — please ask at the counter")
    order.status = CANCELLED
    db.commit()
    await announce(order)
    background.add_task(push_service.notify_admins, f"Order #{order.order_number} cancelled",
                        "The customer cancelled it — don't make it.", order.id, "cancelled")
    return {"id": order.id, "status": order.status}
