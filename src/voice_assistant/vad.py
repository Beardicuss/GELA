from __future__ import annotations

from array import array
from collections import deque
import math
from statistics import median


def pcm16_rms(data: bytes) -> float:
    samples = array("h")
    samples.frombytes(data)
    if not samples:
        return 0.0
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples))


class UtteranceBoundary:
    """Track speech segments so recognizers are finalized when VAD returns to silence."""

    def __init__(self) -> None:
        self.active = False

    def reset(self) -> None:
        self.active = False

    def observe(self, is_voice: bool, recognizer_done: bool = False) -> str:
        if is_voice:
            self.active = not recognizer_done
            return "complete" if recognizer_done else "continue"
        if self.active:
            self.active = False
            return "finalize"
        return "idle"


class AdaptiveVoiceActivityDetector:
    def __init__(
        self,
        min_rms: float,
        noise_ratio: float,
        hangover_blocks: int,
        initial_noise_floor: float = 40.0,
        noise_window_blocks: int = 50,
    ) -> None:
        self.min_rms = min_rms
        self.noise_ratio = noise_ratio
        self.hangover_blocks = hangover_blocks
        self.noise_floor = initial_noise_floor
        self._noise_samples = deque([initial_noise_floor], maxlen=noise_window_blocks)
        self._hangover = 0

    @property
    def threshold(self) -> float:
        return max(self.min_rms, self.noise_floor * self.noise_ratio)

    def reset(self) -> None:
        self._hangover = 0

    def process(self, data: bytes) -> tuple[bool, float]:
        rms = pcm16_rms(data)
        is_voice = rms >= self.threshold
        # Use a rolling median of every block, including sustained signals.
        # Classifying against the previous baseline keeps a new speech onset,
        # while the median prevents one short utterance from becoming noise.
        self._noise_samples.append(rms)
        self.noise_floor = median(self._noise_samples)
        if is_voice:
            self._hangover = self.hangover_blocks
            return True, rms
        if self._hangover > 0:
            self._hangover -= 1
            return True, rms
        return False, rms
