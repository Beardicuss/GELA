from __future__ import annotations

import json
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import sys

from .storage import atomic_write_text, replace_file


def is_microsoft_store_python(value: str | Path) -> bool:
    normalized = str(value).replace("/", "\\").casefold()
    return "windowsapps\\pythonsoftwarefoundation.python" in normalized


def ensure_non_virtualized_development_runtime() -> None:
    if getattr(sys, "frozen", False):
        return
    candidates = (sys.base_prefix, getattr(sys, "_base_executable", ""))
    if any(is_microsoft_store_python(value) for value in candidates):
        raise RuntimeError(
            "Gela development cannot run under Microsoft Store Python because Windows "
            "redirects LocalAppData into a separate package cache. Run scripts/setup_dev.ps1 "
            "with a regular Python 3.11-3.13 installation."
        )


ensure_non_virtualized_development_runtime()


RESOURCE_ROOT = (
    Path(sys._MEIPASS)  # type: ignore[attr-defined]
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parents[2]
)
PROJECT_ROOT = RESOURCE_ROOT
USER_DATA_ROOT = Path(
    os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
) / "Gela"
USER_CONFIG_ROOT = USER_DATA_ROOT / "config"
USER_LOG_ROOT = USER_DATA_ROOT / "logs"
MUTABLE_CONFIG_FILES = (
    "settings.json",
    "aliases.json",
    "english_aliases.json",
    "alias_archive.json",
    "apps.json",
    "vocabulary_audit.json",
    "routines.json",
    "app_profiles.json",
)


def _merge_missing(target: dict, defaults: dict) -> bool:
    changed = False
    for key, value in defaults.items():
        if key not in target:
            target[key] = value
            changed = True
        elif isinstance(target[key], dict) and isinstance(value, dict):
            changed = _merge_missing(target[key], value) or changed
    return changed


