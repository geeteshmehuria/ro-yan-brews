from app.db import SessionLocal
from app.models import MenuItem

from conftest import OWNER, bearer, place

MOMOS = {"name": "Peri Peri Momos", "category": "Momos", "price_full": 120, "price_half": 70}


def menu_names(client):
    return [i["name"] for g in client.get("/api/menu").json() for i in g["items"]]


def test_only_the_owner_can_edit_the_menu(client, login, make_item):
    item, customer = make_item(), bearer(login())
    calls = [("post", "/api/admin/menu", MOMOS), ("patch", f"/api/admin/menu/{item['id']}", MOMOS),
             ("post", f"/api/admin/menu/{item['id']}/remove", None),
             ("post", f"/api/admin/menu/{item['id']}/restore", None),
             ("delete", f"/api/admin/menu/{item['id']}", None), ("get", "/api/admin/menu", None)]
    for method, url, body in calls:
        kwargs = {"json": body} if body else {}
        assert getattr(client, method)(url, headers=customer, **kwargs).status_code == 403, url
        assert getattr(client, method)(url, **kwargs).status_code == 401, url
    assert menu_names(client) == [item["name"]]  # nothing changed


def test_owner_adds_an_item_and_customers_can_order_it(client, login, make_item):
    make_item("Steam Momos", category="Momos", half=50, full=90)
    make_item("Oreo Shake", category="Shakes")
    owner = bearer(login(OWNER))
    r = client.post("/api/admin/menu", headers=owner,
                    json={**MOMOS, "name": "  Peri   Peri Momos ", "category": " Momos "})
    assert r.status_code == 201
    new = r.json()
    assert (new["name"], new["category"], new["archived"], new["ordered"]) == ("Peri Peri Momos", "Momos", False, False)
    groups = client.get("/api/menu").json()
    assert [g["category"] for g in groups] == ["Momos", "Shakes"]  # existing category keeps its place
    assert [i["name"] for i in groups[0]["items"]] == ["Steam Momos", "Peri Peri Momos"]  # added at its end
    order = place(client, login(), {"id": new["id"]}, size="half", qty=2)
    assert order.status_code == 201 and order.json()["total"] == 140


def test_a_new_category_goes_to_the_end(client, login, make_item):
    make_item("Oreo Shake", category="Shakes")
    owner = bearer(login(OWNER))
    client.post("/api/admin/menu", headers=owner,
                json={"name": "Masala Chai", "category": "Tea", "price_full": 20})
    assert [g["category"] for g in client.get("/api/menu").json()] == ["Shakes", "Tea"]


def test_menu_item_form_is_validated(client, login, make_item):
    make_item("Oreo Shake")
    owner = bearer(login(OWNER))
    bad = [
        {**MOMOS, "name": "x"},                          # too short
        {**MOMOS, "name": "x" * 81},                     # too long
        {**MOMOS, "category": "   "},                    # blank category
        {**MOMOS, "price_full": 0},                      # free
        {**MOMOS, "price_full": 10001},                  # absurd
        {**MOMOS, "price_full": 99.5},                   # rupees only
        {**MOMOS, "price_half": 120},                    # half not cheaper than full
        {**MOMOS, "price_half": 200},
    ]
    for body in bad:
        assert client.post("/api/admin/menu", headers=owner, json=body).status_code == 422, body
    dup = client.post("/api/admin/menu", headers=owner, json={**MOMOS, "name": "oreo SHAKE"})
    assert dup.status_code == 409
    assert menu_names(client) == ["Oreo Shake"]


def test_editing_changes_the_menu_but_not_past_orders(client, login, make_item):
    item = make_item("Oreo Shake", full=80)
    owner, token = bearer(login(OWNER)), login()
    old = place(client, token, item, qty=1).json()
    r = client.patch(f"/api/admin/menu/{item['id']}", headers=owner,
                     json={"name": "Oreo Thick Shake", "category": "Shakes", "price_full": 100})
    assert r.status_code == 200 and r.json()["ordered"] is True
    assert client.get("/api/menu").json()[0]["items"][0]["price_full"] == 100
    again = client.get(f"/api/orders/{old['id']}", headers=bearer(token)).json()
    assert again["total"] == 80 and again["items"][0]["price"] == 80  # sold price is kept
    # can't rename onto another item's name
    other = make_item("KitKat Shake")
    r = client.patch(f"/api/admin/menu/{other['id']}", headers=owner,
                     json={"name": "Oreo Thick Shake", "category": "Shakes", "price_full": 90})
    assert r.status_code == 409


def test_removed_items_leave_the_menu_and_cannot_be_ordered(client, login, make_item):
    item, keep = make_item("Mango Shake"), make_item("Oreo Shake")
    owner, token = bearer(login(OWNER)), login()
    past = place(client, token, item, qty=1).json()
    r = client.post(f"/api/admin/menu/{item['id']}/remove", headers=owner)
    assert r.status_code == 200 and r.json()["archived"] is True
    assert menu_names(client) == ["Oreo Shake"]
    refused = place(client, token, item)
    assert refused.status_code == 400 and "not on the menu any more" in refused.json()["detail"]
    # past orders still show it, and the owner still sees it (as removed)
    assert client.get(f"/api/orders/{past['id']}", headers=bearer(token)).json()["items"][0]["name"] == "Mango Shake"
    listed = {i["name"]: i for i in client.get("/api/admin/menu", headers=owner).json()}
    assert listed["Mango Shake"]["archived"] is True and listed["Oreo Shake"]["archived"] is False
    # restore puts it back
    assert client.post(f"/api/admin/menu/{item['id']}/restore", headers=owner).json()["archived"] is False
    assert sorted(menu_names(client)) == ["Mango Shake", "Oreo Shake"]
    assert place(client, token, item, qty=1).status_code == 201
    assert keep  # untouched


def test_a_removed_name_can_be_reused_but_restore_refuses_a_clash(client, login, make_item):
    item = make_item("Mango Shake")
    owner = bearer(login(OWNER))
    client.post(f"/api/admin/menu/{item['id']}/remove", headers=owner)
    r = client.post("/api/admin/menu", headers=owner,
                    json={"name": "Mango Shake", "category": "Shakes", "price_full": 95})
    assert r.status_code == 201  # removed items don't block their name
    assert client.post(f"/api/admin/menu/{item['id']}/restore", headers=owner).status_code == 409


def test_delete_is_only_for_items_never_ordered(client, login, make_item):
    typo, sold = make_item("Panner Momos"), make_item("Steam Momos")
    owner = bearer(login(OWNER))
    place(client, login(), sold)
    assert client.delete(f"/api/admin/menu/{sold['id']}", headers=owner).status_code == 409
    assert client.delete(f"/api/admin/menu/{typo['id']}", headers=owner).status_code == 200
    with SessionLocal() as db:
        assert db.get(MenuItem, typo["id"]) is None and db.get(MenuItem, sold["id"]) is not None
    assert client.delete(f"/api/admin/menu/{typo['id']}", headers=owner).status_code == 404


def test_menu_changes_are_pushed_live(client, login, make_item):
    item = make_item("Oreo Shake")
    owner = bearer(login(OWNER))
    with client.websocket_connect("/ws/menu") as ws:
        client.post("/api/admin/menu", headers=owner, json=MOMOS)
        assert ws.receive_json() == {"type": "menu_changed"}
        client.post(f"/api/admin/menu/{item['id']}/remove", headers=owner)
        assert ws.receive_json() == {"type": "menu_changed"}


def test_delete_is_allowed_by_cors(client):
    r = client.options("/api/admin/menu/1", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "DELETE"})
    assert r.status_code == 200
