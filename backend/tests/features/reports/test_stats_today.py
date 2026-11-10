"""The owner's numbers for today (cash, to collect, out of stock)."""
from datetime import timedelta

from conftest import OWNER, bearer, place

from app.shared.clock import utcnow
from app.shared.database import SessionLocal
from app.shared.models import Order


def status(client, owner, oid, st):
    assert client.patch(f"/api/admin/orders/{oid}/status", json={"status": st}, headers=owner).status_code == 200


def stats(client, owner):
    return client.get("/api/admin/stats/today", headers=owner).json()


def test_stats_today(client, login, make_item):
    admin = bearer(login(OWNER))
    place(client, login(), make_item("Oreo Shake", full=80))
    stats = client.get("/api/admin/stats/today", headers=admin).json()
    assert stats["orders"] == 1
    assert (stats["cash_collected"], stats["to_collect"]) == (0, 160)  # not paid yet


def test_cancelled_orders_are_excluded_from_stats(client, login, make_item):
    owner, token = login(OWNER), login()
    item = make_item(full=80)
    place(client, token, item)  # 160, kept
    oid = place(client, token, item).json()["id"]
    client.post(f"/api/orders/{oid}/cancel", headers=bearer(token))
    stats = client.get("/api/admin/stats/today", headers=bearer(owner)).json()
    assert stats["orders"] == 1 and stats["cancelled"] == 1
    assert stats["to_collect"] == 160 and stats["cash_collected"] == 0


def test_cash_is_only_counted_once_an_order_is_done(client, login, make_item):
    owner, token = bearer(login(OWNER)), login()
    item = make_item(full=100)
    done, ready, new = (place(client, token, item, qty=1).json()["id"] for _ in range(3))
    status(client, owner, done, "completed")
    status(client, owner, ready, "ready")
    s = stats(client, owner)
    assert s["cash_collected"] == 100 and s["completed"] == 1
    assert s["to_collect"] == 200  # ready + placed: not paid yet
    assert s["active"] == {"placed": 1, "preparing": 0, "ready": 1}
    assert s["orders"] == 3 and s["cash_collected"] == 100


def test_yesterdays_unfinished_order_is_still_to_collect(client, login, make_item):
    owner, token = bearer(login(OWNER)), login()
    oid = place(client, token, make_item(full=90), qty=1).json()["id"]
    with SessionLocal() as db:
        db.get(Order, oid).created_at = utcnow() - timedelta(days=1)
        db.commit()
    s = stats(client, owner)
    assert s["orders"] == 0 and s["to_collect"] == 90 and s["active"]["placed"] == 1


def test_out_of_stock_count_ignores_removed_items(client, login, make_item):
    owner = bearer(login(OWNER))
    make_item("A", available=False)
    gone = make_item("B", available=False)
    make_item("C")
    client.post(f"/api/admin/menu/{gone['id']}/remove", headers=owner)
    assert stats(client, owner)["out_of_stock"] == 1


def test_cash_counts_on_the_day_the_order_was_done(client, login, make_item):
    """Placed before midnight, collected after: it is the new day's cash, not lost."""
    owner, token = bearer(login(OWNER)), login()
    oid = place(client, token, make_item(full=120), qty=1).json()["id"]
    with SessionLocal() as db:
        db.get(Order, oid).created_at = utcnow() - timedelta(days=1)  # placed "yesterday"
        db.commit()
    assert stats(client, owner)["to_collect"] == 120
    status(client, owner, oid, "completed")  # collected today
    s = stats(client, owner)
    assert (s["cash_collected"], s["completed"], s["to_collect"], s["orders"]) == (120, 1, 0, 0)
    with SessionLocal() as db:
        assert db.get(Order, oid).completed_at is not None


def test_cash_from_an_earlier_day_is_not_counted_today(client, login, make_item):
    owner, token = bearer(login(OWNER)), login()
    oid = place(client, token, make_item(full=70), qty=1).json()["id"]
    status(client, owner, oid, "completed")
    with SessionLocal() as db:
        o = db.get(Order, oid)
        o.created_at = o.completed_at = utcnow() - timedelta(days=1)
        db.commit()
    assert stats(client, owner)["cash_collected"] == 0


def test_orders_done_before_completed_at_existed_count_by_placed_day(client, login, make_item):
    owner, token = bearer(login(OWNER)), login()
    oid = place(client, token, make_item(full=50), qty=1).json()["id"]
    status(client, owner, oid, "completed")
    with SessionLocal() as db:
        db.get(Order, oid).completed_at = None  # an old row
        db.commit()
    assert stats(client, owner)["cash_collected"] == 50
