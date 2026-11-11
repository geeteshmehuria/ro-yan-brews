"""Live channels: /ws/admin and /ws/me."""
import time

import pytest
from conftest import OWNER, bearer, place
from starlette.websockets import WebSocketDisconnect

from app.shared.ws_manager import manager


def set_status(client, owner_token, oid, status):
    return client.patch(f"/api/admin/orders/{oid}/status", json={"status": status},
                        headers=bearer(owner_token))


def test_ws_admin_receives_new_order_with_full_email(client, login, make_item):
    admin_token = login(OWNER)
    with client.websocket_connect(f"/ws/admin?token={admin_token}") as ws:
        place(client, login("buyer@gmail.com"), make_item())
        msg = ws.receive_json()
        assert msg["type"] == "new_order" and msg["order"]["order_number"] == 1
        assert msg["order"]["email"] == "buyer@gmail.com"


def test_ws_admin_non_owner_rejected(client, login):
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect(f"/ws/admin?token={login()}"):
            pass
    assert e.value.code == 4401


def test_ws_me_needs_a_token(client):
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect("/ws/me"):
            pass
    assert e.value.code == 4401


def test_ws_me_gets_status_updates_for_all_own_orders(client, login, make_item):
    owner, token = login(OWNER), login()
    item = make_item()
    first = place(client, token, item).json()["id"]
    second = place(client, token, item).json()["id"]
    with client.websocket_connect(f"/ws/me?token={token}") as ws:
        set_status(client, owner, first, "preparing")
        set_status(client, owner, second, "preparing")
        assert ws.receive_json() == {"type": "status", "order_id": first, "status": "preparing"}
        assert ws.receive_json() == {"type": "status", "order_id": second, "status": "preparing"}


def test_ws_me_does_not_leak_other_customers_updates(client, login, make_item):
    owner, other = login(OWNER), login("other@x.com")
    oid = place(client, login("aa@x.com"), make_item()).json()["id"]
    with client.websocket_connect(f"/ws/me?token={other}") as ws:
        set_status(client, owner, oid, "preparing")
        place(client, other, make_item("Burger"))  # nothing for `other` yet...
        client.post(f"/api/orders/{oid}/cancel", headers=bearer(login("aa@x.com")))
        mine = place(client, other, make_item("Fries")).json()["id"]
        set_status(client, owner, mine, "preparing")
        assert ws.receive_json()["order_id"] == mine  # first message is for their own order


def test_ws_me_reports_cancellation_to_customer_and_owner(client, login, make_item):
    token, owner = login(), login(OWNER)
    oid = place(client, token, make_item()).json()["id"]
    with client.websocket_connect(f"/ws/me?token={token}") as mine, \
            client.websocket_connect(f"/ws/admin?token={owner}") as admin:
        client.post(f"/api/orders/{oid}/cancel", headers=bearer(token))
        expected = {"type": "status", "order_id": oid, "status": "cancelled"}
        assert mine.receive_json() == expected
        assert admin.receive_json() == expected


def test_ws_me_pool_is_cleaned_up(client, login):
    token = login()
    cid = client.get("/api/me", headers=bearer(token)) and __import__("jwt").decode(
        token, options={"verify_signature": False})["cid"]
    with client.websocket_connect(f"/ws/me?token={token}"):
        assert cid in manager.customers
    for _ in range(50):  # the server side notices the disconnect asynchronously
        if cid not in manager.customers:
            break
        time.sleep(0.02)
    assert cid not in manager.customers


def test_ws_closes_with_4401_when_the_token_expires(client, login):
    import jwt

    from app.shared import auth
    session = jwt.decode(login(OWNER), auth.JWT_SECRET, algorithms=["HS256"])
    for path in ("/ws/admin", "/ws/me"):
        short = jwt.encode({**session, "exp": int(time.time()) + 2}, auth.JWT_SECRET, algorithm="HS256")
        with client.websocket_connect(f"{path}?token={short}") as ws:
            with pytest.raises(WebSocketDisconnect) as e:
                ws.receive_json()  # nothing is sent; the server closes once the token lapses
            assert e.value.code == 4401
        assert not manager.admin and not manager.customers  # and the socket left its pool
