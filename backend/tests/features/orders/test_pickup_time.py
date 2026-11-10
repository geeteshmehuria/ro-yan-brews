"""Pickup time: the customer says when they'll reach the stall, the owner sees it."""
from conftest import OWNER, bearer, my_order


def order(client, token, item, **extra):
    body = {"items": [{"menu_item_id": item["id"], "size": "na", "qty": 1}], **extra}
    return client.post("/api/orders", json=body, headers=bearer(token))


def test_pickup_minutes_is_saved_and_shown_to_both_sides(client, login, make_item):
    token, owner = login(), bearer(login(OWNER))
    r = order(client, token, make_item(), pickup_minutes=15)
    assert r.status_code == 201 and r.json()["pickup_minutes"] == 15
    assert my_order(client, token, r.json()["id"])["pickup_minutes"] == 15
    assert client.get("/api/admin/orders", headers=owner).json()[0]["pickup_minutes"] == 15


def test_coming_now_is_zero_not_missing(client, login, make_item):
    assert order(client, login(), make_item(), pickup_minutes=0).json()["pickup_minutes"] == 0


def test_older_apps_send_no_pickup_time(client, login, make_item):
    r = order(client, login(), make_item())
    assert r.status_code == 201 and r.json()["pickup_minutes"] is None


def test_silly_pickup_times_are_refused(client, login, make_item):
    token, item = login(), make_item()
    assert order(client, token, item, pickup_minutes=-5).status_code == 422
    assert order(client, token, item, pickup_minutes=600).status_code == 422
