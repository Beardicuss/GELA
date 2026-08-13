from voice_assistant.config import MUTABLE_CONFIG_FILES, initialize_user_data
import json


def test_user_data_migration_copies_defaults_without_overwriting(tmp_path) -> None:
    resources = tmp_path / "resources"
    data = tmp_path / "data"
    source_config = resources / "config"
    source_config.mkdir(parents=True)
    for filename in MUTABLE_CONFIG_FILES:
        (source_config / filename).write_text(f"default:{filename}", encoding="utf-8")

    first = initialize_user_data(resources, data)
    settings = data / "config" / "settings.json"
    settings.write_text("personal settings", encoding="utf-8")
    second = initialize_user_data(resources, data)

    assert len(first) == len(MUTABLE_CONFIG_FILES)
    assert second == []
    assert settings.read_text(encoding="utf-8") == "personal settings"
    assert (data / "logs").is_dir()
    assert not list((data / "config").glob("*.tmp"))


def test_user_settings_gain_new_defaults_without_losing_edits(tmp_path) -> None:
    resources = tmp_path / "resources"
    data = tmp_path / "data"
    (resources / "config").mkdir(parents=True)
    (data / "config").mkdir(parents=True)
    defaults = {"audio": {"device": "default", "recovery": 5}, "catalog": {"interval": 3600}}
    current = {"audio": {"device": "my microphone"}}
    (resources / "config" / "settings.json").write_text(json.dumps(defaults), encoding="utf-8")
    (data / "config" / "settings.json").write_text(json.dumps(current), encoding="utf-8")

    initialize_user_data(resources, data)
    merged = json.loads((data / "config" / "settings.json").read_text(encoding="utf-8"))

    assert merged["audio"] == {"device": "my microphone", "recovery": 5}
    assert merged["catalog"]["interval"] == 3600
