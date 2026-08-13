from array import array

from voice_assistant.vad import AdaptiveVoiceActivityDetector, UtteranceBoundary, pcm16_rms


def pcm(value: int, count: int = 1600) -> bytes:
    return array("h", [value] * count).tobytes()


def test_pcm16_rms_for_constant_signal() -> None:
    assert pcm16_rms(pcm(500)) == 500


def test_vad_rejects_silence_and_accepts_voice() -> None:
    vad = AdaptiveVoiceActivityDetector(min_rms=180, noise_ratio=3.0, hangover_blocks=2)
    assert vad.process(pcm(0))[0] is False
    assert vad.process(pcm(600))[0] is True


def test_vad_hangover_preserves_trailing_silence_then_stops() -> None:
    vad = AdaptiveVoiceActivityDetector(min_rms=180, noise_ratio=3.0, hangover_blocks=2)
    assert vad.process(pcm(600))[0] is True
    assert vad.process(pcm(0))[0] is True
    assert vad.process(pcm(0))[0] is True
    assert vad.process(pcm(0))[0] is False


def test_vad_learns_sustained_noise_without_treating_it_as_speech() -> None:
    vad = AdaptiveVoiceActivityDetector(min_rms=180, noise_ratio=3.0, hangover_blocks=2)

    decisions = [vad.process(pcm(900))[0] for _ in range(60)]

    assert decisions[-10:] == [False] * 10
    assert vad.threshold >= 2_500


def test_vad_still_accepts_voice_above_a_learned_noise_floor() -> None:
    vad = AdaptiveVoiceActivityDetector(min_rms=180, noise_ratio=3.0, hangover_blocks=2)
    for _ in range(60):
        vad.process(pcm(900))

    is_voice, rms = vad.process(pcm(5_000))

    assert is_voice is True
    assert rms == 5_000


def test_utterance_boundary_forces_final_result_after_silence() -> None:
    boundary = UtteranceBoundary()

    assert boundary.observe(True, False) == "continue"
    assert boundary.observe(True, False) == "continue"
    assert boundary.observe(False, False) == "finalize"
    assert boundary.observe(False, False) == "idle"


def test_utterance_boundary_accepts_normal_recognizer_endpoint() -> None:
    boundary = UtteranceBoundary()

    assert boundary.observe(True, True) == "complete"
    assert boundary.observe(False, False) == "idle"
