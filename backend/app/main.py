import os
from collections import defaultdict
from datetime import datetime, time as dtime

from fastapi import Depends, FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import auth, otp_service
from .db import Base, engine, get_db, SessionLocal
from .models import Customer, MenuItem, Order, OrderItem, ORDER_STATUSES
from .schemas import AvailabilityIn, OrderIn, OtpVerifyIn, PhoneIn, StatusIn
from .seed import seed_menu
from .ws import manager

app = FastAPI(title="Ro-Yan Brews API")

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_menu(db)
    finally:
        db.close()


def mask(phone: str) -> str:
    return phone[:2] + "xxxx" + phone[-4:]


def order_payload(o: Order) -> dict:
    return {
        "id": o.id,
        "order_number": o.order_number,
        "status": o.status,
        "total": o.total,
        "phone_masked": mask(o.customer.phone_number),
        "created_at": o.created_at.isoformat(),
        "items": [
            {
                "name": i.menu_item.name,
                "size": i.size,
                "qty": i.qty,
                "price": i.price_at_order,
            }
            for i in o.items
        ],
    }


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


@app.post("/api/otp/send")
def otp_send(body: PhoneIn, db: Session = Depends(get_db)) -> dict:
    otp_service.send_otp(db, body.phone)
    return {"sent": True}


@app.post("/api/otp/verify")
def otp_verify(body: OtpVerifyIn, response: Response, db: Session = Depends(get_db)) -> dict:
    otp_service.verify_otp(db, body.phone, body.code)
    customer = db.query(Customer).filter_by(phone_number=body.phone).first()
    if customer is None:
        customer = Customer(phone_number=body.phone)
        db.add(customer)
        db.commit()
        db.refresh(customer)
    token = auth.create_session_token(customer.id, body.phone)
    response.set_cookie(
        "session", token, max_age=60 * 60 * 24 * 30, httponly=True,
        samesite="none" if auth.IS_PROD else "lax", secure=auth.IS_PROD,
    )
    return {"verified": True, "token": token}


@app.post("/api/orders", status_code=201)
async def create_order(body: OrderIn, request: Request, db: Session = Depends(get_db)) -> dict:
    session = auth.current_customer(request)
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

    today_start = datetime.combine(datetime.utcnow().date(), dtime.min)
    todays = db.query(func.count(Order.id)).filter(Order.created_at >= today_start).scalar() or 0

    order = Order(order_number=todays + 1, customer_id=session["cid"], total=total)
    db.add(order)
    db.flush()
    for item, line, price in lines:
        db.add(OrderItem(order_id=order.id, menu_item_id=item.id,
                         size=line.size, qty=line.qty, price_at_order=price))
    db.commit()
    db.refresh(order)

    payload = order_payload(order)
    await manager.broadcast_admin({"type": "new_order", "order": payload})
    return payload


@app.get("/api/orders/{order_id}")
def get_order(order_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    session = auth.current_customer(request)
    order = db.get(Order, order_id)
    if order is None or order.customer_id != session["cid"]:
        raise HTTPException(404, "Order not found")
    return order_payload(order)


# ---------------- admin ----------------

@app.get("/api/admin/orders")
def admin_orders(request: Request, db: Session = Depends(get_db)) -> list:
    auth.require_admin(request)
    today_start = datetime.combine(datetime.utcnow().date(), dtime.min)
    orders = (db.query(Order).filter(Order.created_at >= today_start)
              .order_by(Order.created_at.desc()).all())
    return [order_payload(o) for o in orders]


@app.patch("/api/admin/orders/{order_id}/status")
async def set_status(order_id: int, body: StatusIn, request: Request,
                     db: Session = Depends(get_db)) -> dict:
    auth.require_admin(request)
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(404, "Order not found")
    if ORDER_STATUSES.index(body.status) <= ORDER_STATUSES.index(order.status):
        raise HTTPException(400, f"Cannot move order from {order.status} to {body.status}")
    order.status = body.status
    db.commit()
    await manager.send_order(order.id, {"type": "status", "status": order.status})
    await manager.broadcast_admin({"type": "status", "order_id": order.id, "status": order.status})
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
    today_start = datetime.combine(datetime.utcnow().date(), dtime.min)
    orders = db.query(Order).filter(Order.created_at >= today_start).all()
    revenue = sum(o.total for o in orders)
    counts: dict = defaultdict(int)
    for o in orders:
        for i in o.items:
            counts[i.menu_item.name] += i.qty
    top = max(counts, key=counts.get) if counts else None
    return {"orders": len(orders), "revenue": revenue, "top_item": top}


# ---------------- websockets ----------------

@app.websocket("/ws/admin")
async def ws_admin(ws: WebSocket) -> None:
    if ws.query_params.get("pin") != auth.ADMIN_PIN:
        await ws.close(code=4401)
        return
    await manager.connect(ws, manager.admin)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws, manager.admin)


@app.websocket("/ws/orders/{order_id}")
async def ws_order(ws: WebSocket, order_id: int) -> None:
    pool = manager.orders.setdefault(order_id, set())
    await manager.connect(ws, pool)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws, pool)


@app.websocket("/ws/menu")
async def ws_menu(ws: WebSocket) -> None:
    await manager.connect(ws, manager.menu)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws, manager.menu)
