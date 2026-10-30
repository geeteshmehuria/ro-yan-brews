import os
import time
import traceback
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import auth, mailer, otp_service, request_log
from .clock import today_start
from .db import Base, add_missing_columns, engine, get_db, SessionLocal
from .models import CANCELLED, Customer, Feedback, MenuItem, Order, OrderItem, ORDER_STATUSES, TLog
from .schemas import (AvailabilityIn, EmailIn, FeedbackIn, GoogleAuthIn, OrderIn, OtpVerifyIn,
                      ProfileIn, StatusIn)
from .seed import seed_menu
from .ws import manager


@asynccontextmanager
async def lifespan(_: FastAPI):
    auth.check_prod_config()
    Base.metadata.create_all(bind=engine)
    add_missing_columns(engine)
    request_log.prune()
    # The seed menu is placeholder data: never auto-load it into production.
    if os.getenv("SEED_MENU", "false" if auth.IS_PROD else "true") == "true":
        with SessionLocal() as db:
            seed_menu(db)
    yield


app = FastAPI(title="Ro-Yan Brews API", lifespan=lifespan)

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)

# ---------------- failure log (t_log table) ----------------

@app.exception_handler(StarletteHTTPException)
async def _http_error(request: Request, exc: StarletteHTTPException):
    request.state.error = request_log.describe(exc)
    return await http_exception_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def _validation_error(request: Request, exc: RequestValidationError):
    # field names + messages only: the submitted values (emails, notes) stay out of the log
    request.state.error = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
    return await request_validation_exception_handler(request, exc)


@app.middleware("http")
async def log_failures(request: Request, call_next):
    """Record every failed request (status >= 400, including rejected CORS preflights)
    and every unhandled exception in t_log. Successful requests are not logged."""
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        request.state.error = "".join(traceback.format_exception(exc))[-2000:]  # the end has the actual error
        origin = request.headers.get("origin")
        headers = {}
        if origin and (origin in CORS_ORIGINS or "*" in CORS_ORIGINS):
            headers["Access-Control-Allow-Origin"] = origin
        response = JSONResponse({"detail": "Internal Server Error"}, status_code=500, headers=headers)
    if response.status_code >= 400:
        try:
            email = auth.current_customer(request).get("email")
        except HTTPException:
            email = None
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        await run_in_threadpool(
            request_log.record, request.method, request.url.path,
            status=response.status_code, duration_ms=int((time.perf_counter() - started) * 1000),
            error=getattr(request.state, "error", None),
            client_ip=forwarded or (request.client.host if request.client else None),
            origin=request.headers.get("origin"), user_agent=request.headers.get("user-agent"),
            user_email=email)
    return response


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


MAX_ACTIVE_ORDERS = 3  # per customer: cash on pickup makes prank orders free, so cap the damage


# ---------------- public ----------------

@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/menu")
def get_menu(db: Session = Depends(get_db)) -> list:
    items = db.query(MenuItem).order_by(MenuItem.sort_order).all()
    grouped: dict = defaultdict(list)
    cats: list = []
    for i in items:
        if i.category not in cats:
            cats.append(i.category)
        grouped[i.category].append({
            "id": i.id, "name": i.name, "price_half": i.price_half,
            "price_full": i.price_full, "is_available": i.is_available,
        })
    return [{"category": c, "items": grouped[c]} for c in cats]


@app.get("/api/auth/mode")
def auth_mode() -> dict:
    """Auth settings and client IDs."""
    return {
        "dev_mode": otp_service.OTP_DEV_MODE,
        "google_client_id": auth.GOOGLE_CLIENT_ID,
    }


@app.post("/api/otp/send")
def otp_send(body: EmailIn, db: Session = Depends(get_db)) -> dict:
    otp_service.send_otp(db, body.email)
    return {"sent": True}


@app.post("/api/otp/verify")
def otp_verify(body: OtpVerifyIn, db: Session = Depends(get_db)) -> dict:
    otp_service.verify_otp(db, body.email, body.code)
    customer = db.query(Customer).filter_by(email=body.email).first()
    if customer is None:
        customer = Customer(email=body.email)
        db.add(customer)
        try:
            db.commit()
        except IntegrityError:  # a parallel first login created it
            db.rollback()
            customer = db.query(Customer).filter_by(email=body.email).one()
        db.refresh(customer)
    token = auth.create_session_token(customer.id, body.email)
    return {"verified": True, "token": token, "is_admin": auth.is_admin_email(body.email)}


@app.post("/api/auth/google")
def google_login(body: GoogleAuthIn, db: Session = Depends(get_db)) -> dict:
    info = auth.verify_google_token(body.credential)
    email = info["email"]
    name = info.get("name")
    customer = db.query(Customer).filter_by(email=email).first()
    if customer is None:
        customer = Customer(email=email, name=name)
        db.add(customer)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            customer = db.query(Customer).filter_by(email=email).one()
        db.refresh(customer)
    elif name and not customer.name:
        customer.name = name
        db.commit()
    token = auth.create_session_token(customer.id, email)
    return {"verified": True, "token": token, "is_admin": auth.is_admin_email(email)}


# ---------------- profile ----------------

def _me(request: Request, db: Session) -> Customer:
    customer = db.get(Customer, auth.current_customer(request)["cid"])
    if customer is None:
        raise HTTPException(401, "Please log in again")
    return customer


@app.get("/api/me")
def get_me(request: Request, db: Session = Depends(get_db)) -> dict:
    me = _me(request, db)
    return {"email": me.email, "name": me.name}


@app.patch("/api/me")
def update_me(body: ProfileIn, request: Request, db: Session = Depends(get_db)) -> dict:
    me = _me(request, db)
    me.name = body.name
    db.commit()
    return {"email": me.email, "name": me.name}


