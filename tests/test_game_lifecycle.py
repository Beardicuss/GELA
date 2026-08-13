import json

from voice_assistant.game_lifecycle import (
    gameplay_processes_for,
    is_anti_cheat_process,
    is_gameplay_process,
    is_launcher_process,
    mark_game_stopped,
    record_game_observation,
)


def test_game_process_roles_are_tracked_separately(tmp_path) -> None:
    path = tmp_path / "game_lifecycle.json"

    record = record_game_observation(
        "ELDEN RING NIGHTREIGN",
        "steam://rungameid/2622380",
        {"steam", "steamwebhelper", "start_protected_game", "nightreign"},
        {"steam", "steamwebhelper"},
        {"nightreign"},
        "running",
        verified_process="nightreign",
        path=path,
    )

    assert record["launcher_processes"] == ["steam", "steamwebhelper"]
    assert record["anti_cheat_processes"] == ["start_protected_game"]
    assert record["game_processes"] == ["nightreign"]
    assert gameplay_processes_for("ELDEN RING NIGHTREIGN", path) == ["nightreign"]


def test_short_lived_anticheat_is_retained_until_session_stops(tmp_path) -> None:
    path = tmp_path / "game_lifecycle.json"
    record_game_observation(
        "Game",
        "steam://rungameid/1",
        {"steam", "easyanticheat_eos"},
        {"steam"},
        {"game"},
        "launching",
        path=path,
    )

    record = record_game_observation(
        "Game",
        "steam://rungameid/1",
        {"steam", "game"},
        {"steam"},
        {"game"},
        "running",
        verified_process="game",
        path=path,
    )

    assert record["anti_cheat_processes"] == ["easyanticheat_eos"]
    mark_game_stopped("Game", path)
    assert gameplay_processes_for("Game", path) == []
    assert json.loads(path.read_text(encoding="utf-8"))["Game"]["anti_cheat_processes"] == []


def test_role_classification_never_treats_launcher_or_anticheat_as_gameplay() -> None:
    assert is_launcher_process("Steam.exe")
    assert is_anti_cheat_process("EasyAntiCheat_EOS.exe")
    assert is_anti_cheat_process("start_protected_game.exe")
    assert not is_gameplay_process("steam")
    assert not is_gameplay_process("battleye_launcher")
    assert is_gameplay_process("nightreign")
