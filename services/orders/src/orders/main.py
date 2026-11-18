"""Root ASGI app: mounts every public API version under its own prefix.

    /v1/...  -> orders.api.v1.app   (docs at /v1/docs)
    /v2/...  -> orders.api.v2.app   (docs at /v2/docs)

Run with:  uv run uvicorn orders.main:app --reload
"""

from fastapi import FastAPI

from orders.api import v1, v2
from orders.versioning import load_registry

app = FastAPI(title="Orders service", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/v1", v1.app)
app.mount("/v2", v2.app)


@app.get("/", include_in_schema=False)
def index() -> dict:
    return {
        "versions": {
            name: {
                "status": info.status,
                "sunset": info.sunset.isoformat() if info.sunset else None,
                "docs": f"/{name}/docs",
            }
            for name, info in load_registry().items()
        }
    }
