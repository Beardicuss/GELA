from voice_assistant import audio
from voice_assistant.audio import (
    _normalized_device_name,
    audio_stream_needs_reopen,
    find_input_device,
    input_device_choices,
    input_device_signature,
    selected_input_device_name,
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


def test_stream_reopens_after_resume_gap_or_device_change() -> None:
    usb = (1, "usbmicrophone", 1)
    laptop = (2, "laptopmicrophone", 2)

    assert audio_stream_needs_reopen(10.0, 10.0, usb, usb)
    assert audio_stream_needs_reopen(0.1, 10.0, usb, laptop)
    assert not audio_stream_needs_reopen(0.1, 10.0, usb, usb)


def test_microphone_choices_show_connected_mme_devices_only(monkeypatch) -> None:
    devices = [
        (0, {"name": "Microsoft Sound Mapper - Input", "max_input_channels": 2, "hostapi": 0}),
        (1, {"name": "Microphone (Realtek(R) Audio)", "max_input_channels": 2, "hostapi": 0}),
        (2, {"name": "Microphone (USB Microphone)", "max_input_channels": 1, "hostapi": 0}),
        (8, {"name": "Microphone (Realtek(R) Audio)", "max_input_channels": 2, "hostapi": 1}),
    ]
    host_apis = {0: {"name": "MME"}, 1: {"name": "Windows WASAPI"}}
    monkeypatch.setattr(audio, "input_devices", lambda: devices)
    monkeypatch.setattr(audio.sd, "query_hostapis", lambda index: host_apis[index])
    monkeypatch.setattr(audio.sd.default, "device", (1, 4))

    choices = input_device_choices()

    assert [choice.name for choice in choices] == [
        "Microphone (Realtek(R) Audio)",
        "Microphone (USB Microphone)",
    ]
    assert choices[0].is_default is True


def test_disconnected_saved_microphone_selects_connected_windows_default() -> None:
    choices = [
        audio.InputDeviceChoice("Microphone (Realtek(R) Audio)", 1, True),
        audio.InputDeviceChoice("Microphone (USB Microphone)", 2, False),
    ]

    selected = selected_input_device_name("Disconnected old microphone", choices)

    assert selected == "Microphone (Realtek(R) Audio)"
