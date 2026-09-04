from __future__ import annotations

import json
import time
from dataclasses import dataclass

import sounddevice as sd
from vosk import KaldiRecognizer, Model, SetLogLevel

from .catalog import CatalogEntry, alias_index, normalize_phrase
from .config import Settings
from .models import validate_model_directory


COMMAND_PREFIXES = {
    "en": ("open", "launch", "start", "run"),
    "ka": ("გახსენი", "ჩართე", "გაუშვი"),
}
MIXED_CLOSE_PREFIXES = ("დახურე", "გამორთე", "გათიშე")
MIXED_WINDOW_PREFIXES = {
    "window_focus": ("გადადი", "მაჩვენე"),
    "window_minimize": ("დამალე", "ჩაკეცე"),
    "window_maximize": ("გაზარდე", "გაადიდე"),
    "window_restore": ("აღადგინე", "ამოკეცე", "დააპატარავე"),
}
KA_FORMAL_VERBS = {
    "გახსენით": "გახსენი",
    "ჩართეთ": "ჩართე",
    "დაუკარით": "დაუკარი",
    "გაუშვით": "გაუშვი",
    "დახურეთ": "დახურე",
    "გამორთეთ": "გამორთე",
    "გათიშეთ": "გათიშე",
    "გადადით": "გადადი",
    "მაჩვენეთ": "მაჩვენე",
    "დამალეთ": "დამალე",
    "გაზარდეთ": "გაზარდე",
    "აღადგინეთ": "აღადგინე",
    "ჩაკეცეთ": "ჩაკეცე",
    "ამოკეცეთ": "ამოკეცე",
    "გაადიდეთ": "გაადიდე",
    "დააპატარავეთ": "დააპატარავე",
}


@dataclass(frozen=True)
class RecognitionResult:
    text: str
    confidence: float
    words: tuple[tuple[str, float], ...] = ()


def combine_recognition_results(results: list[RecognitionResult]) -> RecognitionResult:
    """Join decoder endpoint segments without losing per-word confidence."""
    nonempty = [result for result in results if result.text]
    if not nonempty:
        return RecognitionResult("", 0.0)
    text = " ".join(result.text for result in nonempty)
    words = tuple(word for result in nonempty for word in result.words)
    confidence = min(
        (value for result in nonempty for _word, value in result.words),
        default=min(result.confidence for result in nonempty),
    )
    return RecognitionResult(text, confidence, words)


def canonicalize_georgian_command(result: RecognitionResult) -> RecognitionResult:
    tokens = result.text.split()
    if not tokens or tokens[0] not in KA_FORMAL_VERBS:
        return result
    tokens[0] = KA_FORMAL_VERBS[tokens[0]]
    words = result.words
    if words:
        words = ((tokens[0], words[0][1]), *words[1:])
    return RecognitionResult(" ".join(tokens), result.confidence, words)


def decode_result(payload: str) -> RecognitionResult:
    result = json.loads(payload)
    text = normalize_phrase(result.get("text", ""))
    words = tuple(
        (normalize_phrase(str(word.get("word", ""))), float(word.get("conf", 0.0)))
        for word in result.get("result", [])
        if normalize_phrase(str(word.get("word", "")))
    )
    confidence = min((confidence for _word, confidence in words), default=0.0)
    return RecognitionResult(text=text, confidence=confidence, words=words)


def split_wake_command(
    result: RecognitionResult,
    wake_phrases: list[str],
) -> tuple[str, float, RecognitionResult] | None:
    """Split an exact wake prefix from an optional command remainder."""
    tokens = result.text.split()
    normalized_wakes = sorted(
        {normalize_phrase(phrase) for phrase in wake_phrases if normalize_phrase(phrase)},
        key=lambda phrase: len(phrase.split()),
        reverse=True,
    )
    for wake_phrase in normalized_wakes:
        wake_tokens = wake_phrase.split()
        if tokens[: len(wake_tokens)] != wake_tokens:
            continue
        command_text = " ".join(tokens[len(wake_tokens) :])
        if result.words and len(result.words) >= len(wake_tokens):
            word_tokens = [word for word, _confidence in result.words]
            if word_tokens[: len(wake_tokens)] == wake_tokens:
                wake_confidence = min(
                    confidence for _word, confidence in result.words[: len(wake_tokens)]
                )
                command_words = result.words[len(wake_tokens) :]
                command_confidence = min(
                    (confidence for _word, confidence in command_words),
                    default=0.0,
                )
                return wake_phrase, wake_confidence, RecognitionResult(
                    command_text,
                    command_confidence,
                    command_words,
                )
        fallback_confidence = result.confidence
        return wake_phrase, fallback_confidence, RecognitionResult(
            command_text,
            fallback_confidence if command_text else 0.0,
        )
    return None


def matched_phrase_confidence(result: RecognitionResult, phrase: str) -> float:
    """Return the strongest complete-token match confidence for a phrase."""
    phrase_tokens = normalize_phrase(phrase).split()
    if not phrase_tokens:
        return 0.0
    if result.words:
        word_tokens = [word for word, _confidence in result.words]
        width = len(phrase_tokens)
        confidences = [
            min(confidence for _word, confidence in result.words[index : index + width])
            for index in range(len(word_tokens) - width + 1)
            if word_tokens[index : index + width] == phrase_tokens
        ]
        if confidences:
            return max(confidences)
    result_tokens = result.text.split()
    width = len(phrase_tokens)
    if any(
        result_tokens[index : index + width] == phrase_tokens
        for index in range(len(result_tokens) - width + 1)
    ):
        return result.confidence
    return 0.0


