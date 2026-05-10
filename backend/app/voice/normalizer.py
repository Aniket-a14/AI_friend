import math
from array import array

from ..config import Config

try:
    import numpy as np
except ImportError:
    np = None


class AudioNormalizer:
    """
    CVS-1.0 Signal Rendering Engine.
    Handles Peak Normalization, Rate-Adaptive RMS, and Gain Matching.
    """

    def __init__(
        self, target_peak=-1.0, baseline_rms_window=0.1, sample_rate=Config.SAMPLE_RATE
    ):
        self.target_peak = 10 ** (target_peak / 20)  # Convert dB to linear
        self.baseline_rms_window = baseline_rms_window
        self.last_tail_rms = None
        self.sample_rate = sample_rate

    def process(self, audio_data: bytes, speaking_rate: float = 1.0) -> bytes:
        """Apply adaptive normalization and return processed PCM."""
        if not audio_data:
            return b""

        if np is None:
            samples = array("h")
            samples.frombytes(audio_data[: len(audio_data) - (len(audio_data) % 2)])
            if not samples:
                return b""

            peak = max(abs(sample) for sample in samples)
            if peak > 0:
                scale = self.target_peak * 32767 / peak
                samples = array(
                    "h",
                    (
                        max(-32768, min(32767, int(sample * scale)))
                        for sample in samples
                    ),
                )

            current_rms = math.sqrt(
                sum(sample * sample for sample in samples) / len(samples)
            )
            tail_len = int(0.1 * self.sample_rate)
            tail_samples = samples[-tail_len:] if len(samples) > tail_len else samples
            self.last_tail_rms = (
                math.sqrt(
                    sum(sample * sample for sample in tail_samples) / len(tail_samples)
                )
                if tail_samples
                else current_rms
            )
            return samples.tobytes()

        samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)

        # 1. Peak Normalization
        peak = np.max(np.abs(samples))
        if peak > 0:
            samples = samples * (self.target_peak * 32767 / peak)

        # 2. Rate-Adaptive RMS Smoothing (Bounded 40-140ms)
        current_rms = np.sqrt(np.mean(samples**2))

        # 3. Inter-chunk Gain Matching
        if self.last_tail_rms is not None and current_rms > 0:
            gain_multiplier = self.last_tail_rms / current_rms
            gain_multiplier = max(0.5, min(2.0, gain_multiplier))
            samples = samples * gain_multiplier

        # Update tail RMS for next chunk (using last 100ms)
        tail_len = int(0.1 * self.sample_rate)
        if len(samples) > tail_len:
            self.last_tail_rms = np.sqrt(np.mean(samples[-tail_len:] ** 2))
        else:
            self.last_tail_rms = current_rms

        return np.clip(samples, -32768, 32767).astype(np.int16).tobytes()
