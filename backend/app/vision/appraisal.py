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

    def should_appraise(self) -> bool:
        """Check if enough time has elapsed since the last VLM call."""
        return (time.time() - self._last_appraisal_time) >= self.interval

    async def appraise(self, frame_b64: str) -> str:
        """
        Analyze a frame and return a semantic description.

        Returns the cached description if:
        - The rate limit hasn't elapsed
        - The VLM call fails
        """
        if not self.should_appraise():
            return self._last_description

        try:
            description = await self.llm.describe_image(
                image_b64=frame_b64,
                prompt=self.prompt,
                model=self.model,
            )

            if description:
                self._last_description = description
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
