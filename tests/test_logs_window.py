from voice_assistant.logs_window import filter_log


SAMPLE = "\n".join(
    (
        "2026-08-07 10:00:00 INFO Gela started",
        "2026-08-07 10:00:01 WARNING Audio overflow",
        "2026-08-07 10:00:02 ERROR Microphone failed",
    )
)


def test_log_viewer_filters_by_level() -> None:
    assert filter_log(SAMPLE, "ERROR", "") == "2026-08-07 10:00:02 ERROR Microphone failed"


def test_log_viewer_search_is_case_insensitive() -> None:
    assert filter_log(SAMPLE, "ყველა", "audio") == "2026-08-07 10:00:01 WARNING Audio overflow"
