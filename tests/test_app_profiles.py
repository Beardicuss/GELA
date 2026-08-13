import json

import pytest

from voice_assistant.app_profiles import (
    AppProfileStore,
    profile_for,
    validate_profile,
)


def make_store(tmp_path):
    catalog = tmp_path / "apps.json"
    profiles = tmp_path / "app_profiles.json"
    catalog.write_text(json.dumps([{"name": "Chrome"}, {"name": "Nightreign"}]), encoding="utf-8")
    profiles.write_text("{}", encoding="utf-8")
    return AppProfileStore(catalog, profiles), profiles


def test_profile_store_validates_and_persists_controls(tmp_path) -> None:
    store, path = make_store(tmp_path)

    profile = store.set(
        "Nightreign",
        ["Nightreign.exe"],
        ["ELDEN RING NIGHTREIGN"],
        "graceful_only",
    )
    store.save()

    assert profile.preferred_processes == ["nightreign"]
    assert profile_for("Nightreign", path) == profile


def test_default_profile_is_not_written(tmp_path) -> None:
    store, path = make_store(tmp_path)
    store.set("Chrome", [], [], "graceful_then_force")
    store.save()
    assert json.loads(path.read_text(encoding="utf-8")) == {}


def test_profile_rejects_unsafe_processes_titles_and_behavior() -> None:
    with pytest.raises(ValueError, match="process"):
        validate_profile(["explorer.exe"], [], "graceful_only")
    with pytest.raises(ValueError, match="titles"):
        validate_profile([], ["x"], "graceful_only")
    with pytest.raises(ValueError, match="behavior"):
        validate_profile([], [], "destroy_everything")
