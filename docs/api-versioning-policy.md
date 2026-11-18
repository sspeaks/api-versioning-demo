# API versioning policy

> **TL;DR:** Once a version is `stable`, its contract can grow but never break.
> If you need to break it, ship a new version next to it and give consumers time to move.

## Why

In the monorepo, any team can change any code at any time, which is great for us.
It is terrible for anyone who *calls* our services: a field rename in a Python
model quietly breaks a partner integration, a mobile app, or another team's job.

Versioning separates **how fast we change internals** from **how fast consumers
must change**.

## How a service declares its API

```
services/<svc>/
├── api-versions.toml          # registry: which versions exist + lifecycle status
├── openapi/v1.json            # the contract, generated from code and committed
├── openapi/v2.json
└── src/<svc>/
    ├── domain/                # internal: change freely
    └── api/
        ├── schemas.py         # pydantic models = the LATEST contract
        ├── mappers.py         # domain -> latest contract (absorbs internal churn)
        ├── routes.py          # endpoints, written once: /{api_version}/orders
        └── versions.py        # every difference between versions (Cadwyn version changes)
```

* One [Cadwyn](https://github.com/zmievsa/cadwyn) app serves every version at its own
  prefix (`/v1`, `/v2`). Each version still gets its own OpenAPI document.
* Contract models (`api/schemas.py`) are **separate from** domain models.
  Never return a domain object or ORM model directly; map it explicitly.
* The committed `openapi/*.json` is the contract. Review it like code.

## Version lifecycle

| status | Who can rely on it | What may change | Removal |
|---|---|---|---|
| `beta` | Early adopters who accept churn | Anything | Any time |
| `stable` | Everyone | **Additive only** | Never directly; deprecate first |
| `deprecated` | Existing consumers, until `sunset` | **Additive only** (frozen like stable) | Only after `sunset` |

Rules (enforced by CI, using the **base branch's** registry):

1. `stable` and `deprecated` versions may not have breaking changes.
2. A version may not go from `stable`/`deprecated` back to `beta`.
3. `deprecated` requires a `sunset` date at least **90 days** out when it's set.
4. A `sunset` date may be pushed later, never earlier.
5. A `stable` version can't be deleted. A `deprecated` one can be deleted only after its `sunset`.

Deprecated versions automatically:
* mark every operation `deprecated: true` with an `x-sunset` date in their OpenAPI spec
  (generated clients show warnings, and oasdiff refuses to let endpoints disappear early)
* return `Deprecation`, `Sunset` and `Link: <...>; rel="successor-version"` headers on every response

## What counts as breaking?

The CI gate uses [oasdiff](https://github.com/oasdiff/oasdiff) (300+ rules). The common cases:

| ✅ Non-breaking (additive) | ❌ Breaking |
|---|---|
| Add a new endpoint | Remove or rename an endpoint |
| Add an **optional** request field | Add a **required** request field |
| Add a response field | Remove or rename a response field |
| Relax validation (e.g. raise `max_length`) | Tighten validation (e.g. lower `max_length`) |
| Add a new error response code | Change a field's type (`int` → `str`) |
| | Remove an enum value from a request |
| ⚠️ Add an enum value to a **response** (warning: clients with exhaustive `switch`es break) | Make an optional response field nullable |

And one category no schema tool can see: **semantic changes**. Same shape, different
meaning, e.g. `total_cents` starts returning dollars. These are caught by the
consumer golden tests in `services/<svc>/tests/consumers/`.

## How to...

**...add a field or endpoint**
Change `schemas.py`/`routes.py`, run `make openapi`, commit the updated specs. CI
posts the changelog on your PR, and CODEOWNERS pulls in an API owner.
Additions reach **every** version by default. If an older version shouldn't get it,
add `schema(Model).field("x").didnt_exist` to a version change.

**...refactor internals**
Change `domain/` freely and update the mappers. If `make openapi` produces no diff
and the golden tests pass, consumers can't tell anything changed.

**...make a breaking change**
1. Make the change in the latest `schemas.py`/`routes.py`. Then, in `versions.py`, write
   a `VersionChange` that describes how to go *back*: what the old contract looked like,
   plus the request and response migrations between the shapes. List it under a new
   `Version("vN+1", ...)` and register `vN+1` in `api-versions.toml` as `beta`.
   See [docs/single-source-versioning.md](single-source-versioning.md), and
   [demo PR #8](https://github.com/sspeaks/api-versioning-demo/pull/8) for a whole v3 this way.
2. Iterate while it's `beta`; breaking changes are allowed.
3. Promote it to `stable` when consumers are ready to adopt it.
4. Mark the old version `deprecated` with a `sunset` date at least 90 days out.
5. After the sunset date, delete `Version("vN")`, the version changes that only
   existed to describe it, its spec, and its registry entry.

**...break a stable version anyway (emergency only)**
For example, a security fix that cannot be made additive. Get API-owner sign-off,
add the `api-breaking-change-approved` label to the PR, and notify consumers. The gate
then reports the break but doesn't block the merge.

## Day-to-day commands

```bash
make openapi      # regenerate contracts after changing an API
make check        # lint + tests + drift + breaking (vs main), same as CI
make breaking BASE=origin/main
make changelog BASE=origin/main
```
