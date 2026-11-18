"""One FastAPI app per public API version, all built from the same tagged handlers.

``api-versions.toml`` points at these (``app = "orders.api.apps:v1"``), and
``orders.main`` mounts them at ``/v1``, ``/v2``.
"""

from fastapi import FastAPI

from orders.api.routes import router
from orders.versioning import create_version_app


def version_app(version: str, description: str) -> FastAPI:
    app = create_version_app(version, title="Orders API", description=description)
    app.include_router(router.for_version(version))
    return app


v1 = version_app("v1", "The original orders API. Frozen: additive changes only.")
v2 = version_app("v2", "Current orders API. Structured customer and money types, paginated lists.")
v3 = version_app("v3", "v2, plus required idempotency keys when creating orders.")
