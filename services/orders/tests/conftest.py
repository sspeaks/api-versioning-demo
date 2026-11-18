import pytest
from fastapi.testclient import TestClient
from starlette.routing import Mount

from orders.domain.repository import OrderRepository, get_repository
from orders.main import app

# Every mounted version sub-app (/v1, /v2, ...), discovered so new versions need no test plumbing.
VERSION_APPS = [route.app for route in app.routes if isinstance(route, Mount)]


@pytest.fixture
def client():
    """Client for the root app, with a fresh in-memory store per test."""
    repo = OrderRepository()
    for version_app in VERSION_APPS:
        version_app.dependency_overrides[get_repository] = lambda: repo
    with TestClient(app) as c:
        yield c
    for version_app in VERSION_APPS:
        version_app.dependency_overrides.clear()
