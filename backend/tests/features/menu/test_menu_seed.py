"""The Mr. Momo menu: seeding an empty database and replacing an existing menu."""
from conftest import place

from app.features.menu.menu_seed import SEED, replace_menu, seed_menu
from app.shared.database import SessionLocal
from app.shared.models import MenuItem

NAMES = [name for _, items in SEED for name, _, _ in items]


def menu_names(client):
    return [i["name"] for g in client.get("/api/menu").json() for i in g["items"]]


def test_seed_is_the_poster_menu(client):
    with SessionLocal() as db:
        seed_menu(db)
        seed_menu(db)  # a database that already has a menu is left alone
    assert menu_names(client) == NAMES and len(NAMES) == 17
    menu = {i["name"]: i for g in client.get("/api/menu").json() for i in g["items"]}
    assert (menu["Paneer Kurkure Momos"]["price_half"], menu["Paneer Kurkure Momos"]["price_full"]) == (60, 100)
    assert menu["Cold Coffee"]["price_half"] is None and menu["Cold Coffee"]["price_full"] == 50
    assert client.get("/api/menu").json()[0]["category"] == "Momos"


def test_replace_menu_keeps_ordered_items_for_past_orders(client, login, make_item):
    token = login()
    old = make_item(name="KitKat Shake", full=90)            # not on the poster: leaves the menu
    make_item(name="oreo shake", full=999, available=False)   # on the poster: fixed, stock switch kept
    order_id = place(client, token, old).json()["id"]
    with SessionLocal() as db:
        assert replace_menu(db) == {"added": 16, "updated": 1, "removed": 1}
        assert replace_menu(db) == {"added": 0, "updated": 17, "removed": 0}  # safe to run twice
        assert db.get(MenuItem, old["id"]).archived_at is not None           # hidden, not deleted
        oreo = db.query(MenuItem).filter(MenuItem.name == "Oreo Shake").one()
        assert oreo.price_full == 80 and oreo.is_available is False
    assert sorted(menu_names(client)) == sorted(NAMES)
    mine = client.get("/api/orders/mine", headers={"authorization": f"Bearer {token}"}).json()
    assert mine[0]["id"] == order_id and mine[0]["items"][0]["name"] == "KitKat Shake"
