from voice_assistant import audio
from voice_assistant.audio import (
    _normalized_device_name,
    audio_stream_needs_reopen,
    find_input_device,
    input_device_names,
    input_device_signature,
)


def test_device_name_normalization_ignores_windows_punctuation() -> None:
    configured = _normalized_device_name("Microphone 2- USB Microphone")
    reported = _normalized_device_name("Microphone (2- USB Microphone)")
    assert configured == reported


def test_missing_preferred_microphone_can_fall_back_to_default(monkeypatch) -> None:
    devices = [
        (0, {"name": "Webcam microphone", "max_input_channels": 1}),
        (2, {"name": "Laptop microphone", "max_input_channels": 2}),
    ]
    monkeypatch.setattr(audio, "input_devices", lambda: devices)
    monkeypatch.setattr(audio.sd.default, "device", (2, 3))

    index, device = find_input_device("Disconnected USB microphone", fallback_to_default=True)

    assert index == 2
    assert input_device_signature(index, device) == (2, "laptopmicrophone", 2)


def test_empty_preference_uses_current_default_microphone(monkeypatch) -> None:
    devices = [
        (0, {"name": "Webcam microphone", "max_input_channels": 1}),
        (2, {"name": "Laptop microphone", "max_input_channels": 2}),
    ]
    monkeypatch.setattr(audio, "input_devices", lambda: devices)
    monkeypatch.setattr(audio.sd.default, "device", (2, 3))

    index, device = find_input_device("")

    assert index == 2
    assert device["name"] == "Laptop microphone"


def test_input_device_names_removes_host_api_duplicates(monkeypatch) -> None:
    devices = [
        (0, {"name": "Microphone (Realtek Audio)", "max_input_channels": 2, "hostapi": 0}),
        (4, {"name": "Microphone Realtek Audio", "max_input_channels": 2, "hostapi": 0}),
        (7, {"name": "USB Microphone", "max_input_channels": 1, "hostapi": 0}),
        (9, {"name": "Stereo Mix", "max_input_channels": 2, "hostapi": 0}),
        (12, {"name": "Microphone (Realtek Audio)", "max_input_channels": 2, "hostapi": 1}),
    ]
    monkeypatch.setattr(audio, "input_devices", lambda: devices)
    monkeypatch.setattr(
        audio.sd,
        "query_hostapis",
        lambda: ({"name": "MME"}, {"name": "Windows DirectSound"}),
    )

    assert input_device_names() == ["Microphone (Realtek Audio)", "USB Microphone"]


def test_stream_reopens_after_resume_gap_or_device_change() -> None:
    usb = (1, "usbmicrophone", 1)
    laptop = (2, "laptopmicrophone", 2)

    assert audio_stream_needs_reopen(10.0, 10.0, usb, usb)
    assert audio_stream_needs_reopen(0.1, 10.0, usb, laptop)
    assert not audio_stream_needs_reopen(0.1, 10.0, usb, usb)
