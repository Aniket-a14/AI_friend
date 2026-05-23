import asyncio
import json
import orjson
import logging
import time
import os
import nats
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    The blueprint for all v3.0 Micro-Agents.
    Communicates via NATS JetStream.
    """

    def __init__(self, name: str, nats_url: str = None):
        self.name = name
        self.nats_url = nats_url or os.getenv("NATS_URL", "nats://127.0.0.1:4222")
        self.nc = None
        self.js = None
        tracked_subjects_raw = os.getenv(
            "MESH_OBSERVED_SUBJECTS",
            "system.tick,memory.surfaced,audio.stop,audio.resume,chat.output",
        )
        self._tracked_subjects = {
            subject.strip()
            for subject in tracked_subjects_raw.split(",")
            if subject.strip()
        }
        self._subject_metrics: Dict[str, Dict[str, float]] = {}
        self._metrics_log_every = max(
            1, int(os.getenv("SUBJECT_METRICS_LOG_EVERY", "25"))
        )

    async def connect(self):
        """Connect to the NATS Mesh and bootstrap streams."""
        try:
            # Add timeout to prevent indefinite hangs if NATS is down
            self.nc = await nats.connect(self.nats_url, connect_timeout=10)
            self.js = self.nc.jetstream()
            await self._bootstrap_mesh()
            logger.info(f"Agent '{self.name}' connected to mesh at {self.nats_url}")
        except Exception as e:
            logger.error(f"Failed to connect agent '{self.name}': {e}")
            raise

    async def _bootstrap_mesh(self):
        """Ensure core streams exist on the mesh (CVS-1.0 Hardened)."""
        core_streams = {
            "AI_MESSAGES": [
                "chat.>",
                "vision.>",
                "state.>",
                "agent.>",
                "cmd.>",
                "voice.>",
                "system.>",
                "memory.>",
                "identity.>",
                "knowledge.>",
            ],
            "AI_AUDIO": ["audio.>"],
        }

        try:
            # Modern nats-py pattern
            jsm = self.nc.jsm()
        except Exception as e:
            logger.warning(
                f"NATS Management not available: {e}. Ensure streams are pre-configured."
            )
            return

        for stream_name, subjects in core_streams.items():
            try:
                await jsm.add_stream(name=stream_name, subjects=subjects)
                logger.info(f"Created NATS Stream: {stream_name} {subjects}")
            except nats.js.errors.BadRequestError:
                # Stream likely already exists, verify subjects
                try:
                    info = await jsm.stream_info(stream_name)
                    current_subjects = set(info.config.subjects or [])
                    required_subjects = set(subjects)

                    if not required_subjects.issubset(current_subjects):
                        logger.info(
                            f"Updating NATS Stream '{stream_name}' with additional subjects..."
                        )
                        config = info.config
                        config.subjects = list(
                            current_subjects.union(required_subjects)
                        )
                        await jsm.update_stream(config)
                        logger.info(
                            f"✅ Stream '{stream_name}' synchronized successfully."
                        )
                except Exception as update_err:
                    logger.debug(f"Stream update note: {update_err}")
            except Exception as e:
                logger.debug(f"Stream bootstrap note: {e}")

    async def publish(
        self, subject: str, data: Any, metadata: Optional[Dict[str, Any]] = None
    ):
        """Publish an event to the mesh with latency tracking and binary support."""
        if not self.js:
            await self.connect()

        # Resolve Enum subjects to their string values (e.g. Topics.CHAT_OUTPUT -> "chat.output")
        from enum import Enum

        if isinstance(subject, Enum):
            subject = subject.value

        from ..config import Config

        # 1. Prepare Metadata
        if metadata:
            meta = dict(metadata)
            meta.setdefault("start_time", time.time())
            meta.setdefault("hops", [])
            meta.setdefault("source", self.name)
        else:
            meta = {"start_time": time.time(), "hops": [], "source": self.name}

        # Propagate existing meta if present in dict data
        if isinstance(data, dict) and "latency_metadata" in data:
            meta = dict(data["latency_metadata"] or {})
            meta.setdefault("start_time", time.time())
            meta.setdefault("hops", [])
            meta.setdefault("source", self.name)

        meta["hops"].append(
            {"agent": self.name, "subject": subject, "timestamp": time.time()}
        )

        # 2. Determine Transport Mode
        is_binary = subject in getattr(Config, "BINARY_SUBJECTS", [])

        try:
            if is_binary and isinstance(data, (bytes, bytearray)):
                # Direct Binary Transport with Headers
                headers = {
                    "X-Latency-Meta": orjson.dumps(meta).decode(),
                    "X-Payload-Format": "binary/raw-pcm",
                }
                await self.js.publish(subject, data, headers=headers, timeout=10)
            else:
                # Standard JSON Transport
                if isinstance(data, dict):
                    data["latency_metadata"] = meta
                payload = orjson.dumps(data)

                # Use JetStream with explicit timeout and core NATS fallback
                try:
                    await self.js.publish(subject, payload, timeout=10)
                except Exception as js_err:
                    logger.warning(
                        f"JetStream publish to {subject} failed ({js_err}), falling back to core NATS"
                    )
                    await self.nc.publish(subject, payload)

            self._record_subject_metric(
                subject,
                direction="publish",
                latency_ms=self._extract_latency_ms(meta),
            )

            logger.debug(
                f"Agent '{self.name}' published to {subject} ({'binary' if is_binary else 'json'})"
            )
        except Exception as e:
            logger.error(f"Failed to publish to {subject}: {e}")

    def log_latency(self, data: Any, stage_name: str):
        """Utility to log current latency relative to start_time."""
        meta = None
        if isinstance(data, dict):
            meta = data.get("latency_metadata")

        if meta and "start_time" in meta:
            elapsed = (time.time() - meta["start_time"]) * 1000
            # Track drift trends (Observability Hook)
            logger.info(
                f"⏱️ [LATENCY] Stage '{stage_name}' | Total: {elapsed:.2f}ms | Hops: {len(meta['hops'])}"
            )
            return elapsed
        return 0

    def _extract_latency_ms(
        self, metadata: Optional[Dict[str, Any]]
    ) -> Optional[float]:
        if not metadata:
            return None
        start_time = metadata.get("start_time")
        if start_time is None:
            return None
        try:
            return max(0.0, (time.time() - float(start_time)) * 1000)
        except (TypeError, ValueError):
            return None

    def _record_subject_metric(
        self,
        subject: str,
        direction: str,
        latency_ms: Optional[float] = None,
    ):
        if subject not in self._tracked_subjects:
            return

        key = f"{direction}:{subject}"
        metric = self._subject_metrics.setdefault(
            key,
            {"count": 0.0, "latency_total_ms": 0.0, "latency_samples": 0.0},
        )
        metric["count"] += 1

        if latency_ms is not None:
            metric["latency_total_ms"] += latency_ms
            metric["latency_samples"] += 1

        count = int(metric["count"])
        if count == 1 or count % self._metrics_log_every == 0:
            avg_latency = 0.0
            if metric["latency_samples"] > 0:
                avg_latency = metric["latency_total_ms"] / metric["latency_samples"]
            logger.info(
                "[SubjectMetrics][%s] subject=%s count=%s avg_latency_ms=%.2f",
                direction,
                subject,
                count,
                avg_latency,
            )

    async def subscribe(
        self,
        subject: str,
        callback,
        durable: str = None,
        deliver_policy: str = "all",
        pending_msgs_limit: int = None,
        pending_bytes_limit: int = None,
    ):
        """
        Subscribe to events on the mesh with header validation and fallback.
        """
        if not self.js:
            await self.connect()

        async def _handler(msg):
            try:
                # 1. Check for Binary Payload + Headers
                if msg.headers and "X-Latency-Meta" in msg.headers:
                    try:
                        meta = json.loads(msg.headers["X-Latency-Meta"])
                        self._record_subject_metric(
                            subject,
                            direction="consume",
                            latency_ms=self._extract_latency_ms(meta),
                        )
                        # Return binary data as-is if it's the target format
                        # or wrap it if the agent expects a dict with meta
                        await callback(msg.data, metadata=meta)
                    except Exception as he:
                        logger.warning(
                            f"Header validation failed on {subject}: {he}. Using fallback."
                        )
                        await callback(msg.data)
                else:
                    # 2. Standard JSON Fallback
                    data = json.loads(msg.data.decode())
                    if isinstance(data, dict):
                        self._record_subject_metric(
                            subject,
                            direction="consume",
                            latency_ms=self._extract_latency_ms(
                                data.get("latency_metadata")
                            ),
                        )
                    await callback(data)

                await msg.ack()
            except Exception as e:
                logger.error(f"Subscription handler error on {subject}: {e}")
                # Auto-ACK fast-moving media, but NACK critical state/chat flows
                if subject.startswith("chat.") or subject.startswith("state."):
                    await msg.nak()
                else:
                    await msg.ack()

        # 3. Durable Management
        # Generate a unique durable name based on the subject if not provided
        if not durable:
            # Replace dots with underscores for NATS-friendly durable name
            subject_suffix = (
                subject.replace(".", "_").replace(">", "all").replace("*", "any")
            )
            durable = f"{self.name}_{subject_suffix}"

        # Mapping string policy to nats.js.api.DeliverPolicy
        from nats.js.api import DeliverPolicy

        policy_map = {
            "all": DeliverPolicy.ALL,
            "new": DeliverPolicy.NEW,
            "last": DeliverPolicy.LAST,
        }
        policy = policy_map.get(deliver_policy, DeliverPolicy.ALL)

        subscribe_kwargs = {
            "cb": _handler,
            "durable": durable,
            "deliver_policy": policy,
        }
        if pending_msgs_limit is not None:
            subscribe_kwargs["pending_msgs_limit"] = pending_msgs_limit
        if pending_bytes_limit is not None:
            subscribe_kwargs["pending_bytes_limit"] = pending_bytes_limit

        # 4. Reliable Subscription (Retry for JetStream availability)
        max_retries = 10
        retry_delay = 1.0

        for attempt in range(1, max_retries + 1):
            try:
                await self.js.subscribe(subject, **subscribe_kwargs)
                logger.info(
                    f"Agent '{self.name}' subscribed to {subject} with durable '{durable}' and policy '{deliver_policy}'"
                )
                return
            except Exception as e:
                # nats.js.errors.NotFoundError: happens when the subject is not mapped to any stream
                from nats.js.errors import NotFoundError

                if isinstance(e, NotFoundError) and attempt < max_retries:
                    logger.warning(
                        f"Agent '{self.name}' subscription to {subject} failed: stream not found (attempt {attempt}/{max_retries}). Retrying in {retry_delay}s..."
                    )
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    logger.error(
                        f"Agent '{self.name}' failed to subscribe to {subject}: {e}"
                    )
                    raise e

    async def set_state(self, state: str):
        """Broadcast agent state to the mesh (e.g., 'thinking', 'speaking', 'idle')"""
        await self.publish(
            "state.update",
            {"agent": self.name, "state": state, "timestamp": time.time()},
        )
        logger.debug(f"Agent '{self.name}' state set to: {state}")

    async def stop(self):
        """Shutdown the agent."""
        if self.nc:
            await self.nc.drain()
            logger.info(f"Agent '{self.name}' shut down.")
