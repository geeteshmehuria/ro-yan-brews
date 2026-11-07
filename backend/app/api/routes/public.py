"""Public endpoints: health check, Open / Paused status, and the menu."""
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...models import MenuItem
from ...services.orders import PAUSED_MESSAGE, accepting_orders

router = APIRouter(tags=["public"])


@router.get("/api/health")
def health() -> dict:
    return {"ok": True}


@router.get("/api/store")
def store_status(db: Session = Depends(get_db)) -> dict:
    """Is the stall taking orders? Changes are pushed as {type: "store"} on /ws/menu."""
    open_ = accepting_orders(db)
    return {"accepting_orders": open_, "message": None if open_ else PAUSED_MESSAGE}


@router.get("/api/menu")
def get_menu(db: Session = Depends(get_db)) -> list:
    items = db.query(MenuItem).filter(MenuItem.archived_at.is_(None)).order_by(MenuItem.sort_order).all()
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
