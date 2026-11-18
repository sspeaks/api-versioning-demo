#!/usr/bin/env python3
"""API contract tooling for the monorepo. Developers and CI run the same commands.

Every service that publishes an API has ``services/<name>/api-versions.toml``.
For each version listed there, this tool imports the version's FastAPI app,
renders its OpenAPI document and compares it with the committed copy in
``services/<name>/openapi/<version>.json``.

Commands
--------
export     Regenerate the committed specs from code         (make openapi)
drift      Fail if committed specs != specs generated from code
breaking   Fail if a stable/deprecated version has a breaking change vs --base,
           or if a lifecycle rule is violated (e.g. deleting a version early)
changelog  Print a markdown summary of contract changes vs --base (for PR comments)
"""

from __future__ import annotations

import argparse
import difflib
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_FILE = "api-versions.toml"
SPEC_DIR = "openapi"
VALID_STATUSES = {"beta", "stable", "deprecated"}
FROZEN_STATUSES = {"stable", "deprecated"}
MIN_DEPRECATION_NOTICE = timedelta(days=90)
IN_GITHUB_ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"


# --------------------------------------------------------------------------- #
# Output helpers
# --------------------------------------------------------------------------- #
def gh_annotation(level: str, message: str, file: str | None = None) -> None:
    """Emit a GitHub Actions annotation so the failure shows up on the PR."""
    if IN_GITHUB_ACTIONS:
        loc = f" file={file}" if file else ""
        print(f"::{level}{loc}::{message}")


