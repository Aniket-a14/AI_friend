import math
from array import array

from ..config import Config

try:
    import numpy as np
except ImportError:
    np = None

try:
    from numba import jit
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False

    # Graceful fallback decorator if Numba is not installed
    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


@jit(nopython=True, fastmath=True)
def _jit_scale_and_clip(samples, scale_val, clip_min, clip_max):
    """JIT compiled linear scaling and bounds clipping for PCM array samples."""
    n = len(samples)
    out = [0] * n
    for i in range(n):
        val = int(samples[i] * scale_val)
        if val < clip_min:
            out[i] = clip_min
        elif val > clip_max:
            out[i] = clip_max
        else:
            out[i] = val
    return out


@jit(nopython=True, fastmath=True)
def _jit_rms(samples):
    """JIT compiled root-mean-square calculation of PCM array samples."""
    if len(samples) == 0:
        return 0.0
    total = 0.0
    for i in range(len(samples)):
        val = float(samples[i])
        total += val * val
    return (total / len(samples)) ** 0.5


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
        if len(audio_data) % 2:
            audio_data = audio_data[:-1]
            if not audio_data:
                return b""

        if np is None:
            samples = array("h")
            samples.frombytes(audio_data[: len(audio_data) - (len(audio_data) % 2)])
            if not samples:
                return b""

            peak = max(max(samples), -min(samples)) if samples else 0
            if peak > 0:
                scale_val = self.target_peak * 32767 / peak
                clip_min, clip_max = -32768, 32767
                
                if HAS_NUMBA:
                    scaled_list = _jit_scale_and_clip(list(samples), scale_val, clip_min, clip_max)
                    samples = array("h", scaled_list)
                else:
                    samples = array(
                        "h",
                        [
                            clip_min if (val := int(s * scale_val)) < clip_min else (clip_max if val > clip_max else val)
                            for s in samples
                        ],
                    )

            if HAS_NUMBA:
                current_rms = _jit_rms(list(samples))
            else:
                current_rms = math.sqrt(
                    sum([sample * sample for sample in samples]) / len(samples)
                )

            tail_len = int(0.1 * self.sample_rate)
            tail_samples = samples[-tail_len:] if len(samples) > tail_len else samples
            
            if HAS_NUMBA:
                self.last_tail_rms = _jit_rms(list(tail_samples)) if len(tail_samples) > 0 else current_rms
            else:
                self.last_tail_rms = (
                    math.sqrt(
                        sum([sample * sample for sample in tail_samples]) / len(tail_samples)
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
