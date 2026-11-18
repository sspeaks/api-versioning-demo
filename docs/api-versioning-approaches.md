# API versioning approaches: which ones cost the least engineering speed

> Researched 2026-11-17. 22 sources were fetched and 25 claims were checked by three
> independent verifiers each: 20 confirmed, 5 refuted (listed at the end).
> **How much to trust this:** nearly every source is a company describing its own practice
> (Stripe, GitHub, Azure, Google, Zalando, the Cadwyn and oasdiff projects). **None of
> them measures engineering speed** (PR cycle time, review hours, CI minutes), and none
> compares approaches head to head. The speed rankings below are qualitative judgments
> built on verified facts.

## TL;DR

Most changes should never need a new version. The cheapest strategy has layers:

1. **Evolve additively, in place**, and make clients ignore fields they don't know. This is the common baseline at Zalando, GitHub, Google and Stripe.
2. **Let CI enforce it** (committed OpenAPI spec + `oasdiff`), so reviewers don't have to catch breakage by eye.
3. **Signal removals at runtime** with `Deprecation` (RFC 9745) and `Sunset` (RFC 8594) headers.
4. **For a breaking change that can't be avoided**, first try a new field or resource. If breaking changes will keep coming for external consumers, use **date versions chosen by a request header, with a transformation layer** (Stripe, GitHub; Cadwyn for FastAPI).

This repo already does 1–3 (see the [README](../README.md)).

## Approaches compared

| Approach | Velocity cost | Concurrent versions | Who does it | Confidence |
|---|---|---|---|---|
| Additive evolution + tolerant reader | Lowest: discipline only | 1 | Zalando, GitHub, Google, Stripe | High |
| CI breaking-change detection (oasdiff) | Low; replaces manual review | n/a (enabler) | oasdiff docs | High |
| Deprecation + Sunset headers | Low | n/a (signal) | IETF RFC 9745, 8594 | High |
| New resource / endpoint instead of a version | Low to medium | 1 (+ old resource) | Zalando (preferred) | High |
| Header date versions, new version only on breaks | Medium | ~2, with a 24-month overlap | GitHub | High |
| Date versions + transformation layer | Medium upfront, low per change | Dozens, kept indefinitely | Stripe; Cadwyn (FastAPI) | High (Stripe), Medium (Cadwyn) |
| Channels (alpha/beta/stable) + dated interface versions | Medium | 1 per channel; pinned dates | Google AIP-185 | High |
| Strict date `api-version` for *every* behavior change | Highest for producers | Many, ~3 years each | Azure | High |
| Media-type versioning | Medium | Few | Zalando (only allowed form) | High |
| URL path versions (`/v1`, `/v2`) | Medium to high (copies) | Few | **Prohibited by Zalando** | High |
| Consumer-driven contract tests (Pact) | Medium (own CI friction) | n/a | GOV.UK Pay (2019) | Medium |

## The approaches

### 1. Versionless, additive evolution (the default)
Ship backward-compatible changes in place, with no version bump. Zalando rule 106: *"Change APIs, but keep all consumers running."* Rule 108 requires clients to be **tolerant readers** that ignore unknown fields and accept new values of *extensible* enums. Rule 109 is the server-side counterpart: servers should reject unknown input fields. GitHub ships non-breaking changes "every single day" to all versions. Google's stability channels "receive new features and updates in-place". Since 2024, Stripe ships monthly releases with no breaking changes and saves breaking changes for twice-yearly major releases.
**Cost:** discipline only. You can't rename or re-type a field in place, and you can't add values to output enums that weren't declared extensible.
Sources: [Zalando][zalando], [GitHub blog][gh-blog], [AIP-185][aip185], [Stripe release process][stripe-release]

### 2. Automated breaking-change detection in CI
`oasdiff` fails the build on definite breaking OpenAPI changes, and enforces deprecate-then-remove (expand/contract) with configurable grace periods. It's **what keeps approach 1 cheap**: reviewers no longer have to spot breakage by eye. (This repo goes further and blocks removals before the `x-sunset` date.)
Sources: [oasdiff breaking changes][oasdiff-bc], [oasdiff deprecation][oasdiff-dep]

