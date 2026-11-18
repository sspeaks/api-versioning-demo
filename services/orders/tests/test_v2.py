def test_list_orders_is_paginated(client):
    first = client.get("/v2/orders", params={"limit": 2}).json()
    assert [o["id"] for o in first["items"]] == [1, 2]
    assert first["next_cursor"] == "2"

    second = client.get("/v2/orders", params={"limit": 2, "cursor": first["next_cursor"]}).json()
    assert [o["id"] for o in second["items"]] == [3]
    assert second["next_cursor"] is None


def test_get_order(client):
    body = client.get("/v2/orders/1").json()
    assert body["customer"] == {"id": 1, "name": "Ada Lovelace"}
    assert body["total"] == {"amount": "30.48", "currency": "USD"}
    assert body["items"][0] == {
        "sku": "WIDGET-1",
        "quantity": 2,
        "unit_price": {"amount": "12.99", "currency": "USD"},
    }


def test_v2_exposes_paid_status(client):
    assert client.get("/v2/orders/2").json()["status"] == "paid"


def test_internal_fields_never_leak(client):
    body = client.get("/v2/orders/1").json()
    assert "email" not in body["customer"]
    assert "fraud_score" not in body and "tags" not in body


def test_create_order(client):
    resp = client.post(
        "/v2/orders", json={"customer_id": 2, "items": [{"sku": "GADGET-7", "quantity": 3}]}
    )
    assert resp.status_code == 201
    assert resp.json()["total"] == {"amount": "13.50", "currency": "USD"}


def test_create_order_unknown_customer(client):
    resp = client.post(
        "/v2/orders", json={"customer_id": 42, "items": [{"sku": "GADGET-7", "quantity": 1}]}
    )
    assert resp.status_code == 400
    assert resp.json() == {"detail": "unknown customer_id"}


def test_item_count(client):
    assert client.get("/v2/orders/1").json()["item_count"] == 3
