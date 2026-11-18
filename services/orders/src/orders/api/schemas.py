"""Orders API contract: the LATEST version only.

There is no ``v1/schemas.py``. Older versions are generated from these models
by the version changes in ``orders.api.versions``, which describe, one breaking
change at a time, how each older version differed.

Everything here is published in ``openapi/v2.json``; the generated older
shapes are published in ``openapi/v1.json``. CI guards both.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Money(BaseModel):
    amount: str = Field(
        pattern=r"^-?\d+\.\d{2}$",
        description="Decimal amount as a string, to avoid float rounding.",
        examples=["30.48"],
    )
    currency: str = Field(pattern=r"^[A-Z]{3}$", examples=["USD"])


class CustomerRef(BaseModel):
    id: int
    name: str


class OrderItem(BaseModel):
    sku: str = Field(examples=["WIDGET-1"])
    quantity: int = Field(ge=1, examples=[2])
    unit_price: Money


class Order(BaseModel):
    id: int
    customer: CustomerRef
    items: list[OrderItem]
    total: Money
    status: Literal["pending", "paid", "shipped", "cancelled"]
    created_at: datetime


class ListOrdersParams(BaseModel):
    """Query parameters of GET /orders."""

    limit: int = Field(20, ge=1, le=100)
    cursor: str | None = Field(None, description="Opaque cursor from a previous page.")


class OrderPage(BaseModel):
    items: list[Order]
    next_cursor: str | None = Field(
        description="Pass as `cursor` to fetch the next page. null on the last page."
    )


class CreateOrderItem(BaseModel):
    sku: str = Field(examples=["WIDGET-1"])
    quantity: int = Field(ge=1, examples=[2])


class CreateOrderRequest(BaseModel):
    customer_id: int
    items: list[CreateOrderItem] = Field(min_length=1)


class Error(BaseModel):
    detail: str
