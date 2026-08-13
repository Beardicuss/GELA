import json

from voice_assistant.calibration import apply_calibration, recommend_calibration
from voice_assistant.recognizer import RecognitionResult


def test_calibration_requires_three_correct_wake_samples() -> None:
    samples = [
        RecognitionResult("გელა", 0.94),
        RecognitionResult("გელა", 0.91),
        RecognitionResult("სხვა", 0.99),
        RecognitionResult("", 0.0),
        RecognitionResult("გელა", 0.89),
    ]

    assert recommend_calibration(70.0, samples, "გელა") == (0.86, 180)
    assert recommend_calibration(70.0, samples[:2], "გელა") is None


def test_calibration_handles_a_high_noise_microphone() -> None:
    samples = [RecognitionResult("გელა", 0.95) for _ in range(3)]

    assert recommend_calibration(960.0, samples, "გელა") == (0.92, 2400)


def test_apply_calibration_preserves_other_settings(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"audio": {"sample_rate": 16000}, "background": {"wake_confidence": 0.85, "vad_min_rms": 180}}),
        encoding="utf-8",
    )

    apply_calibration(0.9, 220, path)
    result = json.loads(path.read_text(encoding="utf-8"))

    assert result["background"]["wake_confidence"] == 0.9
    assert result["background"]["vad_min_rms"] == 220
    assert result["audio"]["sample_rate"] == 16000
