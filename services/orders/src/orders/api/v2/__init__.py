"""Orders API v2 (stable - see api-versions.toml)."""

from orders.api.v2.routes import router
from orders.versioning import create_version_app

app = create_version_app(
    "v2",
    title="Orders API",
    description="Current orders API. Structured customer and money types, paginated lists.",
)
app.include_router(router)
