import json
import logging
import time
import os
import nats

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    The blueprint for all v3.0 Micro-Agents.
    Communicates via NATS JetStream.
    """

    def __init__(self, name: str, nats_url: str = None):
        self.name = name
        self.nats_url = nats_url or os.getenv("NATS_URL", "nats://localhost:4222")
        self.nc = None
        self.js = None

    async def connect(self):
        """Connect to the NATS Mesh."""
        try:
            self.nc = await nats.connect(self.nats_url)
            self.js = self.nc.jetstream()
            logger.info(f"Agent '{self.name}' connected to mesh at {self.nats_url}")
        except Exception as e:
            logger.error(f"Failed to connect agent '{self.name}': {e}")
            raise

    async def publish(self, subject: str, data: dict):
        """Publish an event to the mesh."""
        if not self.js:
            await self.connect()

        payload = json.dumps(data).encode()
        await self.js.publish(subject, payload)
        logger.debug(f"Agent '{self.name}' published to {subject}")

    async def subscribe(
        self, subject: str, callback, durable: str = None, deliver_policy: str = "all"
    ):
        """
        Subscribe to events on the mesh.
        deliver_policy: "all" (start from beginning), "new" (start from now), etc.
        """
        if not self.js:
            await self.connect()

        async def _handler(msg):
            data = json.loads(msg.data.decode())
            await callback(data)
            await msg.ack()

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

        await self.js.subscribe(
            subject, cb=_handler, durable=durable, deliver_policy=policy
        )
        logger.info(
            f"Agent '{self.name}' subscribed to {subject} with durable '{durable}' and policy '{deliver_policy}'"
        )

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
