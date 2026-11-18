# Tagged handlers: one set of handlers, tagged with the versions they serve

`main` gives each version its own routes module (`api/v1/routes.py`,
`api/v2/routes.py`). The [Cadwyn branch](https://github.com/sspeaks/api-versioning-demo/tree/alt/single-source-cadwyn)
writes only the latest version and generates the older ones. This branch is the
middle ground, and probably the most common pattern in practice. It's the same idea as
`request.version` in Django REST Framework or `[MapToApiVersion]` in ASP.NET:

* **Contracts stay per version.** `api/v1/schemas.py` and `api/v2/schemas.py` are untouched.
  That's what consumers see, so it's still easy to read.
* **Handlers are shared.** Every endpoint lives once in `api/routes.py`, tagged with the
  versions it serves. Where versions differ, there's an `if`.

```
src/orders/
├── versioned_router.py   # ⭐ the mechanism: ~200 lines of plain FastAPI, no dependency
└── api/
    ├── v1/{schemas,mappers}.py
    ├── v2/{schemas,mappers}.py
    ├── routes.py         # ⭐ every handler, for every version
    └── apps.py           # one app per version: router.for_version("v1"), ...
```

## What it looks like

```python
@router.get(
    "/{order_id}",
    response_model={"v1": v1.Order, "v2": v2.Order},  # tag: what each version returns
    operation_id="getOrder",
)
def get_order(order_id: int, repo: Repo, version: ApiVersion):
    order = repo.get_order(order_id)
    ...
    return order_to_v1(order) if version == "v1" else order_to_v2(order)


@router.get(
    "", response_model={"v1": list[v1.Order], "v2": v2.OrderPage}, operation_id="listOrders"
)
def list_orders(
    repo: Repo,
    version: ApiVersion,
    limit: Annotated[int, Query(ge=1, le=100), since("v2")] = 20,  # tag: v1 has no `limit`
    cursor: Annotated[str | None, Query(), since("v2")] = None,
):
    orders = repo.list_orders()
    if version == "v1":  # v1 isn't paginated
        return [order_to_v1(o) for o in orders]
    ...
```

| Tag | Meaning |
|---|---|
| `since="v2"`, `until="v1"` on a handler | The versions it serves (inclusive). Default: all of them |
| `response_model={"v1": A, "v2": B}` | The model each version publishes, keyed by the first version that uses it. v3 would get `B` too |
| `Annotated[..., since("v3")]` on a parameter | Older versions don't have it: it's absent from their signature *and* their OpenAPI document, and the handler receives its default (or `None`) |
| `version: ApiVersion` | The version being served, for `if` statements |

At startup, `router.for_version("v1")` registers each tagged handler on an ordinary
FastAPI `APIRouter`, with v1's signature and response model. Nothing runs per request,
and each version is still its own app with its own `/vN/docs` and OpenAPI document.

## Proof that it's the same API

This branch deleted `api/v1/routes.py` and `api/v2/routes.py`. The generated
`openapi/v1.json` and `openapi/v2.json` are **byte-for-byte identical** to `main`'s,
and every test passes unchanged (only one test's import moved).

## Making a breaking change

[PR #9](https://github.com/sspeaks/api-versioning-demo/pull/9) ships the same v3 as
`main`'s [PR #6](https://github.com/sspeaks/api-versioning-demo/pull/6): `POST /orders`
requires an `Idempotency-Key` header. Here, that's one tagged parameter on the existing
handler, plus registering v3:

```python
def create_order(
    body: v2.CreateOrderRequest,
    repo: Repo,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8), since("v3")],
): ...
```

v2 doesn't have the parameter, so its contract doesn't change, and the handler gets
`None` for v2 requests. Every other endpoint serves v3 without being touched.

## Retiring a version

Delete its registry entry, its spec, its line in `apps.py` and `api/vN/`, then every
tag and `if` that mentions it. A test (`test_routes_only_mention_versions_that_still_exist`)
fails until `routes.py` no longer mentions the removed version, so nothing is left behind.

## Compared with the other two

| | Separate modules (`main`) | **Tagged handlers (this branch)** | Single source (Cadwyn) |
|---|---|---|---|
| Where differences live | Separate folders | `if`s and tags in each handler | One diff file, `versions.py` |
| "What does v1 look like?" | Read `api/v1/` | Read `api/v1/schemas.py`. For behavior, follow the `v1` branches | Read the latest code and subtract `versions.py` |
| Breaking change | New `api/vN/` with the changed endpoints | Tag the parameter, response or handler that changed | A `VersionChange` class plus request/response migrations |
| Bug fix | Once per version that has its own copy | Once | Once |
| Request body changes shape | New handler in the new folder | A separate handler, tagged `since`/`until` | A request migration |
| Behavior differs, not just shape | Easy | Easy: it's an `if` | Awkward (side-effect flags in handlers) |
| Cost as versions pile up | More folders | **More `if`s per handler**: the main risk | More version changes |
| Dependencies | None | None (~200 lines) | Cadwyn |
| CI gates | Same | Same | Same |

## Which one should we use?

Tagged handlers fit when versions mostly differ in **response shape**, and you want one
place to fix bugs without adopting a framework. Watch the `if` count: if handlers
start to look like `if v1 ... elif v2 ... elif v3`, either retire old versions or move
to separate modules for the endpoints that diverged most. Two habits keep it readable:

* **Branch at the edge.** Use the `if` to choose a schema or mapper, never inside
  business logic.
* **Split on request shape.** When a version changes a request body, give it its own
  handler instead of a union type.
