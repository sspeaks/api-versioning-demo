"""In-memory order store with deterministic seed data (good enough for a demo)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from orders.domain.models import Customer, Order, OrderLine, OrderStatus

CATALOG: dict[str, Decimal] = {
    "WIDGET-1": Decimal("12.99"),
    "GADGET-7": Decimal("4.50"),
    "GIZMO-3": Decimal("99.00"),
}


class UnknownSku(ValueError):
    pass


class UnknownCustomer(ValueError):
    pass


class OrderRepository:
    def __init__(self) -> None:
        self._customers: dict[int, Customer] = {}
        self._orders: dict[int, Order] = {}
        self._seed()

    # -- customers ---------------------------------------------------------
    def get_customer(self, customer_id: int) -> Customer:
        try:
            return self._customers[customer_id]
        except KeyError:
            raise UnknownCustomer(customer_id) from None

    def get_or_create_customer_by_name(self, name: str) -> Customer:
        for customer in self._customers.values():
            if customer.name == name:
                return customer
        customer = Customer(
            id=max(self._customers, default=0) + 1,
            name=name,
            email=f"{name.lower().replace(' ', '.')}@example.com",
        )
        self._customers[customer.id] = customer
        return customer

    # -- orders ------------------------------------------------------------
    def list_orders(self) -> list[Order]:
        return [self._orders[k] for k in sorted(self._orders)]

    def get_order(self, order_id: int) -> Order | None:
        return self._orders.get(order_id)

    def create_order(self, customer: Customer, items: list[tuple[str, int]]) -> Order:
        lines = []
        for sku, quantity in items:
            if sku not in CATALOG:
                raise UnknownSku(sku)
            lines.append(OrderLine(sku=sku, quantity=quantity, unit_price=CATALOG[sku]))
        order = Order(
            id=max(self._orders, default=0) + 1,
            customer=customer,
            lines=lines,
            currency="USD",
            status=OrderStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
        self._orders[order.id] = order
        return order

    # -- seed data ---------------------------------------------------------
    def _seed(self) -> None:
        ada = Customer(id=1, name="Ada Lovelace", email="ada@example.com")
        alan = Customer(id=2, name="Alan Turing", email="alan@example.com")
        self._customers = {ada.id: ada, alan.id: alan}
        created = datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc)
        self._orders = {
            1: Order(
                id=1,
                customer=ada,
                lines=[
                    OrderLine("WIDGET-1", 2, CATALOG["WIDGET-1"]),
                    OrderLine("GADGET-7", 1, CATALOG["GADGET-7"]),
                ],
                currency="USD",
                status=OrderStatus.SHIPPED,
                created_at=created,
                fraud_score=0.02,
            ),
            2: Order(
                id=2,
                customer=alan,
                lines=[OrderLine("GIZMO-3", 1, CATALOG["GIZMO-3"])],
                currency="USD",
                status=OrderStatus.PAID,
                created_at=created,
                fraud_score=0.4,
                tags=["manual-review"],
            ),
            3: Order(
                id=3,
                customer=ada,
                lines=[OrderLine("GADGET-7", 4, CATALOG["GADGET-7"])],
                currency="USD",
                status=OrderStatus.CANCELLED,
                created_at=created,
            ),
        }


_repo = OrderRepository()


def get_repository() -> OrderRepository:
    """FastAPI dependency. Tests override this to get a fresh store."""
    return _repo
