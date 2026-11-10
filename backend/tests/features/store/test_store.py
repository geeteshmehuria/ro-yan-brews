"""The Open / Paused switch."""
from conftest import OWNER, bearer, place


def status(client, owner, oid, st):
    assert client.patch(f"/api/admin/orders/{oid}/status", json={"status": st}, headers=owner).status_code == 200


def stats(client, owner):
    return client.get("/api/admin/stats/today", headers=owner).json()


def test_store_is_open_by_default(client):
    assert client.get("/api/store").json() == {"accepting_orders": True, "message": None, "phone": None}


def test_paused_store_refuses_new_orders_until_reopened(client, login, make_item):
    owner, token, item = bearer(login(OWNER)), login(), make_item()
    r = client.patch("/api/admin/store", json={"accepting_orders": False}, headers=owner)
    assert r.status_code == 200 and r.json()["accepting_orders"] is False
    assert client.get("/api/store").json()["message"].startswith("We're not taking orders")
    refused = place(client, token, item)
    assert refused.status_code == 409 and "not taking orders" in refused.json()["detail"]
    assert stats(client, owner)["accepting_orders"] is False
    client.patch("/api/admin/store", json={"accepting_orders": True}, headers=owner)
    assert place(client, token, item).status_code == 201


def test_pausing_does_not_touch_orders_already_placed(client, login, make_item):
    owner, token = bearer(login(OWNER)), login()
    oid = place(client, token, make_item()).json()["id"]
    client.patch("/api/admin/store", json={"accepting_orders": False}, headers=owner)
    status(client, owner, oid, "ready")  # the owner can still finish it
    assert client.post(f"/api/orders/{oid}/cancel", headers=bearer(token)).status_code == 400  # ready: as before


def test_only_the_owner_can_pause(client, login):
    assert client.patch("/api/admin/store", json={"accepting_orders": False}).status_code == 401
    r = client.patch("/api/admin/store", json={"accepting_orders": False}, headers=bearer(login()))
    assert r.status_code == 403
    assert client.get("/api/store").json()["accepting_orders"] is True


def test_pause_is_pushed_live_to_menus_and_the_owner(client, login):
    owner_token = login(OWNER)
    with client.websocket_connect("/ws/menu") as menu, \
            client.websocket_connect(f"/ws/admin?token={owner_token}") as admin:
        client.patch("/api/admin/store", json={"accepting_orders": False}, headers=bearer(owner_token))
        assert menu.receive_json()["type"] == "store"
        msg = admin.receive_json()
        assert msg["type"] == "store" and msg["accepting_orders"] is False
