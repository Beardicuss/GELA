import json

from voice_assistant.process_targets import (
    MAX_LEARNED_PROCESSES_PER_APP,
    load_process_targets,
    normalize_process_name,
    remember_process_target,
)


def test_factory_and_learned_process_targets_are_merged(tmp_path) -> None:
    defaults = tmp_path / "defaults.json"
    learned = tmp_path / "learned.json"
    defaults.write_text(json.dumps({"Chrome": ["chrome"]}), encoding="utf-8")
    learned.write_text(
        json.dumps({"Chrome": ["chrome_proxy"], "ChatGPT": ["codex"]}),
        encoding="utf-8",
    )

    assert load_process_targets(defaults, learned) == {
        "Chrome": ["chrome", "chrome_proxy"],
        "ChatGPT": ["codex"],
    }


def test_process_normalization_preserves_dots_inside_the_executable_name() -> None:
    assert normalize_process_name("unity.bugreporter.exe") == "unity.bugreporter"
    assert normalize_process_name("unity.bugreporter") == "unity.bugreporter"


def test_verified_process_is_persisted_once_without_changing_defaults(tmp_path) -> None:
    defaults = tmp_path / "defaults.json"
    learned = tmp_path / "learned.json"
    defaults.write_text(json.dumps({"Chrome": ["chrome"]}), encoding="utf-8")

    assert remember_process_target("ChatGPT", "Codex.exe", defaults, learned)
    assert not remember_process_target("ChatGPT", "codex", defaults, learned)
    assert json.loads(defaults.read_text(encoding="utf-8")) == {"Chrome": ["chrome"]}
    assert json.loads(learned.read_text(encoding="utf-8")) == {"ChatGPT": ["codex"]}


def test_unsafe_or_unbounded_process_learning_is_rejected(tmp_path) -> None:
    defaults = tmp_path / "defaults.json"
    learned = tmp_path / "learned.json"
    defaults.write_text("{}", encoding="utf-8")

    assert not remember_process_target("App", "explorer.exe", defaults, learned)
    assert not remember_process_target("App", "bad process", defaults, learned)
    for index in range(MAX_LEARNED_PROCESSES_PER_APP):
        assert remember_process_target("App", f"process{index}", defaults, learned)
    assert not remember_process_target("App", "one_too_many", defaults, learned)
