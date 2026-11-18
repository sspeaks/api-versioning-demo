def test_list_orders_is_a_bare_array(client):
    resp = client.get("/v1/orders")
    assert resp.status_code == 200
    assert [o["id"] for o in resp.json()] == [1, 2, 3]


def test_get_order(client):
    body = client.get("/v1/orders/1").json()
    assert body["customer_name"] == "Ada Lovelace"
    assert body["total_cents"] == 3048
    assert body["items"] == [{"sku": "WIDGET-1", "qty": 2}, {"sku": "GADGET-7", "qty": 1}]


def test_paid_is_reported_as_pending_to_v1_clients(client):
    # The domain has a "paid" state that v1 never published. See api/v1/mappers.py.
    assert client.get("/v1/orders/2").json()["status"] == "pending"


def test_internal_fields_never_leak(client):
    body = client.get("/v1/orders/2").json()
    assert set(body) == {"id", "customer_name", "items", "total_cents", "status"}


def test_not_found(client):
    resp = client.get("/v1/orders/999")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "order 999 not found"}


def test_create_order(client):
    resp = client.post(
        "/v1/orders",
        json={"customer_name": "Grace Hopper", "items": [{"sku": "GIZMO-3", "qty": 2}]},
    )
    assert resp.status_code == 201
    assert resp.json()["total_cents"] == 19800
    assert resp.json()["status"] == "pending"


def test_create_order_unknown_sku(client):
    resp = client.post(
        "/v1/orders", json={"customer_name": "X", "items": [{"sku": "NOPE", "qty": 1}]}
    )
    assert resp.status_code == 400
