def test_deprecated_version_sends_deprecation_headers(client):
    resp = client.get("/v1/orders/1")
    assert resp.headers["Deprecation"] == "true"
    assert resp.headers["Sunset"] == "Wed, 30 Jun 2027 23:59:59 GMT"
    assert resp.headers["Link"] == '</docs?version=v2>; rel="successor-version"'


def test_stable_version_has_no_deprecation_headers(client):
    resp = client.get("/v2/orders/1")
    assert "Deprecation" not in resp.headers
    assert "Sunset" not in resp.headers


def test_deprecated_version_is_marked_in_the_spec(client):
    spec = client.get("/openapi.json?version=v1").json()
    for path_item in spec["paths"].values():
        for operation in path_item.values():
            assert operation["deprecated"] is True
            assert operation["x-sunset"] == "2027-06-30"


def test_stable_version_is_not_marked_deprecated(client):
    spec = client.get("/openapi.json?version=v2").json()
    for path_item in spec["paths"].values():
        for operation in path_item.values():
            assert "deprecated" not in operation
