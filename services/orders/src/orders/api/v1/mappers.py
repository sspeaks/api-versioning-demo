"""Translate internal domain objects into the v1 contract.

This is the seam that lets the domain evolve without breaking v1 consumers.
Copy fields explicitly; never ``model_validate(domain_obj)`` the whole thing.
"""

from __future__ import annotations

from orders.api.v1 import schemas
from orders.domain.models import Order, OrderStatus

# v1 predates the "paid" state. Adding a new value to a response enum breaks
# clients that switch over it exhaustively, so v1 keeps reporting "pending".
_STATUS = {
    OrderStatus.PENDING: "pending",
    OrderStatus.PAID: "pending",
    OrderStatus.SHIPPED: "shipped",
    OrderStatus.CANCELLED: "cancelled",
}


def order_to_v1(order: Order) -> schemas.Order:
    return schemas.Order(
        id=order.id,
        customer_name=order.customer.name,
        items=[schemas.OrderItem(sku=line.sku, qty=line.quantity) for line in order.lines],
        total_cents=int(order.total),
        status=_STATUS[order.status],
    )
