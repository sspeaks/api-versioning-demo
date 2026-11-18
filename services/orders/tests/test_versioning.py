import re
from pathlib import Path
from typing import Annotated

import pytest
from fastapi import FastAPI, Query
from fastapi.testclient import TestClient

from orders.api import routes
from orders.versioned_router import ApiVersion, VersionedRouter, since
from orders.versioning import load_registry

router = VersionedRouter()


@router.get("/greeting")
def greet(version: ApiVersion, name: Annotated[str, Query(), since("v2")] = "world"):
    return f"{version}: hello {name}"


@router.post("/things", until="v1")
def create_thing_v1():
    return "v1 handler"


@router.post("/things", since="v2")
def create_thing():
    return "v2+ handler"


def app_for(version: str) -> FastAPI:
    app = FastAPI()
    app.include_router(router.for_version(version))
    return app


def test_tags_choose_the_handler_for_each_version():
    assert TestClient(app_for("v1")).post("/things").json() == "v1 handler"
    assert TestClient(app_for("v2")).post("/things").json() == "v2+ handler"
    assert TestClient(app_for("v3")).post("/things").json() == "v2+ handler"


def test_handler_gets_the_version_and_older_versions_ignore_newer_params():
    params = {"name": "Ada"}
    assert TestClient(app_for("v1")).get("/greeting", params=params).json() == "v1: hello world"
    assert TestClient(app_for("v2")).get("/greeting", params=params).json() == "v2: hello Ada"


def test_tagged_params_only_appear_in_the_versions_that_have_them():
    def documented_params(version):
        operation = app_for(version).openapi()["paths"]["/greeting"]["get"]
        return [p["name"] for p in operation.get("parameters", [])]

    assert documented_params("v1") == []
    assert documented_params("v2") == ["name"]


def test_response_model_applies_from_its_version_onwards():
    r = VersionedRouter()

    @r.get("/x", response_model={"v1": int, "v3": str})
    def x(): ...

    assert [r.for_version(v).routes[0].response_model for v in ("v1", "v2", "v3")] == [
        int,
        int,
        str,
    ]


def test_two_handlers_serving_the_same_endpoint_is_an_error():
    r = VersionedRouter()

    @r.get("/x")
    def old(): ...

    @r.get("/x", since="v2")
    def new(): ...

    r.for_version("v1")  # fine: only `old` serves v1
    with pytest.raises(ValueError, match="both old and new serve v2"):
        r.for_version("v2")


def test_routes_only_mention_versions_that_still_exist():
    """When a version is retired, its tags and `if version == ...` branches must go too.

    Removing v1 from api-versions.toml makes this fail until routes.py stops mentioning it.
    """
    mentioned = set(re.findall(r"""["'](v\d+)["']""", Path(routes.__file__).read_text()))
    assert mentioned <= set(load_registry()), "routes.py still handles a removed version"
