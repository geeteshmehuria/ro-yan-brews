"""Product reviews: a customer rates a collected order once; the owner reads them all."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.features.feedback.feedback_schemas import FeedbackIn
from app.features.orders.orders_service import ORDER_LOAD
from app.shared import auth
from app.shared.database import get_db
from app.shared.models import Feedback, MenuItem, Order

router = APIRouter(tags=["feedback"])


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
