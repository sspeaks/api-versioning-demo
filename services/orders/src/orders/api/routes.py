"""Every orders endpoint, for every API version, in one file.

Each handler is tagged with the versions it serves, and ``for_version`` turns the tags
into a plain FastAPI router per version (see ``orders.versioned_router``):

* ``since=``/``until=`` on a handler: which versions it serves (default: all of them).
* ``response_model={"v1": ..., "v2": ...}``: what each version returns, keyed by the
  first version that returns it.
* ``Annotated[..., since("v2")]`` on a parameter: older versions don't have it.
* ``version: ApiVersion``: the version being served, for ``if`` statements.

The contracts are still one module per version (``api/v1/schemas.py``,
``api/v2/schemas.py``), because that's what consumers see. Only the handlers are shared.

Rules of thumb:

* Branch at the edge, to pick a schema or a mapper. Never in business logic.
* When a version changes the shape of a *request body*, write a separate handler and
  tag both.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import HTTPException, Query, status

from orders.api.deps import Repo
from orders.api.v1 import schemas as v1
from orders.api.v1.mappers import order_to_v1
from orders.api.v2 import schemas as v2
from orders.api.v2.mappers import order_to_v2
from orders.domain.repository import UnknownCustomer, UnknownSku
from orders.versioned_router import ApiVersion, VersionedRouter, since

router = VersionedRouter(prefix="/orders", tags=["orders"])


@router.get(
    "",
    response_model={"v1": list[v1.Order], "v2": v2.OrderPage},
    operation_id="listOrders",
)
def list_orders(
    repo: Repo,
    version: ApiVersion,
    limit: Annotated[int, Query(ge=1, le=100), since("v2")] = 20,
    cursor: Annotated[
        str | None, Query(description="Opaque cursor from a previous page."), since("v2")
    ] = None,
):
    orders = repo.list_orders()
    if version == "v1":  # v1 isn't paginated: a bare array of every order
        return [order_to_v1(o) for o in orders]
    start = int(cursor) if cursor and cursor.isdigit() else 0
    page = orders[start : start + limit]
    more = start + limit < len(orders)
    return v2.OrderPage(
        items=[order_to_v2(o) for o in page],
        next_cursor=str(start + limit) if more else None,
    )


@router.get(
    "/{order_id}",
    response_model={"v1": v1.Order, "v2": v2.Order},
    responses={404: {"model": v2.Error}},  # Error is the same in every version
    operation_id="getOrder",
)
def get_order(order_id: int, repo: Repo, version: ApiVersion):
    order = repo.get_order(order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"order {order_id} not found")
    return order_to_v1(order) if version == "v1" else order_to_v2(order)


# v2 changed the request body (customer_name -> customer_id, qty -> quantity), so
# creating an order has one handler per request shape.
@router.post(
    "",
    until="v1",
    response_model=v1.Order,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": v1.Error}},
    operation_id="createOrder",
    summary="Create Order",  # otherwise FastAPI derives "Create Order V1" from the name
)
def create_order_v1(body: v1.CreateOrderRequest, repo: Repo):
    customer = repo.get_or_create_customer_by_name(body.customer_name)
    try:
        order = repo.create_order(customer, [(i.sku, i.qty) for i in body.items])
    except UnknownSku as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown sku: {exc}") from None
    return order_to_v1(order)


@router.post(
    "",
    since="v2",
    response_model=v2.Order,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": v2.Error}},
    operation_id="createOrder",
)
def create_order(body: v2.CreateOrderRequest, repo: Repo):
    try:
        customer = repo.get_customer(body.customer_id)
        order = repo.create_order(customer, [(i.sku, i.quantity) for i in body.items])
    except UnknownCustomer:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown customer_id") from None
    except UnknownSku as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown sku: {exc}") from None
    return order_to_v2(order)
