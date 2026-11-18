"""Orders API v1 (deprecated - see api-versions.toml)."""

from orders.api.v1.routes import router
from orders.versioning import create_version_app

app = create_version_app(
    "v1",
    title="Orders API",
    description="The original orders API. Frozen: additive changes only.",
)
app.include_router(router)
