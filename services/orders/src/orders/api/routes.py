"""Orders endpoints, written ONCE for the latest version.

``{api_version}`` in the path selects the version (``/v1/orders``, ``/v2/orders``).
Cadwyn migrates v1 requests up to the latest shape before they reach these
handlers, and migrates responses back down afterwards, so the handlers never
know which version was called.
"""

from __future__ import annotations

from typing import Annotated

from cadwyn import VersionedAPIRouter
from fastapi import Header, HTTPException, Query, status

from orders.api import schemas
from orders.api.deps import Repo
from orders.api.mappers import order_to_api
from orders.api.versions import ListBecamePaginated
from orders.domain.repository import UnknownCustomer, UnknownSku

router = VersionedAPIRouter(prefix="/{api_version}/orders", tags=["orders"])


@router.get("", response_model=schemas.OrderPage, operation_id="listOrders")
def list_orders(
    repo: Repo, params: Annotated[schemas.ListOrdersParams, Query()]
) -> schemas.OrderPage:
    orders = repo.list_orders()
    limit, cursor = params.limit, params.cursor
    if not ListBecamePaginated.is_applied:  # v1 always returned every order
        limit = len(orders) or 1
    start = int(cursor) if cursor and cursor.isdigit() else 0
    page = orders[start : start + limit]
    more = start + limit < len(orders)
    return schemas.OrderPage(
        items=[order_to_api(o) for o in page],
        next_cursor=str(start + limit) if more else None,
    )


@router.get(
    "/{order_id}",
    response_model=schemas.Order,
    responses={404: {"model": schemas.Error}},
    operation_id="getOrder",
)
def get_order(order_id: int, repo: Repo) -> schemas.Order:
    order = repo.get_order(order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"order {order_id} not found")
    return order_to_api(order)


@router.post(
    "",
    response_model=schemas.Order,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": schemas.Error}},
    operation_id="createOrder",
)
def create_order(
    body: schemas.CreateOrderRequest,
    repo: Repo,
    headers: Annotated[schemas.CreateOrderHeaders, Header()],
) -> schemas.Order:
    try:
        customer = repo.get_customer(body.customer_id)
        order = repo.create_order(
            customer,
            [(i.sku, i.quantity) for i in body.items],
            idempotency_key=headers.idempotency_key,
        )
    except UnknownCustomer:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown customer_id") from None
    except UnknownSku as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown sku: {exc}") from None
    return order_to_api(order)
