"""Versioned-API plumbing shared by every version of this service.

Reads ``api-versions.toml`` (the registry that CI also enforces) and builds one
FastAPI sub-application per version. Each version therefore gets its own isolated
OpenAPI document (``/v1/openapi.json``, ``/v2/openapi.json``) and its own docs page.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

# services/orders/api-versions.toml (the service is installed in editable mode by uv).
REGISTRY_PATH = Path(__file__).resolve().parents[2] / "api-versions.toml"

Status = Literal["beta", "stable", "deprecated"]


@dataclass(frozen=True)
class VersionInfo:
    name: str
    status: Status
    sunset: date | None = None
    successor: str | None = None


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, VersionInfo]:
    raw = tomllib.loads(path.read_text())["versions"]
    return {
        name: VersionInfo(
            name=name,
            status=cfg["status"],
            sunset=date.fromisoformat(cfg["sunset"]) if "sunset" in cfg else None,
            successor=cfg.get("successor"),
        )
        for name, cfg in raw.items()
    }


def deprecation_headers(info: VersionInfo) -> dict[str, str]:
    """Headers that tell clients, at runtime, that they are calling a deprecated version.

    * ``Deprecation`` - RFC 9745
    * ``Sunset``      - RFC 8594: the date after which the version may stop responding
    * ``Link``        - points at the successor version's docs
    """
    if info.status != "deprecated":
        return {}
    headers = {"Deprecation": "true"}
    if info.sunset:
        sunset_at = datetime.combine(info.sunset, time(23, 59, 59), tzinfo=timezone.utc)
        headers["Sunset"] = format_datetime(sunset_at, usegmt=True)
    if info.successor:
        headers["Link"] = f'</{info.successor}/docs>; rel="successor-version"'
    return headers


def create_version_app(version: str, *, title: str, description: str) -> FastAPI:
    """Build the FastAPI sub-app for one public API version."""
    info = load_registry()[version]
    lifecycle = f"**Lifecycle:** `{info.status}`"
    if info.sunset:
        lifecycle += f", sunset on **{info.sunset.isoformat()}**"
    if info.successor:
        lifecycle += f", migrate to [`{info.successor}`](/{info.successor}/docs)"

    app = FastAPI(
        title=title,
        version=version,
        description=f"{description}\n\n{lifecycle}",
        # Declaring the mount point makes the exported spec self-describing.
        servers=[{"url": f"/{version}"}],
        redoc_url=None,
    )

    if info.status == "deprecated":
        _mark_spec_deprecated(app, info)
        headers = deprecation_headers(info)

        @app.middleware("http")
        async def add_deprecation_headers(request: Request, call_next):
            response = await call_next(request)
            response.headers.update(headers)
            return response

    return app


def _mark_spec_deprecated(app: FastAPI, info: VersionInfo) -> None:
    """Flag every operation as deprecated in the published OpenAPI document.

    * ``deprecated: true`` makes generated clients warn their users.
    * ``x-sunset`` matters for CI: oasdiff allows removing a deprecated operation
      unless it carries a sunset date, in which case removal before that date is an error.
    """
    generate = app.openapi

    def openapi() -> dict:
        if app.openapi_schema is None:
            schema = generate()
            for path_item in schema.get("paths", {}).values():
                for operation in path_item.values():
                    operation["deprecated"] = True
                    if info.sunset:
                        operation["x-sunset"] = info.sunset.isoformat()
        return app.openapi_schema

    app.openapi = openapi