def command_phrases(entries: list[CatalogEntry], language: str) -> dict[str, CatalogEntry]:
    aliases = alias_index(entries)
    phrases: dict[str, CatalogEntry] = dict(aliases)
    for alias, entry in aliases.items():
        for prefix in COMMAND_PREFIXES.get(language, COMMAND_PREFIXES["en"]):
            phrases[f"{prefix} {alias}"] = entry
        if entry.launch_type == "file":
            media_prefix = "დაუკარი" if language == "ka" else "play"
            phrases[f"{media_prefix} {alias}"] = entry
    return phrases


def _mixed_language_target(
    georgian_text: str,
    english_text: str,
    english_targets: dict[str, CatalogEntry],
    prefixes: tuple[str, ...],
) -> tuple[str, CatalogEntry] | None:
    """Resolve Georgian launch verb + embedded English catalog target.

    The English recognizer often surrounds a correctly heard product name with
    junk tokens while trying to decode the Georgian verb. Matching a complete,
    registered alias inside that result lets commands such as ``ჩართე night
    rain`` work without fuzzy application-name guessing.
    """
    ka_tokens = normalize_phrase(georgian_text).split()
    en_tokens = normalize_phrase(english_text).split()
    if not ka_tokens or ka_tokens[0] not in prefixes or not en_tokens:
        return None

    matches: list[tuple[int, int, str, CatalogEntry]] = []
    for alias, entry in english_targets.items():
        normalized_alias = normalize_phrase(alias)
        alias_tokens = normalized_alias.split()
        if not alias_tokens or len(alias_tokens) > len(en_tokens):
            continue
        # Keep one-word mixed targets conservative: the English decoder may
        # add only a few junk tokens for the Georgian verb, not a full sentence.
        if len(alias_tokens) == 1 and len(en_tokens) - 1 > 3:
            continue
        width = len(alias_tokens)
        if any(en_tokens[index : index + width] == alias_tokens for index in range(len(en_tokens) - width + 1)):
            matches.append((width, len(normalized_alias), normalized_alias, entry))
    if not matches:
        return None
    matches.sort(key=lambda item: (item[0], item[1]), reverse=True)
    best_width, best_length = matches[0][0], matches[0][1]
    best = [item for item in matches if item[0] == best_width and item[1] == best_length]
    if any(item[3] != best[0][3] for item in best[1:]):
        return None
    return best[0][2], best[0][3]


def mixed_language_launch_target(
    georgian_text: str,
    english_text: str,
    english_targets: dict[str, CatalogEntry],
) -> tuple[str, CatalogEntry] | None:
    return _mixed_language_target(
        georgian_text,
        english_text,
        english_targets,
        COMMAND_PREFIXES["ka"],
    )


def mixed_language_close_target(
    georgian_text: str,
    english_text: str,
    english_targets: dict[str, CatalogEntry],
) -> tuple[str, CatalogEntry] | None:
    return _mixed_language_target(
        georgian_text,
        english_text,
        english_targets,
        MIXED_CLOSE_PREFIXES,
    )


def mixed_language_window_target(
    georgian_text: str,
    english_text: str,
    english_targets: dict[str, CatalogEntry],
) -> tuple[str, str, CatalogEntry] | None:
    """Resolve a Georgian window verb plus a registered English target.

    The returned action ID is selected only from the fixed window-operation
    allowlist. The target must still be a complete alias from the application
    catalog, so decoder noise can never become an arbitrary process name.
    """
    normalized_georgian = normalize_phrase(georgian_text)
    first_token = normalized_georgian.split(maxsplit=1)[0] if normalized_georgian else ""
    for action_id, prefixes in MIXED_WINDOW_PREFIXES.items():
        if first_token not in prefixes:
            continue
        target = _mixed_language_target(
            normalized_georgian,
            english_text,
            english_targets,
            prefixes,
        )
        if target is not None:
            alias, entry = target
            return action_id, alias, entry
    return None


def listen_for_app(
    entries: list[CatalogEntry], settings: Settings, language: str, seconds: float
) -> tuple[str, CatalogEntry | None]:
    model_path = settings.models.get(language)
    if model_path is None:
        raise ValueError(f"Unsupported language: {language}")
    validate_model_directory(model_path)

    from .audio import find_input_device

    device_index, _ = find_input_device(settings.audio.device_name_contains)
    phrases = command_phrases(entries, language)
    grammar = sorted(phrases)
    grammar.append("[unk]")

    SetLogLevel(-1)
    model = Model(str(model_path))
    recognizer = KaldiRecognizer(model, settings.audio.sample_rate, json.dumps(grammar, ensure_ascii=False))
    deadline = time.monotonic() + seconds
    final_text = ""

    with sd.RawInputStream(
        device=device_index,
        samplerate=settings.audio.sample_rate,
        channels=1,
        dtype="int16",
        blocksize=settings.audio.block_size,
    ) as stream:
        while time.monotonic() < deadline:
            data, overflowed = stream.read(settings.audio.block_size)
            if overflowed:
                continue
            if recognizer.AcceptWaveform(bytes(data)):
                text = json.loads(recognizer.Result()).get("text", "")
                if normalize_phrase(text) in phrases:
                    final_text = text
                    break

    if not final_text:
        final_text = json.loads(recognizer.FinalResult()).get("text", "")
    normalized = normalize_phrase(final_text)
    return final_text, phrases.get(normalized)
