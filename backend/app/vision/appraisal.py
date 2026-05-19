"""
Visual Appraisal Service — Tier-4 VLM Integration.

Converts raw image frames into semantic descriptions via a Vision-Language Model.
Rate-limited and cached to prevent excessive VLM calls on a laptop GPU.
"""

import logging
import time

logger = logging.getLogger(__name__)


class VisualAppraisalService:
    """
    Converts raw base64-encoded frames into natural language descriptions
    using a lightweight VLM (moondream, llava, etc.) via Ollama.

    Design principles:
    - Stateless: just converts images to text
    - Rate-limited: respects VLM_APPRAISAL_INTERVAL
    - Fault-tolerant: returns cached description on VLM failure
    """

    def __init__(
        self,
        ollama_client,
        model: str = "moondream",
        interval: float = 5.0,
        prompt: str = "Describe what you see in this image briefly. Focus on what the user is doing.",
    ):
        self.llm = ollama_client
        self.model = model
        self.interval = interval
        self.prompt = prompt

        self._last_description: str = ""
        self._last_appraisal_time: float = 0.0
        self._last_visual_vector = None

    def should_appraise(self) -> bool:
        """Check if enough time has elapsed since the last VLM call."""
        return (time.time() - self._last_appraisal_time) >= self.interval

    def _compute_visual_vector(self, frame_b64: str) -> list[float]:
        """Convert base64 JPEG frame to a downsampled 16x16 grayscale vector."""
        import base64
        import numpy as np
        try:
            jpeg_bytes = base64.b64decode(frame_b64)
        except Exception:
            return [0.0] * 256
            
        try:
            import cv2
            img = cv2.imdecode(np.frombuffer(jpeg_bytes, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                resized = cv2.resize(img, (16, 16))
                return (resized.flatten().astype(float) / 255.0).tolist()
        except Exception as e:
            logger.debug("[VisualAppraisal] OpenCV downsampling failed, falling back to hash: %s", e)
            
        import hashlib
        h = hashlib.sha256(jpeg_bytes).digest()
        extended = bytearray()
        for i in range(8):
            extended.extend(hashlib.sha256(h + bytes([i])).digest())
        return [b / 255.0 for b in extended[:256]]

    async def appraise(self, frame_b64: str) -> str:
        """
        Analyze a frame and return a semantic description.

        Returns the cached description if:
        - The rate limit hasn't elapsed
        - The sensory habituation delta is below the threshold
        - The VLM call fails
        """
        if not self.should_appraise():
            return self._last_description

        # Compute delta to evaluate sensory habituation
        current_vector = self._compute_visual_vector(frame_b64)
        if self._last_visual_vector is not None:
            try:
                import cognitive_rust
                delta = cognitive_rust.compute_vector_delta(self._last_visual_vector, current_vector)
            except ImportError:
                import numpy as np
                v1 = np.array(self._last_visual_vector)
                v2 = np.array(current_vector)
                delta = float(np.sum((v1 - v2) ** 2) / len(v1))

            from ..config import Config
            threshold = getattr(Config, "VLM_HABITUATION_THRESHOLD", 0.005)
            if delta < threshold:
                logger.info(
                    "[VisualAppraisal] Sensory Habituation: Delta (%.6f) < Threshold (%.6f). Bypassing VLM call.",
                    delta,
                    threshold,
                )
                self._last_appraisal_time = time.time()
                return self._last_description

        try:
            description = await self.llm.describe_image(
                image_b64=frame_b64,
                prompt=self.prompt,
                model=self.model,
            )

            if description:
                self._last_description = description
                self._last_visual_vector = current_vector
                self._last_appraisal_time = time.time()
                logger.info(
                    "[VisualAppraisal] VLM description (%.0fch): %s",
                    len(description),
                    description[:80],
                )
            else:
                logger.warning(
                    "[VisualAppraisal] VLM returned empty description, using cache."
                )

        except Exception as e:
            logger.error(
                "[VisualAppraisal] VLM appraisal failed: %s. Using cached description.",
                e,
            )

        return self._last_description

    @property
    def last_description(self) -> str:
        """Return the most recent cached description."""
        return self._last_description