### 3. Deprecation and Sunset signaling
RFC 9745 `Deprecation` (IETF Standards Track, March 2025) plus RFC 8594 `Sunset` give a cheap, non-breaking, machine-readable signal at runtime, instead of relying only on docs or email. It's a hint; clients shouldn't depend on it.
Sources: [RFC 9745][rfc9745], [RFC 8594][rfc8594]

### 4. Avoid versioning: add a new resource or endpoint
Zalando ranks the options for an unavoidable break: (1) a new resource variant, (2) a new service endpoint, (3) only as a last resort, a parallel version. *"Multiple versions can significantly complicate understanding, testing, maintaining, evolving, operating and releasing our systems."*
Source: [Zalando rule 113][zalando]

### 5. URL path versions (`/v1`, `/v2`)
**Zalando prohibits this** (rule 115): *"The consumer has to wait until the provider has been released and deployed"*. It couples consumer releases to provider deploys and complicates hypermedia links. This is one organization's policy, not a measured result. (`main` in this repo uses path versions because they're the easiest to *demonstrate*; see [PR #6](https://github.com/sspeaks/api-versioning-demo/pull/6) for keeping them cheap.)

### 6. Media-type versioning
Zalando's only allowed form, used when versioning is unavoidable: `application/x.zalando.cart+json;version=2` via `Accept`/`Content-Type`, with `Vary: Content-Type`. *"Until an incompatible change is necessary … stay with the standard application/json media type without versioning."*
Source: [Zalando rule 114][zalando]

### 7. Header date versions, new versions only for breaking changes (GitHub)
Clients send `X-GitHub-Api-Version: 2022-11-28`. New versions are cut **only for breaking changes**. The first version was **identical to the unversioned API** and is the default when the header is missing, so adopting versioning broke nobody. Each previous version gets **at least 24 months** of support. The second version, `2026-03-10`, shipped in March 2026.
**Why it's cheap:** this is the lowest-ceremony way to add versioning to an API that has none.
Sources: [GitHub blog][gh-blog], [GitHub docs][gh-docs], [GitHub changelog][gh-2026]

### 8. Date versions + a backward transformation layer (Stripe; Cadwyn)
Each account is pinned to a date version on its first request, and a header can override it for a single request. Responses are always built at the **current** version, then passed backward through small per-change modules until they reach the caller's version. Stripe reports **almost 100 breaking changes from 2011 to 2017**, with compatibility kept for every version since 2011. (That architecture post is from 2017. Stripe's external release model changed in 2024, but no public source says the transform mechanism was replaced. The per-request override doesn't apply to webhooks.)
**Cadwyn** brings this to FastAPI. Older versions are derived from the latest code, so features and fixes reach them automatically.
**Refuted claims (don't repeat them):** that Cadwyn needs *no* duplicated code, and that business logic stays *fully* version-unaware. Our [`alt/single-source-cadwyn`](https://github.com/sspeaks/api-versioning-demo/tree/alt/single-source-cadwyn) branch found the same thing: it needed a version check in a handler and a lookup inside a conversion.
Sources: [Stripe versioning][stripe-ver], [Stripe docs][stripe-docs], [brandur.org][brandur], [Cadwyn][cadwyn]

### 9. Channels and interface-based versions (Google AIP-185)
At most one long-lived alpha, beta and stable channel per major version, each updated in place. AIP-185 now also defines interface-based versioning: dated stable versions sent in the `X-Goog-Api-Version` header or a `$apiVersion` query parameter, time-bound previews, and support for all published versions. That section is very new (Aug 2026). The goal is that producers iterate fast while consumers pin.
Source: [AIP-185][aip185]

### 10. Strict per-change date versions (Azure)
A required `api-version=YYYY-MM-DD` (usually a query parameter, with `-preview` for previews). **Any** behavior change needs a new version, not only breaking ones. Breaking changes to GA APIs are strongly discouraged and usually come with about 3 years to migrate. Consumers get maximum stability, and producers pay the most in versions and review.
Sources: [Azure SDK blog][azure-blog], [Azure versioning policy][azure-policy], [Azure guidelines][azure-guide]

### 11. Consumer-driven contract testing (Pact)
Pact can replace slow full-system end-to-end tests, but the only verified case study (GOV.UK Pay, 2019) hit a **circular deploy dependency** between consumer and provider. They worked around it by running provider verification 4 times per build. Newer Pact features (branches, environments, pending and WIP pacts) were designed to remove that blocking. This repo's lighter alternative is consumer golden tests (`tests/consumers/`).
Sources: [GOV.UK Pay][govuk], [Pact pending][pact-pending]

### Not covered by verified evidence
No verified claims survived for these: query-parameter versioning on its own terms, GraphQL field deprecation, `buf breaking` and protobuf package versioning, `openapi-diff`, standalone API gateways or translation proxies, generated per-version SDKs, and committed spec snapshots with CODEOWNERS. Anything this repo says about those is our own reasoning.

## How many versions can you afford?
It depends on **where compatibility logic lives**:
- **Transformation layers** (Stripe and Cadwyn in code, Google IBV in a proxy): dozens of versions, kept indefinitely.
- **GitHub-style header dates:** about 2 at a time, with a 24-month overlap.
- **Azure:** many dated versions, about 3 years each.
- **Versionless (Zalando):** exactly 1.

## Recommendation for a FastAPI monorepo (our reasoning, not itself verified)
1. **Default to additive changes** and tell consumers to be tolerant readers. *(Already demonstrated: PR #1, PR #4.)*
2. **Commit generated OpenAPI and gate PRs with oasdiff.** *(Done in this repo: drift and breaking-change gates.)*
3. **Deprecate with `deprecated` + `x-sunset` in the spec and RFC 9745/8594 headers.** *(Done.)*
4. **First unavoidable break:** add a new field or resource instead of a version.
5. **If breaks will recur for external consumers:** use header-based date versions via Cadwyn. Make the first version identical to today's API (GitHub-style), and cut new versions only for breaking changes. (Cadwyn supports header versioning by default; the alt branch uses path versioning only to match `main`.)

## Open questions (no source answered these)
- What does a transformation layer really cost as changes pile up: code size, latency, test matrix, onboarding?
- How often do teams adopting Cadwyn hit versions that differ in data or behavior, which migrations can't express cleanly?
- What's oasdiff's false-positive rate on pydantic-generated specs, for example nullable rendering differences between pydantic versions?
- For consumers inside the same monorepo, does Pact add anything beyond spec diffing plus generated, type-checked clients?

## Refuted during verification
- Google *requires* major versions in the URL path and never exposes minor versions (0–3).
- Specific details of Azure's `azure-openapi-diff` CI pipeline (0–3).
- GOV.UK Pay replaced *most* end-to-end tests with measured gains (0–3).
- Cadwyn needs no duplicated code for older versions (0–3); business logic stays version-unaware (1–2).

[zalando]: https://opensource.zalando.com/restful-api-guidelines/
[gh-blog]: https://github.blog/developer-skills/github/to-infinity-and-beyond-enabling-the-future-of-githubs-rest-api-with-api-versioning/
[gh-docs]: https://docs.github.com/en/rest/about-the-rest-api/api-versions
[gh-2026]: https://github.blog/changelog/2026-03-10-rest-api-version-2026-03-10-is-now-available
[aip185]: https://google.aip.dev/185
[stripe-ver]: https://stripe.com/blog/api-versioning
[stripe-docs]: https://docs.stripe.com/api-versions
[stripe-release]: https://stripe.com/blog/introducing-stripes-new-api-release-process
[brandur]: https://brandur.org/api-upgrades
[cadwyn]: https://github.com/zmievsa/cadwyn
[oasdiff-bc]: https://github.com/oasdiff/oasdiff/blob/main/docs/BREAKING-CHANGES.md
[oasdiff-dep]: https://github.com/oasdiff/oasdiff/blob/main/docs/DEPRECATION.md
[rfc9745]: https://www.rfc-editor.org/rfc/rfc9745.html
[rfc8594]: https://www.rfc-editor.org/rfc/rfc8594.html
[azure-blog]: https://devblogs.microsoft.com/azure-sdk/azure-approach-to-versioning-and-avoiding-breaking-changes/
[azure-policy]: https://learn.microsoft.com/en-us/azure/developer/versioning-policy
[azure-guide]: https://github.com/microsoft/api-guidelines/blob/vNext/azure/VersioningGuidelines.md
[govuk]: https://technology.blog.gov.uk/2019/01/29/lessons-learnt-using-contract-testing-in-gov-uk-pay/
[pact-pending]: https://pact.io/pending
