import pytest
from fastapi.testclient import TestClient

from orders.api import v1, v2
from orders.domain.repository import OrderRepository, get_repository
from orders.main import app


@pytest.fixture
def client():
    """Client for the root app, with a fresh in-memory store per test."""
    repo = OrderRepository()
    for version_app in (v1.app, v2.app):
        version_app.dependency_overrides[get_repository] = lambda: repo
    with TestClient(app) as c:
        yield c
    for version_app in (v1.app, v2.app):
        version_app.dependency_overrides.clear()
