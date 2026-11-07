"""Order helpers shared by the customer and owner routes: loading, the JSON shape sent to
clients, live announcements, the "ready" email, and the Open / Paused switch."""
from typing import Optional

from sqlalchemy.orm import Session, joinedload, selectinload

from ..core.clock import today_start
from ..models import Order, OrderItem, Setting
from . import mailer, request_log
from .ws_manager import manager

# Eager-load everything order_payload touches (avoids one query per order/item).
ORDER_LOAD = (joinedload(Order.customer), selectinload(Order.items).joinedload(OrderItem.menu_item),
              selectinload(Order.feedback))


def mask(email: str) -> str:
    """user@example.com -> us***@example.com"""
    local, _, domain = email.partition("@")
    return f"{local[:2]}***@{domain}"


def order_payload(o: Order, admin: bool = False) -> dict:
    """Customers see a masked email; the owner sees the full one (and the name, if set)."""
    return {
        "id": o.id,
        "order_number": o.order_number,
        "status": o.status,
        "total": o.total,
        "note": o.note,
        "client_key": o.client_key,  # lets the app tell that a checkout whose reply was lost went through
        "name": o.customer.name,
        "email": o.customer.email if admin else mask(o.customer.email),
        "created_at": o.created_at.isoformat(),
        "reviewed": bool(o.feedback),  # feedback is sent once per order
        "items": [
            {
                "menu_item_id": i.menu_item_id,
                "name": i.menu_item.name,
                "size": i.size,
                "qty": i.qty,
                "price": i.price_at_order,
            }
            for i in o.items
        ],
    }


def todays_orders(db: Session):
    return db.query(Order).options(*ORDER_LOAD).filter(Order.created_at >= today_start())


async def announce(order: Order) -> None:
    """Push a status change to the order's customer (all their devices) and to the owner."""
    msg = {"type": "status", "order_id": order.id, "status": order.status}
    await manager.send_customer(order.customer_id, msg)
    await manager.broadcast_admin(msg)


def notify_ready(order_number: int, email: str, name: Optional[str]) -> None:
    """Background task: email the customer that their order is ready. Never raises."""
    if not mailer.configured():
        return
    try:
        mailer.send_mail(
            email,
            f"Your Ro-Yan order #{order_number} is ready",
            f"Hi {name or 'there'},\n\nOrder #{order_number} is ready — please collect it at "
            "the counter and pay cash.\n\n— Ro-Yan Brews",
        )
    except Exception as exc:  # a failed courtesy email must never matter — just leave a trace
        request_log.record("TASK", "notify_ready", error=request_log.describe(exc))


PAUSED_MESSAGE = "We're not taking orders right now — please check back soon."


def accepting_orders(db: Session) -> bool:
    """The owner's Open / Paused switch (open unless they paused it)."""
    row = db.get(Setting, "accepting_orders")
    return row is None or row.value == "1"
