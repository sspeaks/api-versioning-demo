import pytest
from fastapi.testclient import TestClient

from orders.domain import repository
from orders.main import app


@pytest.fixture
def client(monkeypatch):
    """Client for the app, with a fresh in-memory store per test.

    Patches the module-level store instead of using dependency_overrides, because
    v1's request migration (orders.api.versions) also looks customers up in it.
    """
    monkeypatch.setattr(repository, "_repo", repository.OrderRepository())
    with TestClient(app) as c:
        yield c