def initialize_user_data(
    resource_root: Path = RESOURCE_ROOT,
    data_root: Path = USER_DATA_ROOT,
) -> list[Path]:
    """Seed missing user-editable files without overwriting existing preferences."""
    config_root = data_root / "config"
    config_root.mkdir(parents=True, exist_ok=True)
    (data_root / "logs").mkdir(parents=True, exist_ok=True)
    migrated: list[Path] = []
    for filename in MUTABLE_CONFIG_FILES:
        source = resource_root / "config" / filename
        destination = config_root / filename
        if destination.exists() or not source.is_file():
            continue
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        shutil.copy2(source, temporary)
        if destination.exists():
            temporary.unlink()
            continue
        replace_file(temporary, destination)
        migrated.append(destination)
    settings_source = resource_root / "config" / "settings.json"
    settings_destination = config_root / "settings.json"
    if settings_source.is_file() and settings_destination.is_file():
        try:
            defaults = json.loads(settings_source.read_text(encoding="utf-8"))
            current = json.loads(settings_destination.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
        else:
            if _merge_missing(current, defaults):
                atomic_write_text(
                    settings_destination,
                    json.dumps(current, ensure_ascii=False, indent=2) + "\n",
                )
    return migrated


initialize_user_data()
DEFAULT_CONFIG_PATH = USER_CONFIG_ROOT / "settings.json"


@dataclass(frozen=True)
class AudioConfig:
    device_name_contains: str
    sample_rate: int
    channels: int
    block_size: int
    fallback_to_default_input: bool = True
    device_check_interval_seconds: float = 5.0
    resume_gap_seconds: float = 10.0


@dataclass(frozen=True)
class BackgroundConfig:
    language: str
    wake_phrases: list[str]
    wake_confidence: float
    command_confidence: float
    confirmation_response_confidence: float
    ambiguity_margin: float
    vad_min_rms: int
    vad_noise_ratio: float
    vad_hangover_blocks: int
    command_timeout_seconds: float
    one_sentence_commands: bool
    command_retry_attempts: int
    cooldown_seconds: float
    retry_seconds: float


@dataclass(frozen=True)
class CatalogConfig:
    auto_refresh: bool
    interval_seconds: float
    refresh_on_start: bool


@dataclass(frozen=True)
class QuestionAnsweringConfig:
    enabled: bool
    endpoint: str
    model: str
    request_timeout_seconds: float
    question_timeout_seconds: float
    max_answer_characters: int


@dataclass(frozen=True)
class OnlineServicesConfig:
    weather_enabled: bool
    wikipedia_enabled: bool
    location_name: str
    latitude: float
    longitude: float
    request_timeout_seconds: float
    query_timeout_seconds: float
    max_answer_characters: int


@dataclass(frozen=True)
class Settings:
    audio: AudioConfig
    models: dict[str, Path]
    catalog: CatalogConfig
    question_answering: QuestionAnsweringConfig
    online_services: OnlineServicesConfig
    background: BackgroundConfig


def load_settings(path: Path = DEFAULT_CONFIG_PATH) -> Settings:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        audio = AudioConfig(**raw["audio"])
        background_raw = dict(raw["background"])
        background_raw.setdefault("one_sentence_commands", False)
        background_raw.setdefault("command_retry_attempts", 1)
        background = BackgroundConfig(**background_raw)
        catalog = CatalogConfig(**raw["catalog"])
        question_answering = QuestionAnsweringConfig(**raw["question_answering"])
        online_services = OnlineServicesConfig(**raw["online_services"])
        models = {
            language: (RESOURCE_ROOT / model_path).resolve()
            for language, model_path in raw["models"].items()
        }
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeError(f"Cannot load configuration from {path}: {exc}") from exc

    if audio.sample_rate <= 0 or audio.channels != 1 or audio.block_size <= 0:
        raise ValueError("Audio settings require a positive sample rate/block size and one channel")
    if audio.device_check_interval_seconds <= 0 or audio.resume_gap_seconds <= 0:
        raise ValueError("Audio recovery intervals must be positive")
    if background.language not in models or not background.wake_phrases:
        raise ValueError("Background language must have a model and at least one wake phrase")
    if min(background.command_timeout_seconds, background.cooldown_seconds, background.retry_seconds) <= 0:
        raise ValueError("Background timing values must be positive")
    if not 0 <= background.command_retry_attempts <= 3:
        raise ValueError("Command retry attempts must be between 0 and 3")
    confidence_values = (
        background.wake_confidence,
        background.command_confidence,
        background.confirmation_response_confidence,
    )
    if not all(0.0 <= value <= 1.0 for value in confidence_values):
        raise ValueError("Recognition confidence values must be between 0 and 1")
    if not 0.0 <= background.ambiguity_margin <= 1.0:
        raise ValueError("Invalid ambiguity margin")
    if background.vad_min_rms < 0 or background.vad_noise_ratio <= 1 or background.vad_hangover_blocks < 0:
        raise ValueError("Invalid voice-activity settings")
    if catalog.interval_seconds < 30:
        raise ValueError("Catalog refresh interval must be at least 30 seconds")
    if question_answering.request_timeout_seconds <= 0:
        raise ValueError("Question-answering request timeout must be positive")
    if question_answering.question_timeout_seconds < 3:
        raise ValueError("Question-listening timeout must be at least 3 seconds")
    if not 100 <= question_answering.max_answer_characters <= 10_000:
        raise ValueError("Question-answering character limit must be between 100 and 10000")
    if not (-90 <= online_services.latitude <= 90 and -180 <= online_services.longitude <= 180):
        raise ValueError("Online weather coordinates are invalid")
    if not online_services.location_name.strip():
        raise ValueError("Online weather location name is empty")
    if online_services.request_timeout_seconds <= 0 or online_services.query_timeout_seconds < 3:
        raise ValueError("Online service timeouts are invalid")
    if not 100 <= online_services.max_answer_characters <= 10_000:
        raise ValueError("Online answer character limit must be between 100 and 10000")
    return Settings(
        audio=audio,
        models=models,
        catalog=catalog,
        question_answering=question_answering,
        online_services=online_services,
        background=background,
    )
