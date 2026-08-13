from pathlib import Path

from voice_assistant.config import RESOURCE_ROOT, is_microsoft_store_python, load_settings


def test_microsoft_store_python_runtime_detection() -> None:
    assert is_microsoft_store_python(
        r"C:\Program Files\WindowsApps\PythonSoftwareFoundation.Python.3.12_abc"
    )
    assert is_microsoft_store_python(
        r"C:\Users\User\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.12_abc\python.exe"
    )
    assert not is_microsoft_store_python(
        r"C:\Users\User\AppData\Local\Programs\Python\Python311"
    )


def test_default_settings_load() -> None:
    settings = load_settings(RESOURCE_ROOT / "config" / "settings.json")
    assert settings.audio.sample_rate == 16_000
    assert settings.audio.channels == 1
    assert settings.models["en"] == Path(settings.models["en"]).resolve()
    assert settings.models["ka"] == Path(settings.models["ka"]).resolve()
    assert settings.catalog.auto_refresh is True
    assert settings.catalog.interval_seconds == 3600
    assert settings.audio.fallback_to_default_input is True
    assert settings.audio.device_check_interval_seconds == 5.0
    assert settings.audio.resume_gap_seconds == 10.0
    assert settings.background.command_retry_attempts == 1
    assert settings.background.one_sentence_commands is True
    assert settings.question_answering.enabled is False
    assert settings.question_answering.endpoint == "http://127.0.0.1:11434/api/generate"
    assert settings.question_answering.question_timeout_seconds == 12.0
    assert settings.online_services.weather_enabled is False
    assert settings.online_services.wikipedia_enabled is False
    assert settings.online_services.location_name == "Gori, Shida Kartli"
