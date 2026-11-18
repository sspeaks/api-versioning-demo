"""In-memory order store with deterministic seed data (good enough for a demo)."""

from __future__ import annotations

from datetime import datetime, timezone

from orders.domain.models import Customer, LineItem, Order, OrderStatus

CATALOG_CENTS: dict[str, int] = {
    "WIDGET-1": 1299,
    "GADGET-7": 450,
    "GIZMO-3": 9900,
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
            if customer.display_name == name:
                return customer
        customer = Customer(
            id=max(self._customers, default=0) + 1,
            display_name=name,
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
        line_items = []
        for sku, quantity in items:
            if sku not in CATALOG_CENTS:
                raise UnknownSku(sku)
            line_items.append(
                LineItem(sku=sku, quantity=quantity, unit_price_cents=CATALOG_CENTS[sku])
            )
        order = Order(
            id=max(self._orders, default=0) + 1,
            customer=customer,
            line_items=line_items,
            currency="USD",
            status=OrderStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
        self._orders[order.id] = order
        return order

    # -- seed data ---------------------------------------------------------
    def _seed(self) -> None:
        ada = Customer(id=1, display_name="Ada Lovelace", email="ada@example.com")
        alan = Customer(id=2, display_name="Alan Turing", email="alan@example.com")
        self._customers = {ada.id: ada, alan.id: alan}
        created = datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc)
        self._orders = {
            1: Order(
                id=1,
                customer=ada,
                line_items=[
                    LineItem("WIDGET-1", 2, CATALOG_CENTS["WIDGET-1"]),
                    LineItem("GADGET-7", 1, CATALOG_CENTS["GADGET-7"]),
                ],
                currency="USD",
                status=OrderStatus.SHIPPED,
                created_at=created,
                fraud_score=0.02,
            ),
            2: Order(
                id=2,
                customer=alan,
                line_items=[LineItem("GIZMO-3", 1, CATALOG_CENTS["GIZMO-3"])],
                currency="USD",
                status=OrderStatus.PAID,
                created_at=created,
                fraud_score=0.4,
                tags=["manual-review"],
            ),
            3: Order(
                id=3,
                customer=ada,
                line_items=[LineItem("GADGET-7", 4, CATALOG_CENTS["GADGET-7"])],
                currency="USD",
                status=OrderStatus.CANCELLED,
                created_at=created,
            ),
        }


_repo = OrderRepository()


def get_repository() -> OrderRepository:
    """FastAPI dependency. Tests override this to get a fresh store."""
    return _repo
