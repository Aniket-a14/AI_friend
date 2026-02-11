import asyncio
import nats
import json
import logging

logger = logging.getLogger(__name__)

class BaseAgent:
    """
    The blueprint for all v3.0 Micro-Agents.
    Communicates via NATS JetStream.
    """
    def __init__(self, name: str, nats_url: str = "nats://localhost:4222"):
        self.name = name
        self.nats_url = nats_url
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

    async def subscribe(self, subject: str, callback):
        """Subscribe to events on the mesh."""
        if not self.js:
            await self.connect()

        async def _handler(msg):
            data = json.loads(msg.data.decode())
            await callback(data)
            await msg.ack()

        await self.js.subscribe(subject, cb=_handler, durable=f"{self.name}_durable")
        logger.info(f"Agent '{self.name}' subscribed to {subject}")

    async def stop(self):
        """Shutdown the agent."""
        if self.nc:
            await self.nc.drain()
            logger.info(f"Agent '{self.name}' shut down.")
