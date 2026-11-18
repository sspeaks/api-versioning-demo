"""Tag each handler with the API versions it serves; build one plain router per version.

    router = VersionedRouter(prefix="/orders")

    @router.get("/{order_id}", response_model={"v1": v1.Order, "v2": v2.Order})
    def get_order(order_id: int, version: ApiVersion):
        order = ...
        return order_to_v1(order) if version == "v1" else order_to_v2(order)

    v1_app.include_router(router.for_version("v1"))

The tags (all optional):

* ``since="v2"`` / ``until="v1"`` on a handler: the versions it serves, inclusive.
  Without them, a handler serves every version.
* ``response_model={"v1": A, "v2": B}``: the model each version publishes, keyed by
  the first version that uses it. A later v3 would also publish ``B``.
* ``Annotated[..., since("v3")]`` on a parameter: versions before v3 don't have it.
  Their routes leave it out of the signature, so it's also absent from their OpenAPI
  document, and the handler receives the parameter's default (or ``None``).
* ``version: ApiVersion``: the version being served, for ``if`` statements.

All the work happens once, at startup: ``for_version`` registers each handler on an
ordinary FastAPI ``APIRouter`` with that version's signature and response model.
Nothing extra runs per request.
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, get_args, get_origin, get_type_hints

from fastapi import APIRouter


def version_number(name: str) -> int:
    return int(name.removeprefix("v"))


@dataclass(frozen=True)
class VersionRange:
    since: str | None = None
    until: str | None = None

    def __contains__(self, version: str) -> bool:
        n = version_number(version)
        return (self.since is None or version_number(self.since) <= n) and (
            self.until is None or n <= version_number(self.until)
        )


def since(version: str) -> VersionRange:
    """Parameter tag: the parameter exists from ``version`` onwards."""
    return VersionRange(since=version)


def until(version: str) -> VersionRange:
    """Parameter tag: the parameter exists up to and including ``version``."""
    return VersionRange(until=version)


class _CurrentVersion:
    """Marker: ``for_version`` fills this parameter with the version being served."""


ApiVersion = Annotated[str, _CurrentVersion()]


@dataclass(frozen=True)
class TaggedHandler:
    path: str
    methods: list[str]
    endpoint: Callable[..., Any]
    versions: VersionRange
    response_model: Any
    route_kwargs: dict[str, Any]


class VersionedRouter:
    def __init__(self, **router_kwargs: Any) -> None:
        self.router_kwargs = router_kwargs  # prefix, tags, ... for every version's router
        self.handlers: list[TaggedHandler] = []

    def api_route(
        self,
        path: str,
        *,
        methods: list[str],
        since: str | None = None,
        until: str | None = None,
        response_model: Any = None,
        **route_kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def register(endpoint: Callable[..., Any]) -> Callable[..., Any]:
            self.handlers.append(
                TaggedHandler(
                    path,
                    methods,
                    endpoint,
                    VersionRange(since, until),
                    response_model,
                    route_kwargs,
                )
            )
            return endpoint

        return register

    def get(self, path: str, **kwargs: Any):
        return self.api_route(path, methods=["GET"], **kwargs)

    def post(self, path: str, **kwargs: Any):
        return self.api_route(path, methods=["POST"], **kwargs)

    def put(self, path: str, **kwargs: Any):
        return self.api_route(path, methods=["PUT"], **kwargs)

    def patch(self, path: str, **kwargs: Any):
        return self.api_route(path, methods=["PATCH"], **kwargs)

    def delete(self, path: str, **kwargs: Any):
        return self.api_route(path, methods=["DELETE"], **kwargs)

    def for_version(self, version: str) -> APIRouter:
        """A plain FastAPI router with exactly the routes ``version`` serves."""
        router = APIRouter(**self.router_kwargs)
        served_by: dict[tuple[str, str], str] = {}
        for handler in self.handlers:
            if version not in handler.versions:
                continue
            name = handler.endpoint.__name__
            for method in handler.methods:
                other = served_by.setdefault((method, handler.path), name)
                if other != name:
                    raise ValueError(
                        f"{method} {handler.path}: both {other} and {name} serve {version}. "
                        "Give one of them since=/until= tags."
                    )
            route_kwargs = dict(handler.route_kwargs)
            if handler.response_model is not None:
                route_kwargs["response_model"] = _pick(handler.response_model, version)
            router.add_api_route(
                handler.path,
                _bind(handler.endpoint, version),
                methods=handler.methods,
                **route_kwargs,
            )
        return router


def _pick(models: Any, version: str) -> Any:
    """The entry of ``{"v1": A, "v3": B}`` that applies to ``version``."""
    if not isinstance(models, dict):
        return models
    applicable = [v for v in models if version_number(v) <= version_number(version)]
    if not applicable:
        raise ValueError(f"no response_model for {version} in {sorted(models)}")
    return models[max(applicable, key=version_number)]


def _bind(endpoint: Callable[..., Any], version: str) -> Callable[..., Any]:
    """``endpoint`` as FastAPI should see it in ``version``.

    Parameters that ``version`` doesn't have are removed from the signature and
    supplied by us, as is ``ApiVersion``. Version tags are stripped from the rest.
    """
    hints = get_type_hints(endpoint, include_extras=True)
    signature = inspect.signature(endpoint)
    params: list[inspect.Parameter] = []
    supplied: dict[str, Any] = {}
    for param in signature.parameters.values():
        annotation = hints.get(param.name, param.annotation)
        if get_origin(annotation) is Annotated:
            base, *metadata = get_args(annotation)
        else:
            base, metadata = annotation, []
        tags = [m for m in metadata if isinstance(m, (VersionRange, _CurrentVersion))]
        if any(isinstance(tag, _CurrentVersion) for tag in tags):
            supplied[param.name] = version
        elif any(version not in tag for tag in tags):
            supplied[param.name] = None if param.default is param.empty else param.default
        else:
            rest = [m for m in metadata if not isinstance(m, (VersionRange, _CurrentVersion))]
            params.append(param.replace(annotation=Annotated[(base, *rest)] if rest else base))

    if inspect.iscoroutinefunction(endpoint):

        @functools.wraps(endpoint)
        async def bound(**kwargs: Any) -> Any:
            return await endpoint(**kwargs, **supplied)

    else:

        @functools.wraps(endpoint)
        def bound(**kwargs: Any) -> Any:
            return endpoint(**kwargs, **supplied)

    bound.__signature__ = signature.replace(  # type: ignore[attr-defined]
        parameters=params,
        return_annotation=hints.get("return", signature.return_annotation),
    )
    return bound
