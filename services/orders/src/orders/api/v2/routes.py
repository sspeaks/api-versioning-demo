from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from orders.api.deps import Repo
from orders.api.v2 import schemas
from orders.api.v2.mappers import order_to_v2
from orders.domain.repository import UnknownCustomer, UnknownSku

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=schemas.OrderPage, operation_id="listOrders")
def list_orders(
    repo: Repo,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(description="Opaque cursor from a previous page.")] = None,
) -> schemas.OrderPage:
    orders = repo.list_orders()
    start = int(cursor) if cursor and cursor.isdigit() else 0
    page = orders[start : start + limit]
    more = start + limit < len(orders)
    return schemas.OrderPage(
        items=[order_to_v2(o) for o in page],
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
    return order_to_v2(order)


@router.post(
    "",
    response_model=schemas.Order,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": schemas.Error}},
    operation_id="createOrder",
)
def create_order(body: schemas.CreateOrderRequest, repo: Repo) -> schemas.Order:
    try:
        customer = repo.get_customer(body.customer_id)
        order = repo.create_order(customer, [(i.sku, i.quantity) for i in body.items])
    except UnknownCustomer:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown customer_id") from None
    except UnknownSku as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown sku: {exc}") from None
    return order_to_v2(order)
