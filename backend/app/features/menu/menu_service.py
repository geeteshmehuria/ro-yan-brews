"""Menu helpers shared by the owner's menu routes."""
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.shared.models import MenuItem, OrderItem
from app.shared.ws_manager import manager


def menu_item_out(item: MenuItem, ordered: bool) -> dict:
    return {"id": item.id, "name": item.name, "category": item.category,
            "price_half": item.price_half, "price_full": item.price_full,
            "is_available": item.is_available, "archived": item.archived_at is not None,
            "ordered": ordered}  # ever ordered -> can be removed (hidden) but not deleted


def ordered_item_ids(db: Session) -> set:
    return {i for (i,) in db.query(OrderItem.menu_item_id).distinct()}


def check_name_free(db: Session, name: str, exclude_id: Optional[int] = None) -> None:
    """Two items on the menu can't share a name (any letter case); removed items don't count."""
    q = db.query(MenuItem).filter(func.lower(MenuItem.name) == name.lower(), MenuItem.archived_at.is_(None))
    if exclude_id is not None:
        q = q.filter(MenuItem.id != exclude_id)
    if q.first() is not None:
        raise HTTPException(409, f"“{name}” is already on the menu")


def get_item_or_404(db: Session, item_id: int) -> MenuItem:
    item = db.get(MenuItem, item_id)
    if item is None:
        raise HTTPException(404, "Menu item not found")
    return item


async def broadcast_menu_changed() -> None:
    await manager.broadcast_menu({"type": "menu_changed"})
