"""Customer orders: place, list, cancel, rate."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...core import auth
from ...core.clock import today_start
from ...db.session import get_db
from ...models import CANCELLED, CLOSED, Feedback, MenuItem, Order, OrderItem
from ...schemas import FeedbackIn, OrderIn
from ...services import push
from ...services.orders import ORDER_LOAD, PAUSED_MESSAGE, accepting_orders, announce, order_payload
from ...services.ws_manager import manager

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
    background.add_task(push.notify_admins, f"New order #{order.order_number} · ₹{order.total}",
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
    background.add_task(push.notify_admins, f"Order #{order.order_number} cancelled",
                        "The customer cancelled it — don't make it.", order.id, "cancelled")
    return {"id": order.id, "status": order.status}


@router.post("/api/orders/{order_id}/feedback", status_code=201)
def give_feedback(order_id: int, body: FeedbackIn, request: Request, db: Session = Depends(get_db)) -> dict:
    """Rate the products of one of your own collected orders — once per order. Only real,
    completed orders count, so every review comes from someone who actually got the food."""
    session = auth.current_customer(request)
    order = db.get(Order, order_id, options=ORDER_LOAD)
    if order is None or order.customer_id != session["cid"]:
        raise HTTPException(404, "Order not found")
    if order.status != "completed":
        raise HTTPException(400, "You can rate an order once you've collected it")
    if order.feedback:
        raise HTTPException(409, "You've already rated this order — thank you!")
    in_order = {i.menu_item_id for i in order.items}
    if any(r.menu_item_id not in in_order for r in body.ratings):
        raise HTTPException(400, "You can only rate items from this order")
    for r in body.ratings:
        db.add(Feedback(customer_id=order.customer_id, order_id=order.id, menu_item_id=r.menu_item_id,
                        rating=r.rating, comment=r.comment, allow_public=body.allow_public))
    try:
        db.commit()
    except IntegrityError:  # a double tap sent it twice
        db.rollback()
        raise HTTPException(409, "You've already rated this order — thank you!")
    return {"order_id": order.id, "reviewed": True}


@router.get("/api/orders/{order_id}")
def get_order(order_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    session = auth.current_customer(request)
    order = db.get(Order, order_id, options=ORDER_LOAD)
    if order is None or order.customer_id != session["cid"]:
        raise HTTPException(404, "Order not found")
    return order_payload(order)
