import os
import logging
import asyncio
import random
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger("filler_service")


class FillerService:
    """
    Manages the pre-synthesis and random hydration of social fillers.
    Ensures 0ms latency for 'Thinking' markers (Hmm, Accha, etc.).
    """

    PRE_SYNTH_LIST = [
        "Hmm...",
        "Let me think.",
        "Okay...",
        "Wait a second.",
        "Got it.",
        "I'm on it.",
        "Just a moment.",
    ]

    def __init__(self, cache_dir: str = "models/fillers"):
        self.cache_dir = cache_dir
        self.cache: Dict[str, bytes] = {}
        self.is_hydrated = False

    async def hydrate(self, sovits_client, ref_audio: str, ref_text: str):
        """
        Pre-synthesize the social vocabulary at startup.
        Uses the specific voice profile to ensure identity consistency.
        """
        base_dir = Path(__file__).parent.parent.parent / self.cache_dir
        os.makedirs(base_dir, exist_ok=True)

        logger.info(
            f"🎙️ Hydrating Social Vocabulary Mesh ({len(self.PRE_SYNTH_LIST)} fillers)..."
        )

        tasks = []
        for text in self.PRE_SYNTH_LIST:
            tasks.append(
                self._get_or_synth(sovits_client, text, ref_audio, ref_text, base_dir)
            )

        results = await asyncio.gather(*tasks)

        for text, pcm in results:
            if pcm:
                self.cache[text] = pcm

        self.is_hydrated = True
        logger.info(
            f"✅ Social Mesh Hydrated. {len(self.cache)} fillers ready for 0ms access."
        )

    async def _get_or_synth(self, client, text, ref_audio, ref_text, base_dir):
        """Fetch from disk or synthesize if missing."""
        clean_name = "".join(c for c in text.lower() if c.isalnum()) + ".pcm"
        file_path = base_dir / clean_name

        if file_path.exists():
            with open(file_path, "rb") as f:
                return text, f.read()

        # Synthesize using SoVITS
        logger.debug(f"Synthesizing filler: {text}")
        pcm_data = await client.synthesize(
            text=text,
            ref_audio_path=ref_audio,
            ref_text=ref_text,
            text_lang="en",
            media_type="raw",
        )

        if pcm_data:
            with open(file_path, "wb") as f:
                f.write(pcm_data)
            return text, pcm_data

        return text, None

    def get_random_filler(self) -> Optional[bytes]:
        """Provides a random PCM buffer from the hydrated mesh."""
        if not self.is_hydrated or not self.cache:
            return None
        return random.choice(list(self.cache.values()))

    def get_specific_filler(self, text: str) -> Optional[bytes]:
        return self.cache.get(text)
