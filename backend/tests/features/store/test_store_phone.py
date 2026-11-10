"""The stall's phone number: the owner sets it, customers see it as "Call the stall"."""
from conftest import OWNER, bearer


def set_phone(client, headers, phone):
    return client.patch("/api/admin/store/phone", json={"phone": phone}, headers=headers)


def test_owner_sets_the_phone_and_everyone_can_read_it(client, login):
    owner = bearer(login(OWNER))
    r = set_phone(client, owner, "98765 43210")  # typed the way people write numbers
    assert r.status_code == 200 and r.json()["phone"] == "9876543210"
    assert client.get("/api/store").json()["phone"] == "9876543210"  # public, like the poster


def test_blank_phone_removes_it(client, login):
    owner = bearer(login(OWNER))
    set_phone(client, owner, "+919876543210")
    assert client.get("/api/store").json()["phone"] == "+919876543210"
    assert set_phone(client, owner, "  ").json()["phone"] is None
    assert client.get("/api/store").json()["phone"] is None


def test_a_wrong_number_is_refused_with_a_readable_reason(client, login):
    owner = bearer(login(OWNER))
    for bad in ("12345", "call me", "98765432101234567"):
        r = set_phone(client, owner, bad)
        assert r.status_code == 400 and "10-digit" in r.json()["detail"]
    assert client.get("/api/store").json()["phone"] is None


def test_only_the_owner_can_set_the_phone(client, login):
    assert set_phone(client, {}, "9876543210").status_code == 401
    assert set_phone(client, bearer(login()), "9876543210").status_code == 403
    assert client.get("/api/store").json()["phone"] is None


def test_phone_survives_pausing_and_is_pushed_live(client, login):
    owner_token = login(OWNER)
    owner = bearer(owner_token)
    with client.websocket_connect("/ws/menu") as menu:
        set_phone(client, owner, "9876543210")
        msg = menu.receive_json()
        assert msg["type"] == "store" and msg["phone"] == "9876543210" and msg["accepting_orders"] is True
    paused = client.patch("/api/admin/store", json={"accepting_orders": False}, headers=owner).json()
    assert paused["phone"] == "9876543210" and paused["accepting_orders"] is False