# Deliberately `async def` with no `await` between the count and the commit: the
# whole numbering step runs uninterrupted on the event loop, so two orders can never
# get the same number. That only holds for a single worker (render.yaml pins one —
# the in-process WebSocket manager needs that anyway). Don't change to `def`.
@app.post("/api/orders", status_code=201)
async def create_order(body: OrderIn, request: Request, db: Session = Depends(get_db)) -> dict:
    session = auth.current_customer(request)
    active = db.query(func.count(Order.id)).filter(
        Order.customer_id == session["cid"], Order.status.notin_(["completed", CANCELLED])).scalar()
    if active >= MAX_ACTIVE_ORDERS:
        raise HTTPException(429, f"You already have {active} orders in progress — "
                                 "please collect them before ordering more")
    total = 0
    lines = []
    for line in body.items:
        item = db.get(MenuItem, line.menu_item_id)
        if item is None:
            raise HTTPException(400, "That item is not on the menu")
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

    order = Order(order_number=todays + 1, customer_id=session["cid"], total=total, note=body.note)
    db.add(order)
    db.flush()
    for item, line, price in lines:
        db.add(OrderItem(order_id=order.id, menu_item_id=item.id,
                         size=line.size, qty=line.qty, price_at_order=price))
    db.commit()
    db.refresh(order)

    await manager.broadcast_admin({"type": "new_order", "order": order_payload(order, admin=True)})
    return order_payload(order)


@app.get("/api/orders/mine")  # must stay above /api/orders/{order_id}
def my_orders(request: Request, db: Session = Depends(get_db)) -> list:
    session = auth.current_customer(request)
    orders = (db.query(Order).options(*ORDER_LOAD).filter(Order.customer_id == session["cid"])
              .order_by(Order.id.desc()).limit(20).all())
    return [order_payload(o) for o in orders]


@app.post("/api/orders/{order_id}/cancel")
async def cancel_order(order_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    session = auth.current_customer(request)
    order = db.get(Order, order_id)
    if order is None or order.customer_id != session["cid"]:
        raise HTTPException(404, "Order not found")
    if order.status != "placed":
        raise HTTPException(400, "Your order is already being prepared — please ask at the counter")
    order.status = CANCELLED
    db.commit()
    await announce(order)
    return {"id": order.id, "status": order.status}


@app.post("/api/orders/{order_id}/feedback", status_code=201)
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


@app.get("/api/orders/{order_id}")
def get_order(order_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    session = auth.current_customer(request)
    order = db.get(Order, order_id, options=ORDER_LOAD)
    if order is None or order.customer_id != session["cid"]:
        raise HTTPException(404, "Order not found")
    return order_payload(order)


# ---------------- admin ----------------

@app.get("/api/admin/orders")
def admin_orders(request: Request, db: Session = Depends(get_db)) -> list:
    auth.require_admin(request)
    # Today's orders plus any older one still in progress, so an order placed just before
    # midnight doesn't drop out of the queue while it's being made.
    unfinished = Order.status.notin_(["completed", CANCELLED])
    orders = (db.query(Order).options(*ORDER_LOAD)
              .filter(or_(Order.created_at >= today_start(), unfinished))
              .order_by(Order.created_at.desc()).all())
    return [order_payload(o, admin=True) for o in orders]


@app.patch("/api/admin/orders/{order_id}/status")
async def set_status(order_id: int, body: StatusIn, request: Request, background: BackgroundTasks,
                     db: Session = Depends(get_db)) -> dict:
    auth.require_admin(request)
    order = db.get(Order, order_id, options=ORDER_LOAD)
    if order is None:
        raise HTTPException(404, "Order not found")
    if body.status == CANCELLED:  # the owner can reject an order until it's ready
        allowed = order.status in ORDER_STATUSES[:2]
    else:  # otherwise strictly forward; cancelled/completed orders never move again
        allowed = order.status in ORDER_STATUSES and \
            ORDER_STATUSES.index(body.status) > ORDER_STATUSES.index(order.status)
    if not allowed:
        raise HTTPException(400, f"Cannot move order from {order.status} to {body.status}")
    order.status = body.status
    db.commit()
    await announce(order)
    if order.status == "ready":
        background.add_task(notify_ready, order.order_number, order.customer.email, order.customer.name)
    return {"id": order.id, "status": order.status}


@app.patch("/api/admin/menu/{item_id}/availability")
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


@app.get("/api/admin/stats/today")
def stats_today(request: Request, db: Session = Depends(get_db)) -> dict:
    auth.require_admin(request)
    orders = todays_orders(db).filter(Order.status != CANCELLED).all()
    counts: dict = defaultdict(int)
    for o in orders:
        for i in o.items:
            counts[i.menu_item.name] += i.qty
    top = max(counts, key=counts.get) if counts else None
    return {"orders": len(orders), "revenue": sum(o.total for o in orders), "top_item": top}


@app.get("/api/admin/feedback")
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


@app.get("/api/admin/logs")
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


# ---------------- websockets ----------------

@app.websocket("/ws/admin")
async def ws_admin(ws: WebSocket) -> None:
    if not auth.token_is_admin(ws.query_params.get("token", "")):
        await ws.close(code=4401)
        return
    await manager.connect(ws, manager.admin)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws, manager.admin)


@app.websocket("/ws/me")
async def ws_me(ws: WebSocket) -> None:
    """The logged-in customer's channel: status changes for all of their orders."""
    cid = auth.token_customer_id(ws.query_params.get("token", ""))
    if cid is None:
        await ws.close(code=4401)
        return
    await manager.join_customer(ws, cid)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.leave_customer(ws, cid)


@app.websocket("/ws/menu")
async def ws_menu(ws: WebSocket) -> None:
    await manager.connect(ws, manager.menu)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws, manager.menu)
