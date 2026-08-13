from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from array import array
import re

import sounddevice as sd


def _normalized_device_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.casefold())


def input_devices() -> list[tuple[int, Mapping[str, Any]]]:
    return [
        (index, device)
        for index, device in enumerate(sd.query_devices())
        if int(device["max_input_channels"]) > 0
    ]


def find_input_device(
    name_fragment: str,
    fallback_to_default: bool = False,
) -> tuple[int, Mapping[str, Any]]:
    fragment = _normalized_device_name(name_fragment)
    matches = [
        (index, device)
        for index, device in input_devices()
        if fragment in _normalized_device_name(str(device["name"]))
    ]
    if not matches:
        if fallback_to_default:
            default_input = int(sd.default.device[0])
            fallback = next(
                ((index, device) for index, device in input_devices() if index == default_input),
                None,
            )
            if fallback is not None:
                return fallback
        available = ", ".join(str(device["name"]) for _, device in input_devices()) or "none"
        raise RuntimeError(
            f"No input device matches {name_fragment!r}. Available input devices: {available}"
        )
    default_input = int(sd.default.device[0])
    default_match = next((match for match in matches if match[0] == default_input), None)
    if default_match is not None:
        return default_match
    if len(matches) > 1:
        names = ", ".join(f"{index}: {device['name']}" for index, device in matches)
        raise RuntimeError(f"Multiple input devices match {name_fragment!r}: {names}")
    return matches[0]


def input_device_signature(index: int, device: Mapping[str, Any]) -> tuple[int, str, int]:
    return index, _normalized_device_name(str(device["name"])), int(device["max_input_channels"])


def audio_stream_needs_reopen(
    audio_gap: float,
    resume_gap: float,
    original_device: tuple[int, str, int],
    current_device: tuple[int, str, int],
) -> bool:
    return audio_gap >= resume_gap or current_device != original_device


def verify_input_stream(device_index: int, sample_rate: int, channels: int) -> int:
    sd.check_input_settings(
        device=device_index,
        samplerate=sample_rate,
        channels=channels,
        dtype="int16",
    )
    frames = max(sample_rate // 4, 1)
    with sd.RawInputStream(
        device=device_index,
        samplerate=sample_rate,
        channels=channels,
        dtype="int16",
    ) as stream:
        data, overflowed = stream.read(frames)
    if overflowed:
        raise RuntimeError("Microphone input overflowed during the audio diagnostic")
    samples = array("h")
    samples.frombytes(bytes(data))
    return max((abs(sample) for sample in samples), default=0)
