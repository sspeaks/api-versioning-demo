"""Translate internal domain objects into the v2 contract."""

from __future__ import annotations

from decimal import Decimal

from orders.api.v2 import schemas
from orders.domain.models import Order


def money(amount: Decimal, currency: str) -> schemas.Money:
    return schemas.Money(amount=f"{amount:.2f}", currency=currency)


def order_to_v2(order: Order) -> schemas.Order:
    return schemas.Order(
        id=order.id,
        customer=schemas.CustomerRef(id=order.customer.id, name=order.customer.name),
        items=[
            schemas.OrderItem(
                sku=line.sku,
                quantity=line.quantity,
                unit_price=money(line.unit_price, order.currency),
            )
            for line in order.lines
        ],
        total=money(order.total, order.currency),
        status=order.status.value,
        created_at=order.created_at,
        notes=order.notes,
    )
