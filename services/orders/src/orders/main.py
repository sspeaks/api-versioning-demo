"""The whole versioned API is ONE Cadwyn app.

    /v1/orders, /v2/orders     (docs at /docs, with a version switcher)

Routes and schemas exist once, in the latest shape (orders.api.routes, orders.api.schemas).
Cadwyn generates v1 from the differences described in orders.api.versions.

Run with:  uv run uvicorn orders.main:app --reload
"""

from cadwyn import Cadwyn
from fastapi import Request

from orders.api.routes import router
from orders.api.versions import versions
from orders.versioning import (
    deprecated_operation_fields,
    deprecation_headers,
    lifecycle_description,
    load_registry,
)

REGISTRY = load_registry()


def customize_openapi(spec: dict, version: str | None) -> dict:
    """Publish each version as a standalone contract, as consumers see it.

    Cadwyn documents paths as ``/{api_version}/orders`` with a version parameter.
    For a single-version document that's just noise, so publish ``/orders`` under
    the server ``/v1`` instead: same URLs, and the same layout as any other spec.
    """
    info = REGISTRY.get(version or "")
    if info is None:
        return spec
    prefix = "/{api_version}"
    spec["servers"] = [{"url": f"/{version}"}]
    spec["info"]["version"] = version
    spec["info"]["description"] = lifecycle_description(info)
    spec["paths"] = {
        path.removeprefix(prefix) or "/": path_item for path, path_item in spec["paths"].items()
    }
    for path_item in spec["paths"].values():
        for operation in path_item.values():
            operation["parameters"] = [
                p for p in operation.get("parameters", []) if p["name"] != "api_version"
            ]
            if not operation["parameters"]:
                del operation["parameters"]
            operation.update(deprecated_operation_fields(info))
    return spec


app = Cadwyn(
    versions=versions,
    title="Orders API",
    api_version_location="path",
    api_version_format="string",
    api_version_parameter_name="api_version",
    openapi_customizer=customize_openapi,
)
app.generate_and_include_versioned_routers(router)

_HEADERS = {name: deprecation_headers(info) for name, info in REGISTRY.items()}


@app.middleware("http")
async def add_deprecation_headers(request: Request, call_next):
    response = await call_next(request)
    version = request.url.path.split("/")[1]
    response.headers.update(_HEADERS.get(version, {}))
    return response
