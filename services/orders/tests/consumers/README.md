# Consumer golden tests

Each fixture here is a response that a known consumer depends on. Every field
in the fixture must still be present with the same value. Extra fields are fine,
because consumers ignore fields they don't read. If a test here fails, **you are
about to break a real caller**, even if the OpenAPI schema diff looks clean.

The schema gate (`tools/api_contract.py breaking`) catches *structural* breaks:
renamed fields, type changes, removed endpoints. It cannot catch *semantic*
breaks, where the shape stays the same but the meaning changes. For example,
`total_cents` starts returning dollars and is still an `int`. These tests catch
those.

| Fixture | Consumer that relies on it |
|---|---|
| `v1_get_order_1.json` | billing team's nightly reconciliation job |
| `v1_list_orders.json` | legacy partner dashboard |
| `v2_get_order_1.json` | mobile app order-detail screen |

To add one, record the response a consumer actually uses and name the owner in the table.
Only update a fixture when the change is intentional **and** the consumer has signed off.
