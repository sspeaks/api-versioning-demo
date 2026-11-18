"""Orders API v1 - public contract.

Everything in this module is published in ``services/orders/openapi/v1.json``.
Changing it is a contract change and is checked by CI:

* adding an optional response field or a new endpoint  -> fine
* renaming/removing a field, changing a type, making a request
  field required, removing an enum value               -> blocked
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class OrderItem(BaseModel):
    sku: str = Field(examples=["WIDGET-1"])
    qty: int = Field(ge=1, examples=[2])


class Order(BaseModel):
    id: int
    customer_name: str
    items: list[OrderItem]
    total_cents: int = Field(description="Order total in US cents.", examples=[3048])
    status: Literal["pending", "shipped", "cancelled"]


class CreateOrderRequest(BaseModel):
    customer_name: str = Field(min_length=1)
    items: list[OrderItem] = Field(min_length=1)


class Error(BaseModel):
    detail: str
