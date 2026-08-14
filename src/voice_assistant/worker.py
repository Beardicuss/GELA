from __future__ import annotations

import ctypes
from difflib import SequenceMatcher
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import time
import threading
import winsound

import sounddevice as sd
from vosk import KaldiRecognizer, Model, SetLogLevel

from .audio import audio_stream_needs_reopen, find_input_device, input_device_signature
from .actions import SystemAction, build_action_phrases, execute_action
from .catalog import CATALOG_PATH, load_catalog, normalize_phrase, scan_catalog
from .config import USER_CONFIG_ROOT, USER_LOG_ROOT, Settings, load_settings
from .launcher import launch_verified
from .models import validate_model_directory
from .recognizer import (
    RecognitionResult,
    canonicalize_georgian_command,
    combine_recognition_results,
    command_phrases,
    decode_result,
    matched_phrase_confidence,
    mixed_language_close_target,
    mixed_language_launch_target,
    mixed_language_window_target,
    split_wake_command,
)
from .responses import VoiceResponses, response_event_for_detail
from .runtime_status import RuntimeStatusStore
from .routines import Routine, execute_routine, routine_phrases
from .vad import AdaptiveVoiceActivityDetector, UtteranceBoundary
from .command_recognizer import OmnilingualCommandRecognizer
from .interaction import (
    CANCEL_PHRASES,
    CommandCandidate,
    choose_command_action,
    should_retry_command,
)
from .intent import expand_intent_phrases
from .local_qa import (
    LocalQuestionAnswerer,
    QuestionModeAction,
    open_answer_window,
    question_phrases,
    save_answer,
)
from .online_services import OnlineServiceAction, OnlineServices, online_phrases


LOG_PATH = USER_LOG_ROOT / "assistant.log"
ENGLISH_ALIASES_PATH = USER_CONFIG_ROOT / "english_aliases.json"
MUTEX_NAME = "Local\\SimpleVoiceAssistantWorker"
EMBEDDED_WAKE_MIN_CONFIDENCE = 0.75


def exact_embedded_wake(
    result: RecognitionResult,
    wake_phrases: list[str],
    minimum_confidence: float,
) -> tuple[str, float] | None:
    """Accept an exact wake token when Vosk inserts unrelated words before it."""
    match = max(
        (
            (phrase, matched_phrase_confidence(result, phrase))
            for phrase in wake_phrases
        ),
        key=lambda candidate: candidate[1],
        default=("", 0.0),
    )
    return match if match[0] and match[1] >= minimum_confidence else None


class WorkerControls:
    def __init__(self, status_callback=None) -> None:
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.reload_event = threading.Event()
        self.release_audio_event = threading.Event()
        self._audio_release_reason = "calibrating"
        self._status = "starting"
        self._status_lock = threading.Lock()
        self._status_callbacks = [status_callback] if status_callback is not None else []

    @property
    def status(self) -> str:
        with self._status_lock:
            return self._status

    def set_status(self, status: str) -> None:
        with self._status_lock:
            if self._status == status:
                return
            self._status = status
        for callback in self._status_callbacks:
            callback(status)

    def add_status_callback(self, callback) -> None:
        self._status_callbacks.append(callback)

    @property
    def audio_release_reason(self) -> str:
        with self._status_lock:
            return self._audio_release_reason

    def request_audio_release(self, reason: str) -> None:
        if reason not in {"calibrating", "recognition_testing"}:
            raise ValueError("Unsupported microphone release reason")
        with self._status_lock:
            self._audio_release_reason = reason
        self.release_audio_event.set()


def configure_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


def acquire_single_instance() -> int:
    handle = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        raise OSError("Could not create worker mutex")
    if ctypes.windll.kernel32.GetLastError() == 183:
        ctypes.windll.kernel32.CloseHandle(handle)
        raise RuntimeError("The voice-assistant worker is already running")
    return handle