def step_summary(markdown: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(markdown + "\n")


# --------------------------------------------------------------------------- #
# Registry + spec rendering
# --------------------------------------------------------------------------- #
@dataclass
class Service:
    name: str
    path: Path  # services/<name>, relative to ROOT

    @property
    def registry_path(self) -> Path:
        return self.path / REGISTRY_FILE

    @property
    def spec_dir(self) -> Path:
        return self.path / SPEC_DIR

    def spec_path(self, version: str) -> Path:
        return self.spec_dir / f"{version}.json"


def discover_services() -> list[Service]:
    return [
        Service(name=p.parent.name, path=p.parent.relative_to(ROOT))
        for p in sorted(ROOT.glob(f"services/*/{REGISTRY_FILE}"))
    ]


def parse_registry(text: str) -> dict[str, dict]:
    return tomllib.loads(text).get("versions", {})


def load_registry(service: Service) -> dict[str, dict]:
    return parse_registry((ROOT / service.registry_path).read_text())


def render_spec(app_ref: str) -> str:
    """Import ``module:attr`` and return its OpenAPI document as canonical JSON."""
    module_name, _, attr = app_ref.partition(":")
    app = getattr(importlib.import_module(module_name), attr)
    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_service(service: Service) -> dict[str, str]:
    """Return {"v1.json": "<spec>", ...} for every version in the registry."""
    return {
        f"{version}.json": render_spec(cfg["app"])
        for version, cfg in load_registry(service).items()
    }


def committed_specs(service: Service) -> dict[str, str]:
    spec_dir = ROOT / service.spec_dir
    if not spec_dir.is_dir():
        return {}
    return {p.name: p.read_text() for p in sorted(spec_dir.glob("*.json"))}


# --------------------------------------------------------------------------- #
# export / drift
# --------------------------------------------------------------------------- #
def cmd_export(_: argparse.Namespace) -> int:
    for service in discover_services():
        rendered = render_service(service)
        spec_dir = ROOT / service.spec_dir
        spec_dir.mkdir(parents=True, exist_ok=True)
        for name, text in rendered.items():
            (spec_dir / name).write_text(text)
            print(f"wrote {service.spec_dir / name}")
        for stale in set(committed_specs(service)) - set(rendered):
            (spec_dir / stale).unlink()
            print(f"removed {service.spec_dir / stale} (no longer in {REGISTRY_FILE})")
    return 0


def cmd_drift(_: argparse.Namespace) -> int:
    problems = 0
    for service in discover_services():
        rendered = render_service(service)
        committed = committed_specs(service)
        for name in sorted(set(rendered) | set(committed)):
            rel = service.spec_dir / name
            if name not in committed:
                msg = f"{rel} is missing. Run `make openapi` and commit the result."
            elif name not in rendered:
                msg = f"{rel} is committed but its version is not in {REGISTRY_FILE}."
            elif rendered[name] != committed[name]:
                msg = (
                    f"{rel} does not match the code. The API changed but the committed "
                    "contract was not regenerated. Run `make openapi` and commit the result."
                )
                diff = difflib.unified_diff(
                    committed[name].splitlines(),
                    rendered[name].splitlines(),
                    f"{rel} (committed)",
                    f"{rel} (generated from code)",
                    lineterm="",
                )
                print("\n".join(list(diff)[:80]))
            else:
                print(f"ok   {rel}")
                continue
            problems += 1
            print(f"FAIL {msg}")
            gh_annotation("error", msg, file=str(rel))
    if problems:
        step_summary(
            "### ❌ API spec drift\nCommitted OpenAPI specs don't match the code. "
            "Run `make openapi` and commit."
        )
        return 1
    print("No drift: committed contracts match the code.")
    return 0


# --------------------------------------------------------------------------- #
# breaking / lifecycle
# --------------------------------------------------------------------------- #
def git_show(ref: str, path: Path) -> str | None:
    proc = subprocess.run(
        ["git", "show", f"{ref}:{path.as_posix()}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return proc.stdout if proc.returncode == 0 else None


def find_oasdiff() -> str:
    # Prefer the pinned copy from `make tools` so local runs match CI exactly.
    for candidate in (ROOT / ".bin" / "oasdiff", shutil.which("oasdiff")):
        if candidate and Path(candidate).exists():
            return str(candidate)
    sys.exit(
        "oasdiff not found. Install it with `make tools` (downloads a pinned release into "
        ".bin/), or `brew install oasdiff`, or `go install github.com/oasdiff/oasdiff@latest`."
    )


def run_oasdiff(subcommand: str, base_text: str, head_path: Path, *extra: str):
    """Run oasdiff with the base spec from git and the head spec from the working tree.

    The head path is passed repo-relative so GitHub annotations attach to the file in the PR.
    """
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
        tmp.write(base_text)
        base_path = tmp.name
    cmd = [find_oasdiff(), subcommand, base_path, head_path.as_posix(), *extra]
    if "text" in extra:  # --color is only accepted for the text format
        cmd += ["--color", "never"]
    try:
        return subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
    finally:
        os.unlink(base_path)


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rows: list[tuple[str, str, str, str]] = field(default_factory=list)  # svc, ver, status, result


def check_lifecycle(
    service: Service,
    version: str,
    base_cfg: dict | None,
    head_cfg: dict | None,
    report: Report,
    today: date,
) -> None:
    """Rules about how a version's status may change between base and head."""
    where = f"{service.name}/{version}"
    if head_cfg is not None:
        status = head_cfg.get("status")
        if status not in VALID_STATUSES:
            report.errors.append(f"{where}: unknown status {status!r}")
        if status == "deprecated" and "sunset" not in head_cfg:
            report.errors.append(f"{where}: deprecated versions must declare a `sunset` date")
    if base_cfg is None or head_cfg is None:
        return

    before, after = base_cfg["status"], head_cfg["status"]
    if before in FROZEN_STATUSES and after == "beta":
        report.errors.append(
            f"{where}: cannot move from `{before}` back to `beta`. Consumers already depend "
            "on it. Ship the change as a new version instead."
        )
    if before != "deprecated" and after == "deprecated":
        sunset = date.fromisoformat(head_cfg["sunset"])
        if sunset - today < MIN_DEPRECATION_NOTICE:
            report.errors.append(
                f"{where}: sunset {sunset} gives consumers less than "
                f"{MIN_DEPRECATION_NOTICE.days} days' notice."
            )
    if before == "deprecated" and after == "deprecated":
        if date.fromisoformat(head_cfg["sunset"]) < date.fromisoformat(base_cfg["sunset"]):
            report.errors.append(
                f"{where}: sunset date can be moved later, never earlier "
                f"({base_cfg['sunset']} -> {head_cfg['sunset']})."
            )


def check_removed(service: Service, version: str, base_cfg: dict, report: Report, today: date):
    where = f"{service.name}/{version}"
    status = base_cfg["status"]
    sunset = date.fromisoformat(base_cfg["sunset"]) if "sunset" in base_cfg else None
    if status == "beta":
        report.rows.append((service.name, version, status, "🗑️ removed (beta, allowed)"))
    elif status == "deprecated" and sunset and sunset <= today:
        report.rows.append((service.name, version, status, f"🗑️ removed (sunset {sunset})"))
    else:
        when = f"its sunset date ({sunset})" if sunset else "it is deprecated and sunset"
        report.errors.append(
            f"{where}: cannot delete a `{status}` version before {when}. "
            "Consumers are still promised this API."
        )
        report.rows.append((service.name, version, status, "❌ removed too early"))


def cmd_breaking(args: argparse.Namespace) -> int:
    today = date.fromisoformat(args.today) if args.today else date.today()
    fmt = "githubactions" if IN_GITHUB_ACTIONS else "text"
    report = Report()

    for service in discover_services():
        base_registry_text = git_show(args.base, service.registry_path)
        base_registry = parse_registry(base_registry_text) if base_registry_text else {}
        head_registry = load_registry(service)

        for version in sorted(set(base_registry) | set(head_registry)):
            base_cfg, head_cfg = base_registry.get(version), head_registry.get(version)
            check_lifecycle(service, version, base_cfg, head_cfg, report, today)

            if base_cfg is None:
                report.rows.append((service.name, version, head_cfg["status"], "🆕 new version"))
                continue
            if head_cfg is None:
                check_removed(service, version, base_cfg, report, today)
                continue

            base_spec = git_show(args.base, service.spec_path(version))
            if base_spec is None:
                report.rows.append((service.name, version, base_cfg["status"], "🆕 new spec"))
                continue

            # The *base* branch's status decides the rules, so a PR can't relax its own
            # policy (e.g. flip stable -> beta) to slip a breaking change through.
            status = base_cfg["status"]
            print(f"\n=== {service.name} {version} ({status}) vs {args.base} ===", flush=True)
            spec = service.spec_path(version)
            # Machine-readable pass to classify, human-readable pass to display.
            proc = run_oasdiff("breaking", base_spec, spec, "--format", "json")
            if proc.returncode != 0:
                report.errors.append(f"{service.name}/{version}: oasdiff failed:\n{proc.stderr}")
                report.rows.append((service.name, version, status, "💥 oasdiff error"))
                continue
            levels = [change["level"] for change in json.loads(proc.stdout or "[]")]
            has_errors, has_warnings = 3 in levels, 2 in levels

            display = run_oasdiff("breaking", base_spec, spec, "--format", fmt).stdout.strip()
            if IN_GITHUB_ACTIONS and status not in FROZEN_STATUSES:
                # beta: report only, don't let oasdiff emit ::error annotations.
                display = display.replace("::error", "::notice").replace("::warning", "::notice")
            elif IN_GITHUB_ACTIONS and args.allow_breaking:
                display = display.replace("::error", "::warning")
            print(display or "No breaking changes.")

            if not has_errors:
                result = "⚠️ warnings only" if has_warnings else "✅ no breaking changes"
            elif status in FROZEN_STATUSES:
                report.errors.append(
                    f"{service.name}/{version} is `{status}`; breaking changes are not allowed. "
                    "Make the change additive, or introduce it in a new version."
                )
                result = "❌ breaking change"
            else:
                report.warnings.append(f"{service.name}/{version} is beta; breaking change ok.")
                result = "⚠️ breaking (beta, allowed)"
            report.rows.append((service.name, version, status, result))

    summary = [
        "### API contract: breaking-change gate",
        "",
        "| service | version | status (base) | result |",
        "|---|---|---|---|",
    ]
    summary += [f"| {s} | `{v}` | {st} | {r} |" for s, v, st, r in report.rows]
    step_summary("\n".join(summary))

    print()
    for warning in report.warnings:
        print(f"WARN {warning}")
    if report.errors and args.allow_breaking:
        print("Breaking changes found, but override label `api-breaking-change-approved` is set:")
        for error in report.errors:
            print(f"WARN {error}")
            gh_annotation("warning", error)
        step_summary("> ⚠️ Overridden by `api-breaking-change-approved` label.")
        return 0
    for error in report.errors:
        print(f"FAIL {error}")
        gh_annotation("error", error)
    if report.errors:
        return 1
    print("Contract check passed: no breaking changes to stable or deprecated versions.")
    return 0


# --------------------------------------------------------------------------- #
# changelog (markdown for PR comments)
# --------------------------------------------------------------------------- #
def tidy_changelog(markdown: str) -> str:
    """Drop oasdiff's top-level headings and blank-line padding so it nests in a comment."""
    lines = []
    for line in markdown.splitlines():
        if line.startswith(("# API Changelog", "## API Changes", "No changes detected")):
            continue
        if line.startswith("### "):
            line = "**" + line[4:].strip() + "**"
        if line.strip() or (lines and lines[-1].strip()):
            lines.append(line.rstrip())
    return "\n".join(lines).strip()


def version_key(version: str) -> int:
    """Sort v2 < v10 (lexicographic order would not)."""
    digits = "".join(ch for ch in version if ch.isdigit())
    return int(digits) if digits else 0


def new_version_section(
    service: Service, version: str, base_registry: dict, head_registry: dict
) -> str:
    """Describe a brand-new version as a diff against the version it builds on."""
    status = head_registry[version]["status"]
    title = f"#### `{service.name}` {version}\n🆕 New version (`{status}`)."
    older = [
        v for v in base_registry if v in head_registry and version_key(v) < version_key(version)
    ]
    if not older:
        return title
    previous = max(older, key=version_key)
    proc = run_oasdiff(
        "changelog",
        (ROOT / service.spec_path(previous)).read_text(),
        service.spec_path(version),
        "--format",
        "markdown",
    )
    body = tidy_changelog(proc.stdout) or "_Identical to the previous version._"
    return f"{title} Differences from `{previous}`:\n\n{body}"


def cmd_changelog(args: argparse.Namespace) -> int:
    sections: list[str] = []
    for service in discover_services():
        base_text = git_show(args.base, service.registry_path)
        base_registry = parse_registry(base_text) if base_text else {}
        head_registry = load_registry(service)
        for version in sorted(set(base_registry) | set(head_registry)):
            title = f"#### `{service.name}` {version}"
            if version not in base_registry:
                sections.append(new_version_section(service, version, base_registry, head_registry))
                continue
            if version not in head_registry:
                sections.append(f"{title}\n🗑️ Version removed.")
                continue
            base_spec = git_show(args.base, service.spec_path(version))
            if base_spec is None:
                continue
            status = base_registry[version]["status"]
            lifecycle = ""
            if head_registry[version] != base_registry[version]:
                lifecycle = f"\nLifecycle: `{status}` → `{head_registry[version]['status']}`"
            proc = run_oasdiff(
                "changelog", base_spec, service.spec_path(version), "--format", "markdown"
            )
            body = tidy_changelog(proc.stdout)
            if body or lifecycle:
                sections.append(f"{title} (`{status}`){lifecycle}\n\n{body}")

    print("<!-- api-contract-changelog -->")
    print("## 📜 API contract changes\n")
    if sections:
        print("\n\n".join(sections))
    else:
        print("No changes to any public API contract in this PR. ✅")
    repo_url = "{}/{}".format(
        os.environ.get("GITHUB_SERVER_URL", "https://github.com"),
        os.environ.get("GITHUB_REPOSITORY", "sspeaks/api-versioning-demo"),
    )
    print(
        "\n<sub>Generated by `tools/api_contract.py changelog` · see the "
        f"[API versioning policy]({repo_url}/blob/main/docs/api-versioning-policy.md)</sub>"
    )
    return 0


# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("export", help="regenerate committed OpenAPI specs").set_defaults(
        func=cmd_export
    )
    sub.add_parser("drift", help="fail if committed specs differ from code").set_defaults(
        func=cmd_drift
    )
    p = sub.add_parser("breaking", help="fail on breaking changes / lifecycle violations")
    p.add_argument("--base", default="origin/main", help="git ref to compare against")
    p.add_argument("--allow-breaking", action="store_true", help="report but don't fail")
    p.add_argument("--today", help=argparse.SUPPRESS)  # for tests
    p.set_defaults(func=cmd_breaking)
    p = sub.add_parser("changelog", help="markdown summary of contract changes")
    p.add_argument("--base", default="origin/main")
    p.set_defaults(func=cmd_changelog)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
