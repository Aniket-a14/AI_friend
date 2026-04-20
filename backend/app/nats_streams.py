import asyncio
import logging
import os
from typing import Dict, List, Sequence

import nats
from nats.errors import NoRespondersError
from nats.js.errors import BadRequestError, ServiceUnavailableError

logger = logging.getLogger("nats_streams")


CORE_STREAMS: Dict[str, Sequence[str]] = {
    "AI_MESSAGES": [
        "chat.*",
        "vision.*",
        "state.*",
        "cmd.*",
        "voice.*",
        "system.*",
        "memory.*",
        "identity.*",
        "knowledge.*",
    ],
    "AI_AUDIO": ["audio.*"],
}


def _is_retryable_error(error: Exception) -> bool:
    return isinstance(
        error,
        (
            NoRespondersError,
            ServiceUnavailableError,
            asyncio.TimeoutError,
            OSError,
        ),
    )


async def _wait_for_jetstream_ready(jsm, retries: int, delay_seconds: float) -> None:
    last_error: Exception = None
    for attempt in range(1, retries + 1):
        try:
            await jsm.account_info()
            return
        except Exception as error:
            if not _is_retryable_error(error) or attempt >= retries:
                last_error = error
                break
            logger.warning(
                "JetStream API not ready (attempt %s/%s): %s",
                attempt,
                retries,
                error,
            )
            await asyncio.sleep(delay_seconds)

    raise RuntimeError(f"JetStream API not ready after {retries} attempts: {last_error}")


async def _ensure_stream(jsm, stream_name: str, subjects: List[str], retries: int, delay_seconds: float) -> None:
    last_error: Exception = None

    for attempt in range(1, retries + 1):
        try:
            await jsm.add_stream(name=stream_name, subjects=subjects)
            logger.info("Created %s stream", stream_name)
            return
        except BadRequestError:
            info = await jsm.stream_info(stream_name)
            current_subjects = set(info.config.subjects or [])
            desired_subjects = set(subjects)
            if desired_subjects.issubset(current_subjects):
                logger.info("%s already synchronized", stream_name)
                return

            config = info.config
            config.subjects = list(current_subjects.union(desired_subjects))
            await jsm.update_stream(config)
            logger.info("Updated %s subjects", stream_name)
            return
        except Exception as error:
            if not _is_retryable_error(error) or attempt >= retries:
                last_error = error
                break
            logger.warning(
                "JetStream stream %s not ready (attempt %s/%s): %s",
                stream_name,
                attempt,
                retries,
                error,
            )
            await asyncio.sleep(delay_seconds)

    raise RuntimeError(f"Failed to synchronize stream '{stream_name}': {last_error}")


async def setup_streams(
    nats_url: str = None,
    retries: int = 15,
    delay_seconds: float = 1.5,
) -> None:
    """Ensure core JetStream streams are available with startup-race tolerance."""
    nats_url = nats_url or os.getenv("NATS_URL", "nats://localhost:4222")
    logger.info("Connecting to NATS at %s", nats_url)

    nc = await nats.connect(nats_url)
    try:
        jsm = nc.jsm()
        await _wait_for_jetstream_ready(jsm, retries=retries, delay_seconds=delay_seconds)

        for stream_name, subjects in CORE_STREAMS.items():
            await _ensure_stream(
                jsm,
                stream_name=stream_name,
                subjects=list(subjects),
                retries=retries,
                delay_seconds=delay_seconds,
            )
    finally:
        await nc.close()

    logger.info("NATS mesh infrastructure ready")
