"""Internal domain model for orders.

These are plain dataclasses on purpose: they are *not* the API contract.
The public shapes live in ``orders.api.v1.schemas`` and ``orders.api.v2.schemas``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum


class OrderStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"


@dataclass
class Customer:
    id: int
    name: str
    email: str  # PII: deliberately not exposed by any API version


@dataclass
class OrderLine:
    sku: str
    quantity: int
    unit_price: Decimal


@dataclass
class Order:
    id: int
    customer: Customer
    lines: list[OrderLine]
    currency: str
    status: OrderStatus
    created_at: datetime
    # Internal-only bookkeeping. Never leaks into a contract because mappers
    # copy fields explicitly instead of dumping the whole object.
    fraud_score: float = 0.0
    tags: list[str] = field(default_factory=list)
    notes: str | None = None

    @property
    def total(self) -> Decimal:
        return sum((line.unit_price * line.quantity for line in self.lines), Decimal("0"))
