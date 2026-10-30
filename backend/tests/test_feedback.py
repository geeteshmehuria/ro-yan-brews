from app.db import SessionLocal
from app.models import Feedback

from conftest import OWNER, bearer, place


def complete(client, oid, owner):
    r = client.patch(f"/api/admin/orders/{oid}/status", json={"status": "completed"}, headers=owner)
    assert r.status_code == 200


def rate(client, token, oid, ratings, allow_public=False):
    return client.post(f"/api/orders/{oid}/feedback", headers=bearer(token),
                       json={"ratings": ratings, "allow_public": allow_public})


def test_feedback_is_saved_for_a_collected_order(client, login, make_item):
    momo, shake = make_item("Steam Momos", half=50, full=90), make_item("Oreo Shake")
    token, owner = login(), bearer(login(OWNER))
    body = {"items": [{"menu_item_id": momo["id"], "size": "half", "qty": 2},
                      {"menu_item_id": shake["id"], "qty": 1}]}
    oid = client.post("/api/orders", json=body, headers=bearer(token)).json()["id"]
    complete(client, oid, owner)

    r = rate(client, token, oid, [{"menu_item_id": momo["id"], "rating": 5, "comment": "  Loved it  "},
                                  {"menu_item_id": shake["id"], "rating": 3, "comment": "   "}], allow_public=True)
    assert r.status_code == 201
    with SessionLocal() as db:
        rows = {f.menu_item_id: f for f in db.query(Feedback)}
        assert rows[momo["id"]].comment == "Loved it" and rows[momo["id"]].rating == 5
        assert rows[shake["id"]].comment is None  # blank comment stored as NULL
        assert all(f.allow_public and not f.approved for f in rows.values())  # never shown until picked
    mine = client.get("/api/orders/mine", headers=bearer(token)).json()
    assert mine[0]["reviewed"] is True
    assert {i["menu_item_id"] for i in mine[0]["items"]} == {momo["id"], shake["id"]}


def test_only_collected_orders_can_be_rated(client, login, make_item):
    item, token, owner = make_item(), login(), bearer(login(OWNER))
    oid = place(client, token, item).json()["id"]
    one = [{"menu_item_id": item["id"], "rating": 4}]
    assert rate(client, token, oid, one).status_code == 400  # still "placed"
    client.patch(f"/api/admin/orders/{oid}/status", json={"status": "ready"}, headers=owner)
    assert rate(client, token, oid, one).status_code == 400  # ready but not collected
    cancelled = place(client, token, item).json()["id"]
    client.post(f"/api/orders/{cancelled}/cancel", headers=bearer(token))
    assert rate(client, token, cancelled, one).status_code == 400


def test_only_your_own_order_can_be_rated(client, login, make_item):
    item, owner = make_item(), bearer(login(OWNER))
    oid = place(client, login("aa@x.com"), item).json()["id"]
    complete(client, oid, owner)
    one = [{"menu_item_id": item["id"], "rating": 1}]
    assert rate(client, login("bb@x.com"), oid, one).status_code == 404
    assert client.post(f"/api/orders/{oid}/feedback", json={"ratings": one}).status_code == 401


def test_an_order_is_rated_once(client, login, make_item):
    item, token, owner = make_item(), login(), bearer(login(OWNER))
    oid = place(client, token, item).json()["id"]
    complete(client, oid, owner)
    one = [{"menu_item_id": item["id"], "rating": 4}]
    assert rate(client, token, oid, one).status_code == 201
    assert rate(client, token, oid, one).status_code == 409


def test_only_items_in_the_order_can_be_rated(client, login, make_item):
    item, other, token, owner = make_item(), make_item("Fries"), login(), bearer(login(OWNER))
    oid = place(client, token, item).json()["id"]
    complete(client, oid, owner)
    assert rate(client, token, oid, [{"menu_item_id": other["id"], "rating": 5}]).status_code == 400
    with SessionLocal() as db:
        assert db.query(Feedback).count() == 0  # nothing half-saved


def test_feedback_input_is_bounded(client, login, make_item):
    item, token, owner = make_item(), login(), bearer(login(OWNER))
    oid = place(client, token, item).json()["id"]
    complete(client, oid, owner)
    for bad in ([{"menu_item_id": item["id"], "rating": 0}],
                [{"menu_item_id": item["id"], "rating": 6}],
                [{"menu_item_id": item["id"], "rating": 3, "comment": "x" * 301}],
                [{"menu_item_id": item["id"], "rating": 3}] * 2,
                []):
        assert rate(client, token, oid, bad).status_code == 422


def test_owner_sees_averages_and_recent_feedback(client, login, make_item):
    momo, shake = make_item("Steam Momos"), make_item("Oreo Shake")
    owner = bearer(login(OWNER))
    for email, stars in (("aa@x.com", 5), ("bb@x.com", 2)):
        token = login(email)
        oid = place(client, token, momo).json()["id"]
        complete(client, oid, owner)
        assert rate(client, token, oid, [{"menu_item_id": momo["id"], "rating": stars,
                                          "comment": f"from {email}"}]).status_code == 201
    data = client.get("/api/admin/feedback", headers=owner).json()
    assert data["items"] == [{"menu_item_id": momo["id"], "name": "Steam Momos", "average": 3.5, "count": 2}]
    assert [f["comment"] for f in data["recent"]] == ["from bb@x.com", "from aa@x.com"]  # newest first
    assert data["recent"][0]["email"] == "bb@x.com" and data["recent"][0]["allow_public"] is False


def test_feedback_list_is_owner_only(client, login):
    assert client.get("/api/admin/feedback").status_code == 401
    assert client.get("/api/admin/feedback", headers=bearer(login())).status_code == 403
