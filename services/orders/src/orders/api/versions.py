"""Every difference between API versions lives in this file.

The schemas and routes in this package describe only the LATEST version. Each
``VersionChange`` below describes ONE breaking change, as instructions for
going back to the previous version:

* ``instructions_to_migrate_to_previous_version``: how the *contract* differed
  (fields that didn't exist, had another name or type, ...). Cadwyn uses these to
  generate the older version's pydantic models and OpenAPI document.
* ``convert_request_to_next_version_for``: upgrade an old request to the latest shape.
* ``convert_response_to_previous_version_for``: downgrade a latest response to the old shape.

Adding v3 means editing the latest schemas/routes, then writing the change that
turns it back into v2 and listing it under ``Version("v3", ...)``. Nothing is copied.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from cadwyn import (
    HeadVersion,
    RequestInfo,
    ResponseInfo,
    Version,
    VersionBundle,
    VersionChange,
    VersionChangeWithSideEffects,
    convert_request_to_next_version_for,
    convert_response_to_previous_version_for,
    endpoint,
    schema,
)
from pydantic import Field

from orders.api.schemas import (
    CreateOrderItem,
    CreateOrderRequest,
    ListOrdersParams,
    Order,
    OrderItem,
)
from orders.domain.repository import get_repository

LIST_ORDERS = "/{api_version}/orders"


def orders_in(body: dict | list) -> list[dict]:
    """The orders in a list response, whether or not it has been un-paginated yet.

    Migrations keyed on the ``Order`` schema only run when ``Order`` is the endpoint's
    whole response, so each change also migrates the orders inside the list endpoint.
    """
    return body["items"] if isinstance(body, dict) else body


# --------------------------------------------------------------------------- #
# v1 -> v2
# --------------------------------------------------------------------------- #
class CustomerBecameAnObject(VersionChange):
    description = (
        "Orders reference the customer as `customer: {id, name}` instead of a bare "
        "`customer_name` string, and new orders are placed by `customer_id`."
    )
    instructions_to_migrate_to_previous_version = (
        schema(Order).field("customer").didnt_exist,
        schema(Order).field("customer_name").existed_as(type=str),
        schema(CreateOrderRequest).field("customer_id").didnt_exist,
        schema(CreateOrderRequest)
        .field("customer_name")
        .existed_as(type=str, info=Field(min_length=1)),
    )

    @convert_request_to_next_version_for(CreateOrderRequest)
    def customer_name_to_id(request: RequestInfo) -> None:
        # v1 identified customers by name, so turning a v1 request into a v2 one
        # needs a lookup. This is where "only the shape changed" stops being true,
        # and where single-source versioning gets harder than separate versions.
        name = request.body.pop("customer_name")
        request.body["customer_id"] = get_repository().get_or_create_customer_by_name(name).id

    @convert_response_to_previous_version_for(Order)
    def order(response: ResponseInfo) -> None:
        _customer_to_name(response.body)

    @convert_response_to_previous_version_for(LIST_ORDERS, ["GET"])
    def order_list(response: ResponseInfo) -> None:
        for order in orders_in(response.body):
            _customer_to_name(order)


def _customer_to_name(order: dict) -> None:
    order["customer_name"] = order.pop("customer")["name"]


class MoneyBecameDecimalStrings(VersionChange):
    description = (
        "Totals are `{amount, currency}` objects with decimal-string amounts instead of "
        "integer `total_cents`, and each item shows its `unit_price`."
    )
    instructions_to_migrate_to_previous_version = (
        schema(Order).field("total").didnt_exist,
        schema(Order)
        .field("total_cents")
        .existed_as(type=int, info=Field(description="Order total in US cents.", examples=[3048])),
        schema(OrderItem).field("unit_price").didnt_exist,
    )

    @convert_response_to_previous_version_for(Order)
    def order(response: ResponseInfo) -> None:
        _money_to_cents(response.body)

    @convert_response_to_previous_version_for(LIST_ORDERS, ["GET"])
    def order_list(response: ResponseInfo) -> None:
        for order in orders_in(response.body):
            _money_to_cents(order)


def _money_to_cents(order: dict) -> None:
    order["total_cents"] = int(Decimal(order.pop("total")["amount"]) * 100)
    for item in order["items"]:
        item.pop("unit_price")


class QtyRenamedToQuantity(VersionChange):
    description = "Order items spell out `quantity` instead of `qty`."
    instructions_to_migrate_to_previous_version = (
        schema(OrderItem).field("quantity").had(name="qty"),
        schema(CreateOrderItem).field("quantity").had(name="qty"),
    )

    @convert_request_to_next_version_for(CreateOrderRequest)
    def qty_to_quantity(request: RequestInfo) -> None:
        for item in request.body["items"]:
            item["quantity"] = item.pop("qty")

    @convert_response_to_previous_version_for(Order)
    def order(response: ResponseInfo) -> None:
        _quantity_to_qty(response.body)

    @convert_response_to_previous_version_for(LIST_ORDERS, ["GET"])
    def order_list(response: ResponseInfo) -> None:
        for order in orders_in(response.body):
            _quantity_to_qty(order)


def _quantity_to_qty(order: dict) -> None:
    for item in order["items"]:
        item["qty"] = item.pop("quantity")


class ExposedPaidStatus(VersionChange):
    description = (
        "Order `status` can be `paid`. Older clients may switch over status values "
        "exhaustively, so v1 keeps reporting paid orders as `pending`."
    )
    instructions_to_migrate_to_previous_version = (
        schema(Order).field("status").had(type=Literal["pending", "shipped", "cancelled"]),
    )

    @convert_response_to_previous_version_for(Order)
    def order(response: ResponseInfo) -> None:
        _paid_to_pending(response.body)

    @convert_response_to_previous_version_for(LIST_ORDERS, ["GET"])
    def order_list(response: ResponseInfo) -> None:
        for order in orders_in(response.body):
            _paid_to_pending(order)


def _paid_to_pending(order: dict) -> None:
    if order["status"] == "paid":
        order["status"] = "pending"


class AddedCreatedAt(VersionChange):
    description = "Orders include `created_at`."
    # No data migration needed: the v1 model has no `created_at`, so it's dropped
    # when the response is validated against the v1 schema.
    instructions_to_migrate_to_previous_version = (schema(Order).field("created_at").didnt_exist,)


class ListBecamePaginated(VersionChangeWithSideEffects):
    description = (
        "`GET /orders` returns a page `{items, next_cursor}` instead of a bare array "
        "of every order."
    )
    instructions_to_migrate_to_previous_version = (
        endpoint(LIST_ORDERS, ["GET"]).had(response_model=list[Order]),
        schema(ListOrdersParams).field("limit").didnt_exist,
        schema(ListOrdersParams).field("cursor").didnt_exist,
    )

    @convert_response_to_previous_version_for(LIST_ORDERS, ["GET"])
    def page_to_array(response: ResponseInfo) -> None:
        response.body = response.body["items"]


# --------------------------------------------------------------------------- #
# Newest first. Each version lists the changes that it introduced.
# Must match the versions in api-versions.toml (a test checks this).
# --------------------------------------------------------------------------- #
versions = VersionBundle(
    HeadVersion(),
    Version(
        "v2",
        CustomerBecameAnObject,
        MoneyBecameDecimalStrings,
        QtyRenamedToQuantity,
        ExposedPaidStatus,
        AddedCreatedAt,
        ListBecamePaginated,
    ),
    Version("v1"),
)
