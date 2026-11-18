"""Translate internal domain objects into the v2 contract."""

from __future__ import annotations

from decimal import Decimal

from orders.api.v2 import schemas
from orders.domain.models import Order


def money(cents: int, currency: str) -> schemas.Money:
    return schemas.Money(amount=f"{Decimal(cents) / 100:.2f}", currency=currency)


def order_to_v2(order: Order) -> schemas.Order:
    return schemas.Order(
        id=order.id,
        customer=schemas.CustomerRef(id=order.customer.id, name=order.customer.display_name),
        items=[
            schemas.OrderItem(
                sku=item.sku,
                quantity=item.quantity,
                unit_price=money(item.unit_price_cents, order.currency),
            )
            for item in order.line_items
        ],
        total=money(order.total_cents, order.currency),
        status=order.status.value,
        created_at=order.created_at,
    )
