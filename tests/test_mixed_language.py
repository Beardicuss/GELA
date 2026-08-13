from voice_assistant.catalog import CatalogEntry
from voice_assistant.recognizer import (
    mixed_language_close_target,
    mixed_language_launch_target,
    mixed_language_window_target,
)


NIGHTREIGN = CatalogEntry(
    "ELDEN RING NIGHTREIGN",
    ["ნაითრეინი"],
    "uri",
    "steam://rungameid/2622380",
)


def test_georgian_launch_verb_uses_embedded_english_game_alias() -> None:
    result = mixed_language_launch_target(
        "გახსენი ვაი ჩართე ენი",
        "can send e night rain",
        {"night rain": NIGHTREIGN},
    )

    assert result == ("night rain", NIGHTREIGN)


def test_mixed_target_requires_georgian_launch_verb() -> None:
    assert mixed_language_launch_target(
        "დახურე ვაი ჩართე ენი",
        "close you night rain",
        {"night rain": NIGHTREIGN},
    ) is None


def test_georgian_close_verb_uses_embedded_english_game_alias() -> None:
    result = mixed_language_close_target(
        "გამორთე მაჩვენე",
        "more to night rain",
        {"night rain": NIGHTREIGN},
    )

    assert result == ("night rain", NIGHTREIGN)


def test_disconnect_is_supported_as_mixed_close_verb() -> None:
    result = mixed_language_close_target(
        "გათიშე მაჩვენე",
        "to night rain",
        {"night rain": NIGHTREIGN},
    )

    assert result == ("night rain", NIGHTREIGN)


def test_longest_embedded_alias_wins() -> None:
    result = mixed_language_launch_target(
        "ჩართე ვაიფაი ენი",
        "java elder ring night rain",
        {"night rain": NIGHTREIGN, "elder ring night rain": NIGHTREIGN},
    )

    assert result == ("elder ring night rain", NIGHTREIGN)


def test_georgian_window_verbs_use_embedded_english_game_alias() -> None:
    cases = {
        "მაჩვენე მაჩვენე": "window_focus",
        "გადადი მაჩვენე": "window_focus",
        "დამალე მაჩვენე": "window_minimize",
        "გაზარდე მაჩვენე": "window_maximize",
        "აღადგინე მაჩვენე": "window_restore",
    }

    for georgian_text, expected_action in cases.items():
        result = mixed_language_window_target(
            georgian_text,
            "more to night rain",
            {"night rain": NIGHTREIGN},
        )

        assert result == (expected_action, "night rain", NIGHTREIGN)


def test_mixed_window_target_rejects_launch_and_close_verbs() -> None:
    targets = {"night rain": NIGHTREIGN}

    assert mixed_language_window_target("ჩართე მაჩვენე", "to night rain", targets) is None
    assert mixed_language_window_target("დახურე მაჩვენე", "to night rain", targets) is None


def test_mixed_window_target_requires_a_complete_registered_alias() -> None:
    assert mixed_language_window_target(
        "დამალე მაჩვენე",
        "more to night",
        {"night rain": NIGHTREIGN},
    ) is None
