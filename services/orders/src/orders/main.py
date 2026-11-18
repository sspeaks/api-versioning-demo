"""Root ASGI app: mounts every public API version listed in api-versions.toml.

    /v1/...  -> orders.api.v1:app   (docs at /v1/docs)
    /v2/...  -> orders.api.v2:app   (docs at /v2/docs)

Adding a version means adding a registry entry and a package. This file doesn't change.

Run with:  uv run uvicorn orders.main:app --reload
"""

from importlib import import_module

from fastapi import FastAPI

from orders.versioning import load_registry

REGISTRY = load_registry()

app = FastAPI(title="Orders service", docs_url=None, redoc_url=None, openapi_url=None)
for name, info in REGISTRY.items():
    module_name, _, attr = info.app.partition(":")
    app.mount(f"/{name}", getattr(import_module(module_name), attr))


@app.get("/", include_in_schema=False)
def index() -> dict:
    return {
        "versions": {
            name: {
                "status": info.status,
                "sunset": info.sunset.isoformat() if info.sunset else None,
                "docs": f"/{name}/docs",
            }
            for name, info in REGISTRY.items()
        }
    }
