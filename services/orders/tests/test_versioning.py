from fastapi import APIRouter

from orders.versioning import inherit_routes


def test_inherit_routes_reuses_everything_not_redefined():
    previous = APIRouter()

    @previous.get("/orders")
    def list_v2(): ...

    @previous.post("/orders")
    def create_v2(): ...

    @previous.get("/orders/{order_id}")
    def get_v2(): ...

    new = APIRouter()

    @new.post("/orders")
    def create_v3(): ...

    inherit_routes(new, previous)

    served = {(r.path, m): r.endpoint.__name__ for r in new.routes for m in r.methods}
    assert served == {
        ("/orders", "GET"): "list_v2",
        ("/orders", "POST"): "create_v3",
        ("/orders/{order_id}", "GET"): "get_v2",
    }
