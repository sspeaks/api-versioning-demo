NEW_ORDER = {"customer_id": 1, "items": [{"sku": "WIDGET-1", "quantity": 1}]}


def test_reads_are_the_same_as_v2(client):
    assert client.get("/v3/orders/1").json() == client.get("/v2/orders/1").json()
    assert client.get("/v3/orders").json() == client.get("/v2/orders").json()


def test_only_create_order_changed(client):
    v2_paths = client.get("/openapi.json?version=v2").json()["paths"]
    v3_paths = client.get("/openapi.json?version=v3").json()["paths"]
    assert v3_paths["/orders/{order_id}"] == v2_paths["/orders/{order_id}"]
    assert v3_paths["/orders"]["get"] == v2_paths["/orders"]["get"]
    assert v3_paths["/orders"]["post"] != v2_paths["/orders"]["post"]


def test_create_requires_idempotency_key(client):
    resp = client.post("/v3/orders", json=NEW_ORDER)
    assert resp.status_code == 422
    assert resp.json()["detail"][0]["loc"] == ["header", "Idempotency-Key"]


def test_retry_with_same_key_returns_the_original_order(client):
    headers = {"Idempotency-Key": "checkout-7f3a9c"}
    first = client.post("/v3/orders", json=NEW_ORDER, headers=headers)
    retry = client.post("/v3/orders", json=NEW_ORDER, headers=headers)
    assert first.status_code == retry.status_code == 201
    assert first.json()["id"] == retry.json()["id"]
    assert len(client.get("/v3/orders").json()["items"]) == 4  # 3 seeded + 1, not 2


def test_v2_clients_are_unaffected(client):
    assert client.post("/v2/orders", json=NEW_ORDER).status_code == 201


def test_v2_requests_are_never_deduplicated(client):
    # v2 ignores the header. The version change gives each v2 request its own key.
    headers = {"Idempotency-Key": "checkout-7f3a9c"}
    first = client.post("/v2/orders", json=NEW_ORDER, headers=headers)
    second = client.post("/v2/orders", json=NEW_ORDER, headers=headers)
    assert first.json()["id"] != second.json()["id"]
