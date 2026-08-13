from voice_assistant.voice_readiness import classify_voice_readiness


def test_readiness_distinguishes_both_languages_and_unconfigured_apps() -> None:
    records = classify_voice_readiness(
        ["Chrome", "Steam", "Discord", "Unknown"],
        {
            "Chrome": ["ქრომი"],
            "Steam": ["თამაშების ბიბლიოთეკა"],
        },
        {
            "Steam": ["steam"],
            "Discord": ["discord"],
        },
        missing_ka=set(),
        missing_en=set(),
    )

    assert {record.app_name: record.status for record in records} == {
        "Chrome": "ka_ready",
        "Discord": "en_ready",
        "Steam": "both_ready",
        "Unknown": "unconfigured",
    }


def test_readiness_marks_configured_but_unrecognizable_aliases_invalid() -> None:
    records = classify_voice_readiness(
        ["Steam", "Mixed"],
        {"Steam": ["სტიმი"], "Mixed": ["ქრომი", "სტიმი"]},
        {},
        missing_ka={"სტიმი"},
        missing_en=set(),
    )

    by_name = {record.app_name: record for record in records}
    assert by_name["Steam"].status == "invalid"
    assert by_name["Steam"].invalid_aliases == ["სტიმი"]
    assert by_name["Mixed"].status == "ka_ready"
    assert by_name["Mixed"].valid_ka_aliases == ["ქრომი"]
    assert by_name["Mixed"].invalid_aliases == ["სტიმი"]


def test_readiness_ignores_aliases_for_apps_no_longer_in_the_catalog() -> None:
    records = classify_voice_readiness(
        ["Chrome"],
        {"Chrome": ["ქრომი"], "Removed App": ["ძველი"]},
        {"Removed App": ["removed"]},
        missing_ka=set(),
        missing_en=set(),
    )

    assert [record.app_name for record in records] == ["Chrome"]
