from orders.api.versions import versions
from orders.versioning import load_registry


def test_registry_and_version_bundle_agree():
    """api-versions.toml (lifecycle, enforced by CI) and the Cadwyn bundle (shapes)
    must list the same versions."""
    assert set(versions.version_values) == set(load_registry())


def test_every_version_change_explains_itself():
    for version in versions:
        for change in version.changes:
            assert change.__doc__ or getattr(change, "description", ""), change.__name__
