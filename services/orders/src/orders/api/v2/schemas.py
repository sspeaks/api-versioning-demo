"""Orders API v2 - public contract.

v2 exists because these changes could not be made to v1 without breaking callers:

* ``customer_name: str``  -> ``customer: {id, name}``
* ``total_cents: int``    -> ``total: {amount: "12.34", currency: "USD"}``
* list endpoint returns a page object instead of a bare array
* ``status`` gains ``"paid"``
* ``qty`` is spelled ``quantity``

Everything here is published in ``services/orders/openapi/v2.json`` and guarded by CI.
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
    notes: str | None = Field(default=None, description="Delivery notes from the customer.")


class OrderPage(BaseModel):
    items: list[Order]
    next_cursor: str | None = Field(
        description="Pass as `cursor` to fetch the next page. null on the last page."
    )


class CreateOrderItem(BaseModel):
    sku: str
    quantity: int = Field(ge=1)


class CreateOrderRequest(BaseModel):
    customer_id: int
    items: list[CreateOrderItem] = Field(min_length=1)
    notes: str | None = Field(default=None, max_length=500)


class Error(BaseModel):
    detail: str
