"""The public menu and stock on/off."""
from conftest import OWNER, bearer, place


def test_menu_grouped_by_category(client, make_item):
    make_item("Oreo Shake", category="Shakes")
    make_item("Steam Momos", full=90, half=50, category="Momos")
    data = client.get("/api/menu").json()
    assert [g["category"] for g in data] == ["Shakes", "Momos"]
    assert data[1]["items"][0]["price_half"] == 50


def test_stock_toggle_blocks_order_and_shows_in_menu(client, login, make_item):
    item = make_item()
    admin = bearer(login(OWNER))
    r = client.patch(f"/api/admin/menu/{item['id']}/availability", json={"is_available": False}, headers=admin)
    assert r.status_code == 200
    assert client.get("/api/menu").json()[0]["items"][0]["is_available"] is False
    r = place(client, login(), item)
    assert r.status_code == 400 and "out of stock" in r.json()["detail"].lower()
