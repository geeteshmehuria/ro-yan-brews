"""Owner: add, edit, remove, restore and delete menu items.

Every change is broadcast as {type: "menu_changed"} on /ws/menu; clients refetch the menu
(the customer's cart then re-prices itself and drops items that are gone)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...core import auth
from ...core.clock import utcnow
from ...db.session import get_db
from ...models import MenuItem, OrderItem
from ...schemas import MenuItemIn
from ...services.ws_manager import manager

router = APIRouter(tags=["admin"])


def _menu_item_out(item: MenuItem, ordered: bool) -> dict:
    return {"id": item.id, "name": item.name, "category": item.category,
            "price_half": item.price_half, "price_full": item.price_full,
            "is_available": item.is_available, "archived": item.archived_at is not None,
            "ordered": ordered}  # ever ordered -> can be removed (hidden) but not deleted


def _ordered_ids(db: Session) -> set:
    return {i for (i,) in db.query(OrderItem.menu_item_id).distinct()}


def _check_name_free(db: Session, name: str, exclude_id: Optional[int] = None) -> None:
    """Two items on the menu can't share a name (any letter case); removed items don't count."""
    q = db.query(MenuItem).filter(func.lower(MenuItem.name) == name.lower(), MenuItem.archived_at.is_(None))
    if exclude_id is not None:
        q = q.filter(MenuItem.id != exclude_id)
    if q.first() is not None:
        raise HTTPException(409, f"“{name}” is already on the menu")


def _admin_item(db: Session, item_id: int) -> MenuItem:
    item = db.get(MenuItem, item_id)
    if item is None:
        raise HTTPException(404, "Menu item not found")
    return item


async def _menu_changed() -> None:
    await manager.broadcast_menu({"type": "menu_changed"})


@router.get("/api/admin/menu")
def admin_menu(request: Request, db: Session = Depends(get_db)) -> list:
    """Every item, removed ones included, in menu order (the public menu hides removed ones)."""
    auth.require_admin(request)
    ordered = _ordered_ids(db)
    items = db.query(MenuItem).order_by(MenuItem.sort_order, MenuItem.id).all()
    return [_menu_item_out(i, i.id in ordered) for i in items]


@router.post("/api/admin/menu", status_code=201)
async def add_menu_item(body: MenuItemIn, request: Request, db: Session = Depends(get_db)) -> dict:
    auth.require_admin(request)
    _check_name_free(db, body.name)
    last = db.query(func.max(MenuItem.sort_order)).scalar()
    item = MenuItem(name=body.name, category=body.category, price_full=body.price_full,
                    price_half=body.price_half, is_available=body.is_available,
                    sort_order=(last or 0) + 1)  # end of its category; a new category goes last
    db.add(item)
    db.commit()
    await _menu_changed()
    return _menu_item_out(item, False)


@router.patch("/api/admin/menu/{item_id}")
async def edit_menu_item(item_id: int, body: MenuItemIn, request: Request,
                         db: Session = Depends(get_db)) -> dict:
    """Past orders keep their price (price_at_order); a new name shows on old orders too."""
    auth.require_admin(request)
    item = _admin_item(db, item_id)
    if item.archived_at is None:
        _check_name_free(db, body.name, exclude_id=item.id)
    item.name, item.category = body.name, body.category
    item.price_full, item.price_half, item.is_available = body.price_full, body.price_half, body.is_available
    db.commit()
    await _menu_changed()
    return _menu_item_out(item, item.id in _ordered_ids(db))


@router.post("/api/admin/menu/{item_id}/remove")
async def remove_menu_item(item_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    auth.require_admin(request)
    item = _admin_item(db, item_id)
    if item.archived_at is None:
        item.archived_at = utcnow()
        db.commit()
        await _menu_changed()
    return _menu_item_out(item, item.id in _ordered_ids(db))


@router.post("/api/admin/menu/{item_id}/restore")
async def restore_menu_item(item_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    auth.require_admin(request)
    item = _admin_item(db, item_id)
    if item.archived_at is not None:
        _check_name_free(db, item.name, exclude_id=item.id)  # a new item may have taken the name
        item.archived_at = None
        db.commit()
        await _menu_changed()
    return _menu_item_out(item, item.id in _ordered_ids(db))


@router.delete("/api/admin/menu/{item_id}")
async def delete_menu_item(item_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    """Only for items never ordered (typos); anything ordered must stay for past orders."""
    auth.require_admin(request)
    item = _admin_item(db, item_id)
    if item.id in _ordered_ids(db):
        raise HTTPException(409, f"{item.name} has been ordered before — remove it instead, "
                                 "so past orders keep it")
    db.delete(item)
    db.commit()
    await _menu_changed()
    return {"id": item_id, "deleted": True}
