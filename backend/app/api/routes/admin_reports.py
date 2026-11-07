"""Owner: today's numbers, reports, customer reviews and the failure log."""
from collections import defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload

from ...core import auth
from ...core.clock import days_start, to_ist, today_start
from ...db.session import get_db
from ...models import CANCELLED, CLOSED, NOT_COLLECTED, Feedback, MenuItem, Order, TLog
from ...services.orders import ORDER_LOAD, accepting_orders, todays_orders

router = APIRouter(tags=["admin"])


@router.get("/api/admin/stats/today")
def stats_today(request: Request, db: Session = Depends(get_db)) -> dict:
    """The owner's numbers. Cash is only counted once an order is Done: at a cash-on-pickup
    stall, Done means handed over and paid — so it counts on the day it was marked Done (an
    order placed at 23:50 and collected at 00:10 is the new day's cash). Unfinished orders
    (any day) are "to collect"."""
    auth.require_admin(request)
    start = today_start()
    today = todays_orders(db).all()
    kept = [o for o in today if o.status != CANCELLED]
    done = (db.query(Order).filter(Order.status == "completed", or_(
        Order.completed_at >= start,
        and_(Order.completed_at.is_(None), Order.created_at >= start),  # done before completed_at existed
    )).all())
    unfinished = (db.query(Order).filter(Order.status.notin_(CLOSED)).all())
    counts: dict = defaultdict(int)
    for o in kept:
        for i in o.items:
            counts[i.menu_item.name] += i.qty
    top = max(counts, key=counts.get) if counts else None
    cash = sum(o.total for o in done)
    by_status = {st: sum(1 for o in unfinished if o.status == st) for st in ("placed", "preparing", "ready")}
    out_of_stock = db.query(func.count(MenuItem.id)).filter(
        MenuItem.archived_at.is_(None), MenuItem.is_available.is_(False)).scalar()
    return {
        "orders": len(kept),                       # placed today, not cancelled
        "cancelled": len(today) - len(kept),
        "not_collected": sum(1 for o in today if o.status == NOT_COLLECTED),
        "completed": len(done),
        "cash_collected": cash,
        "to_collect": sum(o.total for o in unfinished),
        "active": by_status,                       # unfinished orders by status (any day)
        "out_of_stock": out_of_stock,
        "accepting_orders": accepting_orders(db),
        "top_item": top,
        "revenue": cash,  # old app versions (<= 1.9) show this as "Revenue": now the cash actually collected
    }


@router.get("/api/admin/reports")
def reports(request: Request, days: int = 7, db: Session = Depends(get_db)) -> dict:
    """The owner's "Today" tab: today's summary, then the last `days` days (today included,
    stall days in IST). Cash counts on the day an order was marked Done (completed_at; orders
    done before it existed fall back to created_at) and uses the prices saved on the order.
    Item sales and busiest hours are over the same days; best sellers count paid (Done) orders."""
    auth.require_admin(request)
    days = max(1, min(days, 90))
    start, today = days_start(days), today_start()
    paid_at = lambda o: o.completed_at or o.created_at  # noqa: E731

    placed = db.query(Order).options(*ORDER_LOAD).filter(Order.created_at >= start).all()
    done = (db.query(Order).options(*ORDER_LOAD).filter(Order.status == "completed", or_(
        Order.completed_at >= start, and_(Order.completed_at.is_(None), Order.created_at >= start))).all())

    # per day, oldest first
    labels = [to_ist(start + timedelta(days=d)).date() for d in range(days)]
    cash_by_day = defaultdict(int)
    orders_by_day = defaultdict(int)
    for o in done:
        cash_by_day[to_ist(paid_at(o)).date()] += o.total
    hours = [0] * 24
    for o in placed:
        if o.status != CANCELLED:
            orders_by_day[to_ist(o.created_at).date()] += 1
            hours[to_ist(o.created_at).hour] += 1

    items: dict = {}
    for o in done:
        for i in o.items:
            row = items.setdefault(i.menu_item_id, {"menu_item_id": i.menu_item_id, "name": i.menu_item.name,
                                                    "qty": 0, "half": 0, "value": 0})
            row["qty"] += i.qty
            row["half"] += i.qty if i.size == "half" else 0
            row["value"] += i.qty * i.price_at_order
    top = sorted(items.values(), key=lambda r: (-r["qty"], -r["value"], r["name"]))[:5]

    def summary(orders_placed, orders_done) -> dict:
        cash = sum(o.total for o in orders_done)
        return {
            "orders": sum(1 for o in orders_placed if o.status != CANCELLED),
            "completed": len(orders_done),
            "cancelled": sum(1 for o in orders_placed if o.status == CANCELLED),
            "not_collected": sum(1 for o in orders_placed if o.status == NOT_COLLECTED),
            "cash": cash,
            "average": round(cash / len(orders_done)) if orders_done else 0,
        }

    today_summary = summary([o for o in placed if o.created_at >= today],
                            [o for o in done if paid_at(o) >= today])
    today_summary["in_progress"] = db.query(func.count(Order.id)).filter(Order.status.notin_(CLOSED)).scalar()
    return {
        "days": days,
        "today": today_summary,
        "period": summary(placed, done),
        "daily": [{"date": d.isoformat(), "cash": cash_by_day[d], "orders": orders_by_day[d]} for d in labels],
        "top_items": top,
        "hours": hours,  # orders placed (not cancelled) per IST hour, 0-23
    }


@router.get("/api/admin/feedback")
def admin_feedback(request: Request, db: Session = Depends(get_db)) -> dict:
    """Average stars per product, plus the latest 100 reviews (full email: owner only)."""
    auth.require_admin(request)
    averages = (db.query(MenuItem.id, MenuItem.name, func.avg(Feedback.rating), func.count(Feedback.id))
                .join(Feedback, Feedback.menu_item_id == MenuItem.id)
                .group_by(MenuItem.id, MenuItem.name).order_by(func.count(Feedback.id).desc()).all())
    recent = (db.query(Feedback).options(joinedload(Feedback.customer), joinedload(Feedback.menu_item))
              .order_by(Feedback.id.desc()).limit(100).all())
    return {
        "items": [{"menu_item_id": i, "name": n, "average": round(float(a), 1), "count": c}
                  for i, n, a, c in averages],
        "recent": [{
            "id": f.id, "order_id": f.order_id, "item": f.menu_item.name, "rating": f.rating,
            "comment": f.comment, "name": f.customer.name, "email": f.customer.email,
            "allow_public": f.allow_public, "created_at": f.created_at.isoformat(),
        } for f in recent],
    }


@router.get("/api/admin/logs")
def get_admin_logs(limit: int = 50, request: Request = None, db: Session = Depends(get_db)) -> list:
    auth.require_admin(request)
    logs = db.query(TLog).order_by(TLog.created_at.desc()).limit(min(limit, 200)).all()
    return [
        {
            "id": l.id,
            "created_at": l.created_at.isoformat(),
            "method": l.method,
            "path": l.path,
            "status": l.status,
            "duration_ms": l.duration_ms,
            "error": l.error,
            "client_ip": l.client_ip,
            "origin": l.origin,
            "user_email": l.user_email,
        }
        for l in logs
    ]
