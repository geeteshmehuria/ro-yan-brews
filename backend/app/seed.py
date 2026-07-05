# TODO real menu from owner — placeholder items/prices until the stall poster is provided
from sqlalchemy.orm import Session

from .models import MenuItem

SEED = [
    ("Shakes", [("Oreo Shake", None, 80), ("KitKat Shake", None, 90),
                ("Cold Coffee", None, 70), ("Mango Shake", None, 70)]),
    ("Burgers", [("Aloo Tikki Burger", None, 50), ("Veg Cheese Burger", None, 70),
                 ("Paneer Burger", None, 90)]),
    ("Sandwiches", [("Veg Grilled Sandwich", None, 60), ("Cheese Sandwich", None, 80),
                    ("Paneer Sandwich", None, 90)]),
    ("Momos", [("Steam Momos", 50, 90), ("Fried Momos", 60, 110),
               ("Paneer Momos", 70, 130)]),
    ("Fries", [("Classic Fries", 40, 70), ("Peri Peri Fries", 50, 90),
               ("Cheese Fries", 60, 100)]),
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
