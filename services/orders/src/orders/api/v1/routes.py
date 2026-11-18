from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from orders.api.deps import Repo
from orders.api.v1 import schemas
from orders.api.v1.mappers import order_to_v1
from orders.domain.repository import UnknownSku

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=list[schemas.Order], operation_id="listOrders")
def list_orders(repo: Repo) -> list[schemas.Order]:
    return [order_to_v1(o) for o in repo.list_orders()]


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
    return order_to_v1(order)


@router.post(
    "",
    response_model=schemas.Order,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": schemas.Error}},
    operation_id="createOrder",
)
def create_order(body: schemas.CreateOrderRequest, repo: Repo) -> schemas.Order:
    customer = repo.get_or_create_customer_by_name(body.customer_name)
    try:
        order = repo.create_order(customer, [(i.sku, i.qty) for i in body.items])
    except UnknownSku as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown sku: {exc}") from None
    return order_to_v1(order)
