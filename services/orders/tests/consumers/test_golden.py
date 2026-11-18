"""Consumer-driven golden tests. See README.md in this folder.

A fixture lists the fields a consumer actually reads. The live response must still
contain each of them with the same value. *New* fields are fine: consumers ignore
fields they don't know about (the "tolerant reader" rule), so additive changes pass.
"""

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

CASES = [
    ("/v1/orders/1", "v1_get_order_1.json"),
    ("/v1/orders", "v1_list_orders.json"),
    ("/v2/orders/1", "v2_get_order_1.json"),
]


def assert_contains(actual, expected, path="$"):
    """Recursively assert that ``actual`` has everything ``expected`` has."""
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"{path}: expected an object, got {actual!r}"
        for key, value in expected.items():
            assert key in actual, f"{path}.{key}: field missing, but a consumer reads it"
            assert_contains(actual[key], value, f"{path}.{key}")
    elif isinstance(expected, list):
        assert isinstance(actual, list), f"{path}: expected an array, got {actual!r}"
        assert len(actual) == len(expected), f"{path}: expected {len(expected)} items"
        for i, (a, e) in enumerate(zip(actual, expected, strict=True)):
            assert_contains(a, e, f"{path}[{i}]")
    else:
        assert actual == expected, f"{path}: consumer expects {expected!r}, API returned {actual!r}"


@pytest.mark.parametrize(("url", "fixture"), CASES)
def test_consumer_payload_unchanged(client, url, fixture):
    expected = json.loads((FIXTURES / fixture).read_text())
    assert_contains(client.get(url).json(), expected, path=f"GET {url}")
