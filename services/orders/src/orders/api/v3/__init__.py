"""Orders API v3 (beta - see api-versions.toml)."""

from orders.api.v3.routes import router
from orders.versioning import create_version_app

app = create_version_app(
    "v3",
    title="Orders API",
    description="v2, plus required idempotency keys when creating orders.",
)
app.include_router(router)
