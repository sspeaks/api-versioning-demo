"""Unit tests for the lifecycle rules in tools/api_contract.py."""

from datetime import date
from pathlib import Path

import pytest

import api_contract as ac

SVC = ac.Service(name="orders", path=Path("services/orders"))
TODAY = date(2026, 11, 17)


def lifecycle(base, head):
    report = ac.Report()
    ac.check_lifecycle(SVC, "v1", base, head, report, TODAY)
    return report.errors


def removed(base):
    report = ac.Report()
    ac.check_removed(SVC, "v1", base, report, TODAY)
    return report.errors


def test_promoting_beta_to_stable_is_fine():
    assert lifecycle({"status": "beta"}, {"status": "stable"}) == []


@pytest.mark.parametrize("before", ["stable", "deprecated"])
def test_cannot_demote_to_beta(before):
    base = {"status": before, "sunset": "2027-06-30"}
    assert "back to `beta`" in lifecycle(base, {"status": "beta"})[0]


def test_deprecated_requires_sunset():
    assert "must declare a `sunset`" in lifecycle(None, {"status": "deprecated"})[0]


def test_deprecation_needs_90_days_notice():
    errors = lifecycle({"status": "stable"}, {"status": "deprecated", "sunset": "2026-12-01"})
    assert "less than 90 days" in errors[0]
    assert lifecycle({"status": "stable"}, {"status": "deprecated", "sunset": "2027-06-30"}) == []


def test_sunset_can_only_move_later():
    base = {"status": "deprecated", "sunset": "2027-06-30"}
    assert lifecycle(base, {"status": "deprecated", "sunset": "2027-12-31"}) == []
    assert "never earlier" in lifecycle(base, {"status": "deprecated", "sunset": "2027-01-01"})[0]


def test_removing_beta_is_fine():
    assert removed({"status": "beta"}) == []


def test_removing_stable_is_blocked():
    assert "cannot delete" in removed({"status": "stable"})[0]


def test_removing_deprecated_before_sunset_is_blocked():
    assert "cannot delete" in removed({"status": "deprecated", "sunset": "2027-06-30"})[0]


def test_removing_deprecated_after_sunset_is_fine():
    assert removed({"status": "deprecated", "sunset": "2026-11-01"}) == []


def test_changelog_reports_only_lifecycle_fields():
    base = {"app": "a:app", "status": "stable"}
    assert ac.lifecycle_changes(base, {**base, "app": "b:app"}) == ""
    assert ac.lifecycle_changes(base, {**base, "status": "deprecated", "sunset": "2027-06-30"}) == (
        "\nLifecycle: status `stable` → `deprecated`, sunset `None` → `2027-06-30`"
    )


def test_tidy_changelog_drops_oasdiff_noise():
    noise = "No changes to report, but the specs are different.\nRun 'oasdiff diff' to see more.\n"
    assert ac.tidy_changelog(noise) == ""
