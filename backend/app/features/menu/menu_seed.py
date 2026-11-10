"""The Mr. Momo menu, from the stall's poster. (category, [(name, half price, full price)]).

`seed_menu` fills an empty database (local / a brand-new one). A database that already has a
menu is changed with `replace_menu`, run once by hand from `backend/`:

    python -m app.features.menu.menu_seed          # uses DATABASE_URL, like the app

Day to day the owner edits the menu in the admin dashboard, not here.
"""
from sqlalchemy.orm import Session

from app.shared.clock import utcnow
from app.shared.models import MenuItem

SEED = [
    ("Momos", [("Steam Veg Momos", 30, 50), ("Fry Veg Momos", 30, 50), ("Paneer Momos", 40, 70),
               ("Veg Kurkure Momos", 50, 80), ("Paneer Kurkure Momos", 60, 100)]),
    ("Fries", [("Fries", 30, 50)]),
    ("Burgers", [("Cheese Burger", None, 70), ("Veg Burger", None, 50)]),
    ("Sandwiches", [("Veg Grilled Sandwich", None, 50), ("Veg Paneer Grilled Sandwich", None, 60),
                    ("Veg Cheese Sandwich", None, 70), ("Veg Paneer with Cheese Sandwich", None, 80)]),
    ("Shakes", [("Cold Coffee", None, 50), ("Oreo Shake", None, 80), ("Chocolate Shake", None, 70),
                ("Blue Berry Shake", None, 70), ("Strawberry Shake", None, 70)]),
]


def seed_menu(db: Session) -> None:
    if db.query(MenuItem).count() > 0:
        return
    order = 0
    for category, items in SEED:
        for name, half, full in items:
            db.add(MenuItem(name=name, category=category, price_half=half,
                            price_full=full, sort_order=order))
            order += 1
    db.commit()


def replace_menu(db: Session) -> dict:
    """Make the menu match SEED. Items not in it are removed from the menu (archived, never
    deleted: past orders and reviews point at them); the rest are added or updated by name.
    Stock switches are left alone. Safe to run twice."""
    before = db.query(MenuItem).all()
    by_name: dict = {}
    for item in sorted(before, key=lambda i: (i.archived_at is not None, i.id)):
        by_name.setdefault(item.name.lower(), item)  # an item on the menu wins over a removed namesake
    kept, added, order = set(), 0, 0
    for category, items in SEED:
        for name, half, full in items:
            item = by_name.get(name.lower())
            if item is None:
                item = MenuItem(name=name, is_available=True)
                db.add(item)
                added += 1
            else:
                kept.add(item.id)
            item.name, item.category, item.price_half, item.price_full = name, category, half, full
            item.sort_order, item.archived_at = order, None
            order += 1
    removed = 0
    for item in before:
        if item.archived_at is None and item.id not in kept:
            item.archived_at = utcnow()
            removed += 1
    db.commit()
    return {"added": added, "updated": len(kept), "removed": removed}


if __name__ == "__main__":
    from app.shared.database import Base, SessionLocal, add_missing_columns, engine

    Base.metadata.create_all(bind=engine)
    add_missing_columns(engine)
    with SessionLocal() as session:
        print(replace_menu(session))