class BackgroundAssistant:
    def __init__(self, settings: Settings, diagnostics: RuntimeStatusStore | None = None) -> None:
        self.settings = settings
        self.diagnostics = diagnostics
        if not CATALOG_PATH.is_file():
            scan_catalog()
        self.entries = load_catalog()
        self.phrases = command_phrases(self.entries, settings.background.language)
        model_path = settings.models[settings.background.language]
        validate_model_directory(model_path)
        SetLogLevel(-1)
        self.model = Model(str(model_path))
        self.english_model = Model(str(settings.models["en"]))
        self.command_model = OmnilingualCommandRecognizer(
            settings.models["command"], num_threads=2
        )
        english_aliases = json.loads(ENGLISH_ALIASES_PATH.read_text(encoding="utf-8"))
        entries_by_name = {entry.name: entry for entry in self.entries}
        self.english_phrases = {
            normalize_phrase(alias): entries_by_name[name]
            for name, aliases in english_aliases.items()
            if name in entries_by_name
            for alias in aliases
        }
        self.english_targets = dict(self.english_phrases)
        georgian_actions = build_action_phrases(
            self.entries,
            settings.background.language,
            english_aliases,
        )
        english_actions = build_action_phrases(self.entries, "en", english_aliases)
        self.phrases.update(georgian_actions)
        self.english_phrases.update(english_actions)
        self.english_close_targets = {
            normalize_phrase(alias): english_actions[f"close {normalize_phrase(alias)}"]
            for name, aliases in english_aliases.items()
            if name in entries_by_name
            for alias in aliases
            if f"close {normalize_phrase(alias)}" in english_actions
        }
        english_window_prefixes = {
            "window_focus": "focus",
            "window_minimize": "minimize",
            "window_maximize": "maximize",
            "window_restore": "restore",
        }
        self.english_window_targets = {
            action_id: {
                normalize_phrase(alias): english_actions[f"{prefix} {normalize_phrase(alias)}"]
                for name, aliases in english_aliases.items()
                if name in entries_by_name
                for alias in aliases
                if f"{prefix} {normalize_phrase(alias)}" in english_actions
            }
            for action_id, prefix in english_window_prefixes.items()
        }
        self.phrases.update(routine_phrases(settings.background.language))
        self.english_phrases.update(routine_phrases("en"))
        self.question_answerer: LocalQuestionAnswerer | None = None
        if settings.question_answering.enabled:
            self.question_answerer = LocalQuestionAnswerer(settings.question_answering)
            self.phrases.update(question_phrases(settings.background.language))
            self.english_phrases.update(question_phrases("en"))
        self.online_services = OnlineServices(settings.online_services)
        self.phrases.update(online_phrases(settings.background.language, settings.online_services))
        self.english_phrases.update(online_phrases("en", settings.online_services))
        self.phrases = expand_intent_phrases(self.phrases, settings.background.language)
        self.english_phrases = expand_intent_phrases(self.english_phrases, "en")
        self.responses = VoiceResponses()
        if self.diagnostics is not None:
            self.diagnostics.update(
                models="Vosk wake models and Omnilingual command model loaded",
                catalog=f"Ready — {len(self.entries)} launchable entries",
            )

    def _command_candidates(
        self,
        ka_result: RecognitionResult,
        en_result: RecognitionResult,
    ) -> list[CommandCandidate]:
        ka_result = canonicalize_georgian_command(ka_result)
        candidates: list[CommandCandidate] = []
        ka_entry = self.phrases.get(ka_result.text)
        if ka_entry is not None:
            candidates.append(CommandCandidate(ka_result.confidence, "ka", ka_result, ka_entry))
        en_entry = self.english_phrases.get(en_result.text)
        if en_entry is not None:
            candidates.append(CommandCandidate(en_result.confidence, "en", en_result, en_entry))
        if ka_entry is not None or en_entry is not None:
            return candidates

        mixed = mixed_language_launch_target(
            ka_result.text,
            en_result.text,
            self.english_targets,
        )
        if mixed is not None:
            mixed_alias, mixed_entry = mixed
            mixed_confidence = min(
                matched_phrase_confidence(ka_result, ka_result.text.split()[0]),
                matched_phrase_confidence(en_result, mixed_alias),
            )
            mixed_result = RecognitionResult(
                f"{ka_result.text.split()[0]} {mixed_alias}",
                mixed_confidence,
            )
            candidates.append(
                CommandCandidate(mixed_confidence, "ka+en", mixed_result, mixed_entry)
            )
            return candidates

        mixed_close = mixed_language_close_target(
            ka_result.text,
            en_result.text,
            self.english_targets,
        )
        if mixed_close is not None:
            mixed_alias, _mixed_entry = mixed_close
            close_action = self.english_close_targets.get(mixed_alias)
            if close_action is not None:
                mixed_confidence = min(
                    matched_phrase_confidence(ka_result, ka_result.text.split()[0]),
                    matched_phrase_confidence(en_result, mixed_alias),
                )
                mixed_result = RecognitionResult(
                    f"{ka_result.text.split()[0]} {mixed_alias}",
                    mixed_confidence,
                )
                candidates.append(
                    CommandCandidate(mixed_confidence, "ka+en", mixed_result, close_action)
                )
            return candidates

        mixed_window = mixed_language_window_target(
            ka_result.text,
            en_result.text,
            self.english_targets,
        )
        if mixed_window is not None:
            action_id, mixed_alias, _mixed_entry = mixed_window
            window_action = self.english_window_targets.get(action_id, {}).get(mixed_alias)
            if window_action is not None:
                mixed_confidence = min(
                    matched_phrase_confidence(ka_result, ka_result.text.split()[0]),
                    matched_phrase_confidence(en_result, mixed_alias),
                )
                mixed_result = RecognitionResult(
                    f"{ka_result.text.split()[0]} {mixed_alias}",
                    mixed_confidence,
                )
                candidates.append(
                    CommandCandidate(mixed_confidence, "ka+en", mixed_result, window_action)
                )
        if candidates:
            return candidates
        fuzzy = self._fuzzy_command_candidates(ka_result, self.phrases, "ka")
        if en_result.text and en_result.text != ka_result.text:
            fuzzy.extend(
                self._fuzzy_command_candidates(en_result, self.english_phrases, "en")
            )
        return fuzzy

    @staticmethod
    def _fuzzy_command_candidates(
        result: RecognitionResult,
        phrases: dict[str, object],
        language: str,
    ) -> list[CommandCandidate]:
        """Resolve only a high-confidence, uniquely closest allowlisted phrase."""
        if not result.text or len(result.text.split()) > 8:
            return []
        heard_tokens = result.text.split()
        ranked: list[tuple[float, str, object]] = []
        for phrase, entry in phrases.items():
            phrase_tokens = phrase.split()
            if abs(len(phrase_tokens) - len(heard_tokens)) > 1:
                continue
            if phrase[0] != result.text[0]:
                continue
            maximum_length = max(len(phrase), len(result.text))
            if abs(len(phrase) - len(result.text)) > max(3, maximum_length // 5):
                continue
            score = SequenceMatcher(None, result.text, phrase).ratio()
            if score >= 0.86:
                ranked.append((score, phrase, entry))
        ranked.sort(key=lambda item: item[0], reverse=True)
        distinct: list[tuple[float, str, object]] = []
        for item in ranked:
            if any(item[2] == existing[2] for existing in distinct):
                continue
            distinct.append(item)
            if len(distinct) == 2:
                break
        if not distinct:
            return []
        best_score, best_phrase, best_entry = distinct[0]
        if len(distinct) > 1 and best_score - distinct[1][0] < 0.08:
            return []
        logging.info(
            "Corrected command transcription: %s -> %s (score=%.3f)",
            result.text,
            best_phrase,
            best_score,
        )
        corrected = RecognitionResult(best_phrase, best_score)
        return [CommandCandidate(best_score, f"{language}-fuzzy", corrected, best_entry)]

    def _execute_with_response(self, entry, context: str) -> None:
        try:
            if isinstance(entry, SystemAction):
                detail = execute_action(entry)
            elif isinstance(entry, Routine):
                detail = execute_routine(entry, self.entries)
            else:
                detail = launch_verified(entry)
        except Exception:
            logging.exception("Failed to execute %s from %s", entry.name, context)
            if self.diagnostics is not None:
                self.diagnostics.update(last_execution=f"Failed — {entry.name}")
            self.responses.play("launch_failed", winsound.MB_ICONHAND)
            return
        logging.info("Executed %s from %s%s", entry.name, context, f" ({detail})" if detail else "")
        if self.diagnostics is not None:
            state_labels = {
                "already_running": "Already running",
                "already_stopped": "Already stopped",
                "already_on": "Already on",
                "already_off": "Already off",
            }
            event = response_event_for_detail(detail)
            label = state_labels.get(event, "Successful")
            self.diagnostics.update(last_execution=f"{label} — {entry.name}")
        event = response_event_for_detail(detail)
        if event != "launch_success" and not self.responses.available(event):
            event = "launch_success"
        self.responses.play(event, winsound.MB_ICONASTERISK)

    def _recognizer(self, grammar: list[str]) -> KaldiRecognizer:
        recognizer = KaldiRecognizer(
            self.model,
            self.settings.audio.sample_rate,
            json.dumps([*grammar, "[unk]"], ensure_ascii=False),
        )
        recognizer.SetWords(True)
        return recognizer

    def _english_recognizer(self) -> KaldiRecognizer:
        recognizer = KaldiRecognizer(
            self.english_model,
            self.settings.audio.sample_rate,
            json.dumps([*sorted(self.english_phrases), "[unk]"], ensure_ascii=False),
        )
        recognizer.SetWords(True)
        return recognizer

    def _dictation_recognizer(self, model: Model) -> KaldiRecognizer:
        recognizer = KaldiRecognizer(model, self.settings.audio.sample_rate)
        recognizer.SetWords(True)
        return recognizer

    def _wake_recognizer(self) -> KaldiRecognizer:
        recognizer = KaldiRecognizer(self.model, self.settings.audio.sample_rate)
        recognizer.SetWords(True)
        return recognizer

    def _command_model_result(self, audio: bytes) -> RecognitionResult:
        """Decode one bounded utterance after Vosk has already accepted the wake word."""
        try:
            return self.command_model.transcribe_pcm16(audio)
        except Exception:
            logging.exception("Omnilingual command transcription failed")
            return RecognitionResult("", 0.0)

    def run_stream(self, controls: WorkerControls) -> str:
        device_index, device = find_input_device(
            self.settings.audio.device_name_contains,
            fallback_to_default=self.settings.audio.fallback_to_default_input,
        )
        device_signature = input_device_signature(device_index, device)
        wake_phrases = [normalize_phrase(phrase) for phrase in self.settings.background.wake_phrases]
        wake_recognizer = self._wake_recognizer()
        english_wake_recognizer = (
            self._english_recognizer()
            if self.settings.background.one_sentence_commands
            else None
        )
        wake_segments: list[RecognitionResult] = []
        english_wake_segments: list[RecognitionResult] = []
        wake_audio = bytearray()
        vad = AdaptiveVoiceActivityDetector(
            min_rms=self.settings.background.vad_min_rms,
            noise_ratio=self.settings.background.vad_noise_ratio,
            hangover_blocks=self.settings.background.vad_hangover_blocks,
        )
        wake_boundary = UtteranceBoundary()
        wake_peak_rms = 0.0
        state = "sleeping"
        command_recognizer: KaldiRecognizer | None = None
        english_command_recognizer: KaldiRecognizer | None = None
        command_audio = bytearray()
        command_deadline = 0.0
        command_attempt = 1
        pending_online_action: OnlineServiceAction | None = None
        cooldown_until = 0.0
        logging.info(
            "Listening on device %s (%s), language=%s, wake=%s, catalog=%d",
            device_index,
            device["name"],
            self.settings.background.language,
            wake_phrases,
            len(self.entries),
        )
        if self.diagnostics is not None:
            self.diagnostics.update(
                microphone=f"{device_index}: {device['name']}",
                microphone_state="connected and listening",
            )
        controls.set_status("sleeping")
        catalog_modified = CATALOG_PATH.stat().st_mtime_ns
        last_audio_at = time.monotonic()
        next_device_check = last_audio_at + self.settings.audio.device_check_interval_seconds

        with sd.RawInputStream(
            device=device_index,
            samplerate=self.settings.audio.sample_rate,
            channels=1,
            dtype="int16",
            blocksize=self.settings.audio.block_size,
        ) as stream:
            while True:
                if controls.stop_event.is_set():
                    return "stop"
                if controls.reload_event.is_set():
                    return "reload"
                if controls.release_audio_event.is_set():
                    return "release_audio"
                if CATALOG_PATH.stat().st_mtime_ns != catalog_modified:
                    logging.info("Catalog change detected; reloading worker")
                    return "reload"
                data, overflowed = stream.read(self.settings.audio.block_size)
                now = time.monotonic()
                audio_gap = now - last_audio_at
                last_audio_at = now
                if audio_stream_needs_reopen(
                    audio_gap,
                    self.settings.audio.resume_gap_seconds,
                    device_signature,
                    device_signature,
                ):
                    logging.info("Long audio gap detected (%.1fs); reopening microphone", audio_gap)
                    return "audio_changed"
                if now >= next_device_check:
                    current_index, current_device = find_input_device(
                        self.settings.audio.device_name_contains,
                        fallback_to_default=self.settings.audio.fallback_to_default_input,
                    )
                    current_signature = input_device_signature(current_index, current_device)
                    next_device_check = now + self.settings.audio.device_check_interval_seconds
                    if audio_stream_needs_reopen(
                        0.0,
                        self.settings.audio.resume_gap_seconds,
                        device_signature,
                        current_signature,
                    ):
                        logging.info(
                            "Audio device changed from %s to %s; reopening microphone",
                            device_signature,
                            current_signature,
                        )
                        return "audio_changed"
                if overflowed:
                    logging.warning("Audio input overflow")
                    continue
                audio = bytes(data)

                if controls.pause_event.is_set():
                    if controls.status != "paused":
                        state = "sleeping"
                        wake_recognizer = self._wake_recognizer()
                        english_wake_recognizer = (
                            self._english_recognizer()
                            if self.settings.background.one_sentence_commands
                            else None
                        )
                        wake_segments.clear()
                        english_wake_segments.clear()
                        wake_audio.clear()
                        command_audio.clear()
                        vad.reset()
                        wake_boundary.reset()
                        wake_peak_rms = 0.0
                        controls.set_status("paused")
                    continue
                if controls.status == "paused":
                    controls.set_status("sleeping")

                if state == "cooldown":
                    if now >= cooldown_until:
                        wake_recognizer = self._wake_recognizer()
                        english_wake_recognizer = (
                            self._english_recognizer()
                            if self.settings.background.one_sentence_commands
                            else None
                        )
                        wake_segments.clear()
                        english_wake_segments.clear()
                        wake_audio.clear()
                        command_audio.clear()
                        vad.reset()
                        wake_boundary.reset()
                        wake_peak_rms = 0.0
                        state = "sleeping"
                        controls.set_status("sleeping")
                    continue

                if state == "sleeping":
                    is_voice, rms = vad.process(audio)
                    if is_voice:
                        wake_audio.extend(audio)
                    recognizer_done = wake_recognizer.AcceptWaveform(audio) if is_voice else False
                    english_wake_done = (
                        english_wake_recognizer.AcceptWaveform(audio)
                        if is_voice and english_wake_recognizer is not None
                        else False
                    )
                    if self.settings.background.one_sentence_commands and recognizer_done:
                        segment = decode_result(wake_recognizer.Result())
                        if segment.text:
                            wake_segments.append(segment)
                        wake_recognizer = self._wake_recognizer()
                    if (
                        self.settings.background.one_sentence_commands
                        and english_wake_done
                        and english_wake_recognizer is not None
                    ):
                        segment = decode_result(english_wake_recognizer.Result())
                        if segment.text:
                            english_wake_segments.append(segment)
                        english_wake_recognizer = self._english_recognizer()
                    boundary = wake_boundary.observe(
                        is_voice,
                        recognizer_done
                        and not self.settings.background.one_sentence_commands,
                    )
                    if is_voice:
                        wake_peak_rms = max(wake_peak_rms, rms)
                    if boundary in {"idle", "continue"}:
                        continue
                    completed_wake_audio = bytes(wake_audio)
                    wake_audio.clear()
                    if self.settings.background.one_sentence_commands:
                        result = combine_recognition_results(
                            [*wake_segments, decode_result(wake_recognizer.FinalResult())]
                        )
                        english_wake_result = (
                            combine_recognition_results(
                                [
                                    *english_wake_segments,
                                    decode_result(english_wake_recognizer.FinalResult()),
                                ]
                            )
                            if english_wake_recognizer is not None
                            else RecognitionResult("", 0.0)
                        )
                    else:
                        payload = (
                            wake_recognizer.Result()
                            if boundary == "complete"
                            else wake_recognizer.FinalResult()
                        )
                        result = decode_result(payload)
                        english_wake_result = RecognitionResult("", 0.0)
                    wake_segments.clear()
                    english_wake_segments.clear()
                    wake_recognizer = self._wake_recognizer()
                    english_wake_recognizer = (
                        self._english_recognizer()
                        if self.settings.background.one_sentence_commands
                        else None
                    )
                    wake_split = split_wake_command(result, wake_phrases)
                    embedded_wake = (
                        exact_embedded_wake(
                            result,
                            wake_phrases,
                            max(
                                self.settings.background.wake_confidence,
                                EMBEDDED_WAKE_MIN_CONFIDENCE,
                            ),
                        )
                        if wake_split is None
                        else None
                    )
                    wake_phrase = (
                        wake_split[0]
                        if wake_split
                        else embedded_wake[0] if embedded_wake else ""
                    )
                    confidence = (
                        wake_split[1]
                        if wake_split
                        else embedded_wake[1] if embedded_wake else result.confidence
                    )
                    wake_command = wake_split[2] if wake_split else RecognitionResult("", 0.0)
                    eligible_wake = bool(wake_split or embedded_wake) and (
                        not wake_command.text
                        or self.settings.background.one_sentence_commands
                    )
                    evaluation = (
                        "embedded exact wake"
                        if embedded_wake
                        else "vosk endpoint" if boundary == "complete" else "VAD finalization"
                    )
                    if eligible_wake and confidence >= self.settings.background.wake_confidence:
                        logging.info(
                            "Wake phrase recognized: %s (confidence=%.3f peak_rms=%.1f threshold=%.1f via=%s command=%s)",
                            wake_phrase,
                            confidence,
                            wake_peak_rms,
                            vad.threshold,
                            evaluation,
                            wake_command.text or "[two-stage]",
                        )
                        if self.diagnostics is not None:
                            self.diagnostics.update(
                                last_wake=f"Accepted — {wake_phrase} ({confidence:.3f}, {evaluation})"
                            )
                        wake_peak_rms = 0.0
                        if wake_command.text:
                            stream.stop()
                            command_utterance = self._command_model_result(completed_wake_audio)
                            stream.start()
                            command_split = split_wake_command(command_utterance, wake_phrases)
                            command_options: list[RecognitionResult] = []
                            if command_split is not None:
                                command_options.append(command_split[2])
                            command_options.append(command_utterance)
                            utterance_tokens = command_utterance.text.split()
                            if len(utterance_tokens) > 1:
                                command_options.append(
                                    RecognitionResult(" ".join(utterance_tokens[1:]), 1.0)
                                )
                            command_options = list(
                                {
                                    option.text: option
                                    for option in command_options
                                    if option.text
                                }.values()
                            )
                            command_result = RecognitionResult("", 0.0)
                            one_sentence_action = "reject"
                            selected = None
                            for option in command_options:
                                candidates = self._command_candidates(option, option)
                                option_action, option_selected = choose_command_action(
                                    candidates,
                                    execute_confidence=self.settings.background.command_confidence,
                                    ambiguity_margin=self.settings.background.ambiguity_margin,
                                )
                                if option_action == "execute":
                                    command_result = option
                                    one_sentence_action = option_action
                                    selected = option_selected
                                    break
                            if not command_result.text and command_options:
                                command_result = command_options[0]
                            if self.diagnostics is not None:
                                self.diagnostics.update(
                                    last_command=(
                                        f"One sentence — Omnilingual: "
                                        f"{command_result.text or '[nothing]'}; "
                                        f"Vosk wake/command: {wake_command.text}; "
                                        f"result: {one_sentence_action}"
                                    )
                                )
                            if (
                                one_sentence_action == "execute"
                                and selected is not None
                                and not isinstance(
                                    selected.entry,
                                    (QuestionModeAction, OnlineServiceAction),
                                )
                            ):
                                logging.info(
                                    "Executing one-sentence command: language=%s command=%s",
                                    selected.language,
                                    selected.result.text,
                                )
                                controls.set_status("executing")
                                self._execute_with_response(
                                    selected.entry,
                                    (
                                        "one sentence: "
                                        f"command_model={command_result.text} vosk={wake_command.text}"
                                    ),
                                )
                                cooldown_until = (
                                    time.monotonic()
                                    + self.settings.background.cooldown_seconds
                                )
                                state = "cooldown"
                                controls.set_status("cooldown")
                                continue
                            logging.info(
                                "One-sentence command was not safe to execute; falling back to two-stage mode"
                            )
                        stream.stop()
                        self.responses.play("ready", winsound.MB_OK)
                        stream.start()
                        command_recognizer = self._recognizer(
                            sorted(set(self.phrases) | set(CANCEL_PHRASES))
                        )
                        english_command_recognizer = self._english_recognizer()
                        command_audio.clear()
                        command_deadline = (
                            time.monotonic() + self.settings.background.command_timeout_seconds
                        )
                        command_attempt = 1
                        state = "command"
                        controls.set_status("listening_command")
                    elif eligible_wake:
                        logging.info(
                            "Rejected wake candidate: %s (confidence=%.3f peak_rms=%.1f via=%s)",
                            wake_phrase,
                            confidence,
                            wake_peak_rms,
                            evaluation,
                        )
                        if self.diagnostics is not None:
                            self.diagnostics.update(
                                last_wake=f"Rejected — {wake_phrase} ({confidence:.3f}, {evaluation})"
                            )
                    wake_peak_rms = 0.0
                    continue

                if state == "command" and command_recognizer is not None:
                    command_audio.extend(audio)
                    ka_done = command_recognizer.AcceptWaveform(audio)
                    en_done = (
                        english_command_recognizer.AcceptWaveform(audio)
                        if english_command_recognizer is not None
                        else False
                    )
                    timed_out = now >= command_deadline
                    if ka_done or en_done or timed_out:
                        ka_result = decode_result(
                            command_recognizer.Result() if ka_done else command_recognizer.FinalResult()
                        )
                        en_result = (
                            decode_result(
                                english_command_recognizer.Result()
                                if en_done
                                else english_command_recognizer.FinalResult()
                            )
                            if english_command_recognizer is not None
                            else RecognitionResult("", 0.0)
                        )
                        stream.stop()
                        command_model_result = self._command_model_result(bytes(command_audio))
                        stream.start()
                        command_audio.clear()
                        if command_model_result.text:
                            ka_result = command_model_result
                            en_result = command_model_result
                        if (
                            ka_result.text in CANCEL_PHRASES
                            and ka_result.confidence
                            >= self.settings.background.confirmation_response_confidence
                        ):
                            logging.info("Command cancelled by voice")
                            self.responses.play("cancelled", winsound.MB_ICONHAND)
                            cooldown_until = (
                                time.monotonic() + self.settings.background.cooldown_seconds
                            )
                            state = "cooldown"
                            controls.set_status("cooldown")
                            continue
                        candidates = self._command_candidates(ka_result, en_result)
                        action, selected = choose_command_action(
                            candidates,
                            execute_confidence=self.settings.background.command_confidence,
                            ambiguity_margin=self.settings.background.ambiguity_margin,
                        )
                        logging.info(
                            "Command result: ka=%s(%.3f) en=%s(%.3f) action=%s selected=%s",
                            ka_result.text or "[nothing]",
                            ka_result.confidence,
                            en_result.text or "[nothing]",
                            en_result.confidence,
                            action,
                            selected.language if selected else "none",
                        )
                        if self.diagnostics is not None:
                            self.diagnostics.update(
                                last_command=(
                                    f"KA: {ka_result.text or '[nothing]'} ({ka_result.confidence:.3f}); "
                                    f"EN: {en_result.text or '[nothing]'} ({en_result.confidence:.3f}); "
                                    f"result: {action}"
                                )
                            )
                        controls.set_status("executing")
                        if action == "execute" and selected is not None:
                            if isinstance(selected.entry, QuestionModeAction):
                                logging.info("Entering local question mode")
                                stream.stop()
                                self.responses.play("ready", winsound.MB_OK)
                                stream.start()
                                command_recognizer = self._dictation_recognizer(self.model)
                                english_command_recognizer = self._dictation_recognizer(
                                    self.english_model
                                )
                                command_deadline = (
                                    time.monotonic()
                                    + self.settings.question_answering.question_timeout_seconds
                                )
                                state = "question"
                                controls.set_status("listening_question")
                                continue
                            if isinstance(selected.entry, OnlineServiceAction):
                                if selected.entry.kind == "weather":
                                    try:
                                        question, answer = self.online_services.weather(selected.language)
                                        open_answer_window(save_answer(
                                            question, answer,
                                            window_title="Gela — ამინდი",
                                            source="Open-Meteo",
                                        ))
                                        if self.diagnostics is not None:
                                            self.diagnostics.update(last_execution="Online weather shown")
                                        self.responses.play("launch_success", winsound.MB_ICONASTERISK)
                                    except Exception:
                                        logging.exception("Online weather request failed")
                                        if self.diagnostics is not None:
                                            self.diagnostics.update(last_execution="Online weather failed")
                                        self.responses.play("launch_failed", winsound.MB_ICONHAND)
                                else:
                                    pending_online_action = selected.entry
                                    stream.stop()
                                    self.responses.play("ready", winsound.MB_OK)
                                    stream.start()
                                    command_recognizer = self._dictation_recognizer(self.model)
                                    english_command_recognizer = self._dictation_recognizer(self.english_model)
                                    command_deadline = time.monotonic() + self.settings.online_services.query_timeout_seconds
                                    state = "online_query"
                                    controls.set_status("listening_online_query")
                                    continue
                            else:
                                self._execute_with_response(
                                    selected.entry,
                                    f"phrase: ka={ka_result.text} en={en_result.text}",
                                )
                        else:
                            logging.info("No command matched confidence threshold")
                            if should_retry_command(
                                command_attempt,
                                self.settings.background.command_retry_attempts,
                            ):
                                logging.info(
                                    "Listening for command retry %d/%d without a new wake word",
                                    command_attempt,
                                    self.settings.background.command_retry_attempts,
                                )
                                if self.diagnostics is not None:
                                    self.diagnostics.update(
                                        last_execution=(
                                            f"Waiting for retry {command_attempt}/"
                                            f"{self.settings.background.command_retry_attempts}"
                                        )
                                    )
                                stream.stop()
                                self.responses.play("command_not_understood", winsound.MB_ICONHAND)
                                stream.start()
                                command_attempt += 1
                                command_recognizer = self._recognizer(
                                    sorted(set(self.phrases) | set(CANCEL_PHRASES))
                                )
                                english_command_recognizer = self._english_recognizer()
                                command_audio.clear()
                                command_deadline = (
                                    time.monotonic()
                                    + self.settings.background.command_timeout_seconds
                                )
                                controls.set_status("listening_command")
                                continue
                            if self.diagnostics is not None:
                                self.diagnostics.update(last_execution="Not executed — retry rejected")
                            winsound.MessageBeep(winsound.MB_ICONHAND)
                        cooldown_until = time.monotonic() + self.settings.background.cooldown_seconds
                        state = "cooldown"
                        controls.set_status("cooldown")

                if state == "question" and command_recognizer is not None:
                    ka_done = command_recognizer.AcceptWaveform(audio)
                    en_done = (
                        english_command_recognizer.AcceptWaveform(audio)
                        if english_command_recognizer is not None
                        else False
                    )
                    timed_out = now >= command_deadline
                    if not (ka_done or en_done or timed_out):
                        continue
                    ka_result = decode_result(
                        command_recognizer.Result() if ka_done else command_recognizer.FinalResult()
                    )
                    en_result = (
                        decode_result(
                            english_command_recognizer.Result()
                            if en_done
                            else english_command_recognizer.FinalResult()
                        )
                        if english_command_recognizer is not None
                        else RecognitionResult("", 0.0)
                    )
                    result = max((ka_result, en_result), key=lambda value: value.confidence)
                    language = "ka" if result is ka_result else "en"
                    logging.info(
                        "Local question captured: language=%s confidence=%.3f text=%s",
                        language,
                        result.confidence,
                        result.text or "[nothing]",
                    )
                    if result.text in CANCEL_PHRASES:
                        logging.info("Local question cancelled by voice")
                        self.responses.play("cancelled", winsound.MB_ICONHAND)
                        cooldown_until = (
                            time.monotonic() + self.settings.background.cooldown_seconds
                        )
                        state = "cooldown"
                        controls.set_status("cooldown")
                        continue
                    controls.set_status("answering_question")
                    stream.stop()
                    try:
                        if not result.text or result.confidence < 0.45:
                            raise ValueError("Question was not recognized clearly")
                        if self.question_answerer is None:
                            raise RuntimeError("Local question answering is disabled")
                        answer = self.question_answerer.ask(result.text)
                        open_answer_window(save_answer(result.text, answer))
                        if self.diagnostics is not None:
                            self.diagnostics.update(
                                last_execution=f"Local answer shown — {language.upper()} question"
                            )
                        self.responses.play("launch_success", winsound.MB_ICONASTERISK)
                    except Exception:
                        logging.exception("Local question answering failed")
                        if self.diagnostics is not None:
                            self.diagnostics.update(last_execution="Local question failed")
                        self.responses.play("launch_failed", winsound.MB_ICONHAND)
                    finally:
                        stream.start()
                    cooldown_until = time.monotonic() + self.settings.background.cooldown_seconds
                    state = "cooldown"
                    controls.set_status("cooldown")

                if state == "online_query" and command_recognizer is not None:
                    ka_done = command_recognizer.AcceptWaveform(audio)
                    en_done = english_command_recognizer.AcceptWaveform(audio) if english_command_recognizer else False
                    if not (ka_done or en_done or now >= command_deadline):
                        continue
                    ka_result = decode_result(command_recognizer.Result() if ka_done else command_recognizer.FinalResult())
                    en_result = decode_result(english_command_recognizer.Result() if en_done else english_command_recognizer.FinalResult()) if english_command_recognizer else RecognitionResult("", 0.0)
                    result = max((ka_result, en_result), key=lambda value: value.confidence)
                    language = "ka" if result is ka_result else "en"
                    controls.set_status("fetching_online")
                    stream.stop()
                    try:
                        if result.text in CANCEL_PHRASES:
                            self.responses.play("cancelled", winsound.MB_ICONHAND)
                        elif not result.text or result.confidence < 0.45 or pending_online_action is None:
                            raise ValueError("Online query was not recognized clearly")
                        else:
                            title, answer = self.online_services.wikipedia(result.text, language)
                            open_answer_window(save_answer(title, answer, window_title="Gela — ვიკიპედია", source="ვიკიპედია"))
                            if self.diagnostics is not None:
                                self.diagnostics.update(last_execution="Wikipedia result shown")
                            self.responses.play("launch_success", winsound.MB_ICONASTERISK)
                    except Exception:
                        logging.exception("Online lookup failed")
                        if self.diagnostics is not None:
                            self.diagnostics.update(last_execution="Online lookup failed")
                        self.responses.play("launch_failed", winsound.MB_ICONHAND)
                    finally:
                        stream.start()
                    pending_online_action = None
                    cooldown_until = time.monotonic() + self.settings.background.cooldown_seconds
                    state = "cooldown"
                    controls.set_status("cooldown")


def run_worker(controls: WorkerControls | None = None) -> int:
    configure_logging()
    controls = controls or WorkerControls()
    diagnostics = RuntimeStatusStore()
    controls.add_status_callback(lambda status: diagnostics.update(status=status))
    diagnostics.update(status=controls.status)
    try:
        mutex = acquire_single_instance()
    except RuntimeError as exc:
        logging.info(str(exc))
        return 0
    try:
        first_start = True
        assistant: BackgroundAssistant | None = None
        settings: Settings | None = None
        last_error_response = 0.0
        while not controls.stop_event.is_set():
            try:
                if assistant is None:
                    settings = load_settings()
                    assistant = BackgroundAssistant(settings, diagnostics)
                    if first_start:
                        assistant.responses.play("startup_ready", winsound.MB_OK)
                        first_start = False
                result = assistant.run_stream(controls)
                if result == "stop":
                    break
                if result == "reload":
                    controls.reload_event.clear()
                    controls.set_status("reloading")
                    assistant = None
                    continue
                if result == "audio_changed":
                    controls.set_status("recovering_audio")
                    diagnostics.update(microphone_state="reopening after device or resume change")
                    controls.stop_event.wait(0.5)
                    continue
                if result == "release_audio":
                    release_reason = controls.audio_release_reason
                    controls.set_status(release_reason)
                    microphone_state = (
                        "released for recognition testing"
                        if release_reason == "recognition_testing"
                        else "released for wake-word calibration"
                    )
                    diagnostics.update(microphone_state=microphone_state)
                    while controls.release_audio_event.is_set() and not controls.stop_event.wait(0.1):
                        pass
                    continue
            except Exception:
                logging.exception("Worker stream failed; retrying")
                controls.set_status("recovering_audio")
                diagnostics.update(microphone_state="recovering after an audio error")
                now = time.monotonic()
                if assistant is not None and now - last_error_response >= 60.0:
                    assistant.responses.play("microphone_error", winsound.MB_ICONHAND)
                    last_error_response = now
                retry_seconds = settings.background.retry_seconds if settings is not None else 5.0
                controls.stop_event.wait(retry_seconds)
        controls.set_status("stopped")
        diagnostics.update(microphone_state="stopped")
        return 0
    except Exception:
        logging.exception("Worker stopped unexpectedly")
        diagnostics.update(status="error", microphone_state="worker stopped unexpectedly")
        return 1
    finally:
        ctypes.windll.kernel32.ReleaseMutex(mutex)
        ctypes.windll.kernel32.CloseHandle(mutex)


def main() -> int:
    return run_worker()


if __name__ == "__main__":
    raise SystemExit(main())
