"""Lifecycle plumbing shared by every version of this service.

Reads ``api-versions.toml`` (the registry that CI also enforces). The versions
themselves, and how they differ, are defined in ``orders.api.versions``.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Literal

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
    app: str  # import path of the version's FastAPI app, e.g. "orders.api.v1:app"
    status: Status
    sunset: date | None = None
    successor: str | None = None


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, VersionInfo]:
    raw = tomllib.loads(path.read_text())["versions"]
    return {
        name: VersionInfo(
            name=name,
            app=cfg["app"],
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
        headers["Link"] = f'</docs?version={info.successor}>; rel="successor-version"'
    return headers


def deprecated_operation_fields(info: VersionInfo) -> dict:
    """OpenAPI fields added to every operation of a deprecated version.

    * ``deprecated: true`` makes generated clients warn their users.
    * ``x-sunset`` matters for CI: oasdiff allows removing a deprecated operation
      unless it carries a sunset date, in which case removal before that date is an error.
    """
    if info.status != "deprecated":
        return {}
    fields: dict = {"deprecated": True}
    if info.sunset:
        fields["x-sunset"] = info.sunset.isoformat()
    return fields


def lifecycle_description(info: VersionInfo) -> str:
    text = f"**Lifecycle:** `{info.status}`"
    if info.sunset:
        text += f", sunset on **{info.sunset.isoformat()}**"
    if info.successor:
        text += f", migrate to [`{info.successor}`](/docs?version={info.successor})"
    return text
