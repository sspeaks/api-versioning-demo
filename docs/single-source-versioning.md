# Single-source versioning: every version from one set of files

`main` keeps a thin, separate layer per version (`api/v1/`, `api/v2/`). This branch
serves **the same v1 and v2 APIs** with no per-version code at all:

```
src/orders/api/
├── schemas.py    # pydantic models: the LATEST contract only
├── mappers.py    # domain -> latest contract
├── routes.py     # endpoints, written once:  /{api_version}/orders
└── versions.py   # ⭐ every difference between versions, one class per breaking change
```

It uses [Cadwyn](https://github.com/zmievsa/cadwyn), which implements
[Stripe's approach](https://stripe.com/blog/api-versioning): write the newest API,
then describe each older version as a set of changes *backwards* from it, much
like a chain of git diffs.

## What a version change looks like

```python
class QtyRenamedToQuantity(VersionChange):
    description = "Order items spell out `quantity` instead of `qty`."

    # 1. How the CONTRACT differed. Cadwyn generates v1's models and OpenAPI from this.
    instructions_to_migrate_to_previous_version = (
        schema(OrderItem).field("quantity").had(name="qty"),
        schema(CreateOrderItem).field("quantity").had(name="qty"),
    )

    # 2. How to upgrade a v1 request so the (latest-only) handler can process it.
    @convert_request_to_next_version_for(CreateOrderRequest)
    def qty_to_quantity(request: RequestInfo) -> None:
        for item in request.body["items"]:
            item["quantity"] = item.pop("qty")

    # 3. How to downgrade the handler's (latest) response for a v1 client.
    @convert_response_to_previous_version_for(Order)
    def order(response: ResponseInfo) -> None:
        for item in response.body["items"]:
            item["qty"] = item.pop("quantity")
```

The versions are then declared in one place, newest first:

```python
versions = VersionBundle(
    HeadVersion(),
    Version(
        "v2",
        CustomerBecameAnObject,
        MoneyBecameDecimalStrings,
        QtyRenamedToQuantity,
        ExposedPaidStatus,
        AddedCreatedAt,
        ListBecamePaginated,
    ),
    Version("v1"),
)
```

The v1 → v2 redesign from `main` becomes **six small, named changes**, each with a
description. Together they form a changelog of the API that lives in the code.

## Proof that it's the same API

This branch **deleted** `api/v1/` and `api/v2/`, and the CI gates still pass against `main`:

* **Breaking-change gate:** compared with `main`'s committed contracts, the generated v1 and v2
  have **no breaking changes**. v2 has no reported differences at all. v1 gains one
  harmless documented `422` response on `GET /orders`.
* **Tests:** every v1 and v2 test from `main` passes unchanged, including the
  consumer golden tests (`tests/consumers/`).
* **Deprecation:** v1 still carries `Deprecation`/`Sunset` headers and `deprecated` + `x-sunset` in its spec.

The CI tooling needed one generic addition: `api-versions.toml` can say where a
version's spec is served (`openapi_url = "/openapi.json?version=v1"`), because one app
now serves every version.

## Day to day

| Task | `main` (separate modules) | This branch (single source) |
|---|---|---|
| Add an optional field | Edit `api/v2/schemas.py`. Only v2 gets it | Edit `api/schemas.py`. **Every** version gets it, unless a version change says `.didnt_exist` |
| Breaking change | New `api/v3/` with the changed endpoints (+ `inherit_routes`), see [PR #6](https://github.com/sspeaks/api-versioning-demo/pull/6) | Edit the latest code, then add one `VersionChange` describing how v2 differed |
| Fix a bug | Fix it in each version's handler that has it | Fix it once; every version gets the fix |
| Delete a version after sunset | Delete `api/v1/` | Delete `Version("v1")` and the changes that describe it |
| Refactor internals | Update each version's mapper | Update the one mapper |

## Trade-offs

| | Separate modules (`main`) | Single source (this branch) |
|---|---|---|
| Duplication | A thin layer per version | None |
| "What does v1 look like?" | Read `api/v1/`. It's plain FastAPI | Read the latest code and *subtract* `versions.py`, or read `openapi/v1.json` |
| Versions you can afford | A few at a time | Many (Stripe keeps years of versions) |
| Versions that differ in **behavior**, not just shape | Easy: each handler does what it wants | Awkward. v1's `customer_name` needed a DB lookup inside a migration, and v1's "return every order" needed a [`VersionChangeWithSideEffects`](https://docs.cadwyn.dev/concepts/version_changes/#version-changes-with-side-effects) check in the handler |
| Lists and nested objects | Nothing special | Schema migrations only run for the top-level response, so each change also migrates the orders inside `GET /orders` |
| New fields leak into old versions | Never (opt-in per version) | By default (opt-out per version) |
| Dependencies | Plain FastAPI | Cadwyn: an active project, but a framework to learn and upgrade (9.0 had a long list of breaking changes) |
| CI enforcement | Same gates | Same gates |

## Which one should we use?

* **Start with separate modules** (`main`) if breaking changes are rare and you expect
  one or two live versions. It's plain FastAPI, anyone can read it, and `inherit_routes`
  keeps new versions small.
* **Move to single source** when you're making breaking changes often, need to keep
  many versions alive, or keep copying the same bug fix into several versions.

You can switch later without consumers noticing. This branch is the proof: the CI
gates show that the published contracts don't break.
