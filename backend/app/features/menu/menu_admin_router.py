"""Owner: add, edit, remove, restore and delete menu items, and switch stock on/off.

Every change is broadcast on /ws/menu; clients refetch the menu (the customer's cart then
re-prices itself and drops items that are gone)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.features.menu.menu_schemas import AvailabilityIn, MenuItemIn
from app.features.menu.menu_service import (
    broadcast_menu_changed,
    check_name_free,
    get_item_or_404,
    menu_item_out,
    ordered_item_ids,
)
from app.shared import auth
from app.shared.clock import utcnow
from app.shared.database import get_db
from app.shared.models import MenuItem
from app.shared.ws_manager import manager

router = APIRouter(tags=["menu (owner)"])


@router.patch("/api/admin/menu/{item_id}/availability")
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


@router.get("/api/admin/menu")
def admin_menu(request: Request, db: Session = Depends(get_db)) -> list:
    """Every item, removed ones included, in menu order (the public menu hides removed ones)."""
    auth.require_admin(request)
    ordered = ordered_item_ids(db)
    items = db.query(MenuItem).order_by(MenuItem.sort_order, MenuItem.id).all()
    return [menu_item_out(i, i.id in ordered) for i in items]


@router.post("/api/admin/menu", status_code=201)
async def add_menu_item(body: MenuItemIn, request: Request, db: Session = Depends(get_db)) -> dict:
    auth.require_admin(request)
    check_name_free(db, body.name)
    last = db.query(func.max(MenuItem.sort_order)).scalar()
    item = MenuItem(name=body.name, category=body.category, price_full=body.price_full,
                    price_half=body.price_half, is_available=body.is_available,
                    sort_order=(last or 0) + 1)  # end of its category; a new category goes last
    db.add(item)
    db.commit()
    await broadcast_menu_changed()
    return menu_item_out(item, False)


@router.patch("/api/admin/menu/{item_id}")
async def edit_menu_item(item_id: int, body: MenuItemIn, request: Request,
                         db: Session = Depends(get_db)) -> dict:
    """Past orders keep their price (price_at_order); a new name shows on old orders too."""
    auth.require_admin(request)
    item = get_item_or_404(db, item_id)
    if item.archived_at is None:
        check_name_free(db, body.name, exclude_id=item.id)
    item.name, item.category = body.name, body.category
    item.price_full, item.price_half, item.is_available = body.price_full, body.price_half, body.is_available
    db.commit()
    await broadcast_menu_changed()
    return menu_item_out(item, item.id in ordered_item_ids(db))


@router.post("/api/admin/menu/{item_id}/remove")
async def remove_menu_item(item_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    auth.require_admin(request)
    item = get_item_or_404(db, item_id)
    if item.archived_at is None:
        item.archived_at = utcnow()
        db.commit()
        await broadcast_menu_changed()
    return menu_item_out(item, item.id in ordered_item_ids(db))


@router.post("/api/admin/menu/{item_id}/restore")
async def restore_menu_item(item_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    auth.require_admin(request)
    item = get_item_or_404(db, item_id)
    if item.archived_at is not None:
        check_name_free(db, item.name, exclude_id=item.id)  # a new item may have taken the name
        item.archived_at = None
        db.commit()
        await broadcast_menu_changed()
    return menu_item_out(item, item.id in ordered_item_ids(db))


@router.delete("/api/admin/menu/{item_id}")
async def delete_menu_item(item_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    """Only for items never ordered (typos); anything ordered must stay for past orders."""
    auth.require_admin(request)
    item = get_item_or_404(db, item_id)
    if item.id in ordered_item_ids(db):
        raise HTTPException(409, f"{item.name} has been ordered before — remove it instead, "
                                 "so past orders keep it")
    db.delete(item)
    db.commit()
    await broadcast_menu_changed()
    return {"id": item_id, "deleted": True}
