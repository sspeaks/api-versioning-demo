"""Orders API v3.

v3 exists for ONE breaking change: ``POST /orders`` now *requires* an
``Idempotency-Key`` header, so a client that retries after a timeout can't create a
duplicate order. Making a header required would break every v2 client, so this
can't ship in v2.

Only that endpoint is defined here. Everything else is v2's code, inherited unchanged:
same handlers, same pydantic schemas, same mappers.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

from orders.api.deps import Repo
from orders.api.v2 import routes as v2_routes
from orders.api.v2 import schemas
from orders.api.v2.mappers import order_to_v2
from orders.domain.repository import UnknownCustomer, UnknownSku
from orders.versioning import inherit_routes

router = APIRouter(prefix="/orders", tags=["orders"])


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
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=8,
            description="Unique per logical order. Retrying with the same key returns "
            "the original order instead of creating a new one.",
        ),
    ],
) -> schemas.Order:
    try:
        customer = repo.get_customer(body.customer_id)
        order = repo.create_order(
            customer,
            [(i.sku, i.quantity) for i in body.items],
            idempotency_key=idempotency_key,
        )
    except UnknownCustomer:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown customer_id") from None
    except UnknownSku as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown sku: {exc}") from None
    return order_to_v2(order)


# Every endpoint not redefined above (GET /orders, GET /orders/{order_id}) is v2's.
inherit_routes(router, v2_routes.router)
