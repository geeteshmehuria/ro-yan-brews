from datetime import timedelta

from app.clock import days_start, to_ist, today_start, utcnow
from app.db import SessionLocal
from app.models import Order

from conftest import OWNER, bearer, place


def status(client, owner, oid, st):
    assert client.patch(f"/api/admin/orders/{oid}/status", json={"status": st}, headers=owner).status_code == 200


def shift(oid, *, created=None, completed=None):
    with SessionLocal() as db:
        o = db.get(Order, oid)
        if created is not None:
            o.created_at = created
        if completed is not None:
            o.completed_at = completed
        db.commit()


def report(client, owner, days=7):
    r = client.get(f"/api/admin/reports?days={days}", headers=owner)
    assert r.status_code == 200
    return r.json()


def test_reports_are_owner_only(client, login):
    assert client.get("/api/admin/reports").status_code == 401
    assert client.get("/api/admin/reports", headers=bearer(login())).status_code == 403


def test_today_summary(client, login, make_item):
    owner, item = bearer(login(OWNER)), make_item(full=100)
    tokens = [login(f"c{n}@x.com") for n in range(4)]
    a, b, c, d = (place(client, t, item, qty=1).json()["id"] for t in tokens)
    status(client, owner, a, "completed")
    status(client, owner, b, "completed")
    client.post(f"/api/orders/{c}/cancel", headers=bearer(tokens[2]))
    status(client, owner, d, "ready")
    status(client, owner, d, "not_collected")
    t = report(client, owner)["today"]
    assert (t["orders"], t["completed"], t["cancelled"], t["not_collected"]) == (3, 2, 1, 1)
    assert (t["cash"], t["average"], t["in_progress"]) == (200, 100, 0)


def test_daily_cash_counts_on_the_day_it_was_paid(client, login, make_item):
    owner, item = bearer(login(OWNER)), make_item(full=60)
    late = place(client, login("a@x.com"), item, qty=1).json()["id"]
    old = place(client, login("b@x.com"), item, qty=1).json()["id"]
    status(client, owner, late, "completed")
    status(client, owner, old, "completed")
    # placed yesterday, paid today -> today's cash; placed and paid 3 days ago -> that day
    shift(late, created=utcnow() - timedelta(days=1))
    shift(old, created=utcnow() - timedelta(days=3), completed=utcnow() - timedelta(days=3))
    r = report(client, owner)
    assert len(r["daily"]) == 7 and r["daily"][-1]["date"] == to_ist(today_start()).date().isoformat()
    cash = [d["cash"] for d in r["daily"]]
    assert cash[-1] == 60 and cash[-4] == 60 and sum(cash) == 120
    assert r["period"]["cash"] == 120 and r["today"]["cash"] == 60
    orders = [d["orders"] for d in r["daily"]]
    assert orders[-2] == 1 and orders[-4] == 1  # counted on the day placed


def test_older_days_fall_outside_the_range(client, login, make_item):
    owner, token = bearer(login(OWNER)), login()
    oid = place(client, token, make_item(full=90), qty=1).json()["id"]
    status(client, owner, oid, "completed")
    shift(oid, created=days_start(7) - timedelta(hours=1), completed=days_start(7) - timedelta(hours=1))
    assert report(client, owner)["period"]["cash"] == 0
    assert report(client, owner, days=30)["period"]["cash"] == 90


def test_top_items_use_sold_prices_and_split_half_and_full(client, login, make_item):
    owner = bearer(login(OWNER))
    momo, shake = make_item("Steam Momos", half=50, full=90), make_item("Oreo Shake", full=80)
    body = {"items": [{"menu_item_id": momo["id"], "size": "half", "qty": 3},
                      {"menu_item_id": momo["id"], "size": "full", "qty": 1},
                      {"menu_item_id": shake["id"], "qty": 2}]}
    token = login()
    oid = client.post("/api/orders", json=body, headers=bearer(token)).json()["id"]
    unpaid = place(client, login("x@x.com"), shake, qty=9).json()["id"]  # not Done: not a sale yet
    status(client, owner, oid, "completed")
    client.patch(f"/api/admin/menu/{momo['id']}", headers=owner,
                 json={"name": "Steam Momos", "category": "Momos", "price_full": 200, "price_half": 150})
    top = report(client, owner)["top_items"]
    assert top[0] == {"name": "Steam Momos", "qty": 4, "half": 3, "value": 240}  # 3*50 + 90, old prices
    assert top[1] == {"name": "Oreo Shake", "qty": 2, "half": 0, "value": 160}
    assert unpaid


def test_busiest_hours_count_placed_orders_by_ist_hour(client, login, make_item):
    owner, item = bearer(login(OWNER)), make_item()
    ids = [place(client, login(f"h{n}@x.com"), item, qty=1).json()["id"] for n in range(3)]
    at = today_start() + timedelta(hours=13, minutes=40)  # 19:10 IST... in naive UTC
    for oid in ids[:2]:
        shift(oid, created=at)
    client.post(f"/api/orders/{ids[2]}/cancel", headers=bearer(login("h2@x.com")))
    hours = report(client, owner)["hours"]
    assert len(hours) == 24 and hours[to_ist(at).hour] == 2 and sum(hours) == 2  # cancelled not counted


def test_days_are_clamped(client, login):
    owner = bearer(login(OWNER))
    assert report(client, owner, days=0)["days"] == 1
    assert len(report(client, owner, days=500)["daily"]) == 90
