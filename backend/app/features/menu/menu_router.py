"""The public menu, grouped by category."""
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.shared.database import get_db
from app.shared.models import MenuItem

router = APIRouter(tags=["menu"])


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
